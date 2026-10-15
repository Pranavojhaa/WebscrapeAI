import sqlite3
import threading
from contextlib import contextmanager

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
                            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )"""
                    )
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

    def get_user(self, email: str):
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                self._execute(
                    cursor,
                    "SELECT email, password_hash, is_admin, is_active, created_at FROM users WHERE email = %s",
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
                    "created_at": row["created_at"],
                }
            finally:
                cursor.close()

    def authenticate(self, email: str, password: str):
        user = self.get_user(email)
        if user and user["is_active"] and check_password_hash(user["password_hash"], password):
            return user
        return None

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
