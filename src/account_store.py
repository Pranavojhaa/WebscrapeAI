import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash


class AccountStoreError(RuntimeError):
    pass


class AccountStore:
    def __init__(self, database_url: str):
        self.database_url = database_url.strip()
        self._is_sqlite = self.database_url.startswith("sqlite:///")
        self._memory_connection = None
        self._initialized = False
        self._initialize_lock = threading.Lock()

        if self._is_sqlite:
            self._sqlite_path = self.database_url.removeprefix("sqlite:///")
            if self._sqlite_path == ":memory:":
                self._memory_connection = sqlite3.connect(":memory:", check_same_thread=False)
                self._memory_connection.row_factory = sqlite3.Row
        elif self.database_url.startswith(("postgres://", "postgresql://")):
            self._sqlite_path = None
        else:
            raise AccountStoreError("DATABASE_URL must use PostgreSQL or SQLite.")

    def _connect(self):
        if self._is_sqlite:
            if self._memory_connection is not None:
                return self._memory_connection
            connection = sqlite3.connect(self._sqlite_path, timeout=10)
            connection.row_factory = sqlite3.Row
            return connection

        import psycopg
        from psycopg.rows import dict_row

        database_url = self.database_url
        if database_url.startswith("postgres://"):
            database_url = "postgresql://" + database_url.removeprefix("postgres://")
        return psycopg.connect(database_url, row_factory=dict_row, connect_timeout=5)

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            if connection is not self._memory_connection:
                connection.close()

    def _execute(self, cursor, statement: str, parameters=()):
        if self._is_sqlite:
            statement = statement.replace("%s", "?")
        return cursor.execute(statement, parameters)

    def _timestamp_parameter(self, value: datetime) -> datetime | str:
        value = value.replace(tzinfo=None)
        return value.isoformat(sep=" ") if self._is_sqlite else value

    def initialize(self, bootstrap_email: str = "", bootstrap_password: str = "") -> None:
        if self._initialized:
            return
        with self._initialize_lock:
            if self._initialized:
                return
            with self._connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        """CREATE TABLE IF NOT EXISTS users (
                            email TEXT PRIMARY KEY,
                            password_hash TEXT NOT NULL,
                            is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                            is_active BOOLEAN NOT NULL DEFAULT TRUE,
                            session_version INTEGER NOT NULL DEFAULT 0,
                            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )"""
                    )
                    self._apply_schema_migrations(cursor)
                    self._execute(cursor, "SELECT COUNT(*) AS user_count FROM users")
                    user_count = cursor.fetchone()["user_count"]
                    if user_count == 0:
                        email = bootstrap_email.strip().lower()
                        if not email or len(bootstrap_password) < 16:
                            raise AccountStoreError(
                                "Set BOOTSTRAP_ADMIN_EMAIL and a 16-character BOOTSTRAP_ADMIN_PASSWORD to initialize the first admin."
                            )
                        self._execute(
                            cursor,
                            "INSERT INTO users (email, password_hash, is_admin, is_active) VALUES (%s, %s, %s, %s) ON CONFLICT (email) DO NOTHING",
                            (email, generate_password_hash(bootstrap_password), True, True),
                        )
                    self._initialized = True
                finally:
                    cursor.close()

    def _apply_schema_migrations(self, cursor) -> None:
        if not self._is_sqlite:
            cursor.execute("SELECT pg_advisory_xact_lock(739184201)")
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        self._execute(
            cursor,
            "INSERT INTO schema_migrations (version, name) VALUES (%s, %s) ON CONFLICT (version) DO NOTHING",
            (1, "existing users table baseline"),
        )
        self._execute(cursor, "SELECT version FROM schema_migrations")
        applied = {row["version"] for row in cursor.fetchall()}

        if 2 not in applied:
            if self._is_sqlite:
                cursor.execute("PRAGMA table_info(users)")
                columns = {row["name"] for row in cursor.fetchall()}
                if "session_version" not in columns:
                    cursor.execute(
                        "ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0"
                    )
            else:
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS session_version INTEGER NOT NULL DEFAULT 0"
                )
            self._execute(
                cursor,
                "INSERT INTO schema_migrations (version, name) VALUES (%s, %s) ON CONFLICT (version) DO NOTHING",
                (2, "revoke sessions after password changes"),
            )

        if 3 not in applied:
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    token_hash TEXT PRIMARY KEY,
                    email TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
                    expires_at TIMESTAMP NOT NULL
                )"""
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS password_reset_tokens_email_idx ON password_reset_tokens (email)"
            )
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS password_reset_tokens_email_uq ON password_reset_tokens (email)"
            )
            self._execute(
                cursor,
                "INSERT INTO schema_migrations (version, name) VALUES (%s, %s) ON CONFLICT (version) DO NOTHING",
                (3, "single-use password reset tokens"),
            )
    def get_user(self, email: str):
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                self._execute(
                    cursor,
                    "SELECT email, password_hash, is_admin, is_active, session_version, created_at FROM users WHERE email = %s",
                    (email.strip().lower(),),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return {
                    "email": row["email"],
                    "password_hash": row["password_hash"],
                    "is_admin": bool(row["is_admin"]),
                    "is_active": bool(row["is_active"]),
                    "session_version": int(row["session_version"]),
                    "created_at": row["created_at"],
                }
            finally:
                cursor.close()

    def authenticate(self, email: str, password: str):
        user = self.get_user(email)
        if user and user["is_active"] and check_password_hash(user["password_hash"], password):
            return user
        return None

    def issue_password_reset(self, email: str, token_hash: str, expires_at: datetime) -> bool:
        email = email.strip().lower()
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                self._execute(
                    cursor,
                    "DELETE FROM password_reset_tokens WHERE expires_at <= %s",
                    (self._timestamp_parameter(datetime.now(timezone.utc)),),
                )
                self._execute(cursor, "SELECT is_active FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()
                if user is None or not user["is_active"]:
                    return False
                self._execute(
                    cursor,
                    "INSERT INTO password_reset_tokens (token_hash, email, expires_at) VALUES (%s, %s, %s) ON CONFLICT (email) DO UPDATE SET token_hash = EXCLUDED.token_hash, expires_at = EXCLUDED.expires_at",
                    (token_hash, email, self._timestamp_parameter(expires_at)),
                )
                return True
            finally:
                cursor.close()

    def delete_password_reset_token(self, token_hash: str) -> None:
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                self._execute(
                    cursor,
                    "DELETE FROM password_reset_tokens WHERE token_hash = %s",
                    (token_hash,),
                )
            finally:
                cursor.close()

    def consume_password_reset(self, token_hash: str, password: str, now: datetime | None = None) -> bool:
        if len(password) < 16 or len(password) > 1024:
            raise AccountStoreError("Choose a password between 16 and 1024 characters.")
        current_time = self._timestamp_parameter(now or datetime.now(timezone.utc))
        password_hash = generate_password_hash(password)
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                self._execute(
                    cursor,
                    "DELETE FROM password_reset_tokens WHERE token_hash = %s AND expires_at > %s RETURNING email",
                    (token_hash, current_time),
                )
                token = cursor.fetchone()
                if token is None:
                    return False
                email = token["email"]
                self._execute(
                    cursor,
                    "UPDATE users SET password_hash = %s, session_version = session_version + 1 WHERE email = %s AND is_active = %s",
                    (password_hash, email, True),
                )
                if cursor.rowcount != 1:
                    return False
                self._execute(cursor, "DELETE FROM password_reset_tokens WHERE email = %s", (email,))
                return True
            finally:
                cursor.close()

    def list_users(self):
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                self._execute(
                    cursor,
                    "SELECT email, is_admin, is_active, created_at FROM users ORDER BY email",
                )
                return [
                    {
                        "email": row["email"],
                        "is_admin": bool(row["is_admin"]),
                        "is_active": bool(row["is_active"]),
                        "created_at": row["created_at"],
                    }
                    for row in cursor.fetchall()
                ]
            finally:
                cursor.close()

    def create_user(self, email: str, password: str) -> None:
        email = email.strip().lower()
        try:
            with self._connection() as connection:
                cursor = connection.cursor()
                try:
                    self._execute(
                        cursor,
                        "INSERT INTO users (email, password_hash, is_admin, is_active) VALUES (%s, %s, %s, %s)",
                        (email, generate_password_hash(password), False, True),
                    )
                finally:
                    cursor.close()
        except Exception as error:
            if isinstance(error, sqlite3.IntegrityError) or getattr(error, "sqlstate", None) == "23505":
                raise AccountStoreError("An account with that email already exists.") from error
            raise

    def set_active(self, email: str, is_active: bool, actor_email: str) -> None:
        email = email.strip().lower()
        actor_email = actor_email.strip().lower()
        if not is_active and email == actor_email:
            raise AccountStoreError("You cannot disable your own account.")

        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                self._execute(
                    cursor,
                    "SELECT is_admin, is_active FROM users WHERE email = %s",
                    (email,),
                )
                target = cursor.fetchone()
                if target is None:
                    raise AccountStoreError("That account does not exist.")
                if not is_active and target["is_admin"]:
                    self._execute(
                        cursor,
                        "SELECT COUNT(*) AS admin_count FROM users WHERE is_admin = %s AND is_active = %s AND email <> %s",
                        (True, True, email),
                    )
                    if cursor.fetchone()["admin_count"] == 0:
                        raise AccountStoreError("The last active admin account cannot be disabled.")
                self._execute(
                    cursor,
                    "UPDATE users SET is_active = %s WHERE email = %s",
                    (is_active, email),
                )
            finally:
                cursor.close()
