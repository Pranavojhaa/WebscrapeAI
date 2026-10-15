FROM python:3.12.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY src/ ./src/

RUN groupadd --system app \
    && useradd --system --gid app --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin app

USER app
EXPOSE 8080

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 40 src.app:app"]
