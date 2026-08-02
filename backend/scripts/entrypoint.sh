#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."
python - <<'PY'
import os
import time
from urllib.parse import urlparse

import psycopg2

url = os.environ.get("DATABASE_URL", "")
parsed = urlparse(url)
deadline = time.time() + 60

while time.time() < deadline:
    try:
        conn = psycopg2.connect(
            dbname=parsed.path.lstrip("/") or "postgres",
            user=parsed.username,
            password=parsed.password,
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
        )
        conn.close()
        print("PostgreSQL is ready.")
        break
    except Exception as exc:
        print(f"PostgreSQL not ready yet: {exc}")
        time.sleep(2)
else:
    raise SystemExit("Timed out waiting for PostgreSQL")
PY

echo "Running database migrations..."
alembic upgrade head

echo "Starting API server..."
exec "$@"
