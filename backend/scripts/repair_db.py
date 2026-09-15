"""Repair schema drift when create_all ran before Alembic 007 (missing documents.team_id)."""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "app.db"


def main() -> int:
    if not DB_PATH.exists():
        print(f"No database at {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(documents)").fetchall()]

    if "team_id" in cols:
        print("documents.team_id already exists — nothing to repair")
    else:
        print("Adding documents.team_id …")
        conn.execute("ALTER TABLE documents ADD COLUMN team_id INTEGER REFERENCES teams(id) ON DELETE CASCADE")
        conn.commit()
        print("Added documents.team_id")

    version = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    if version and version[0] != "007_teams":
        conn.execute("UPDATE alembic_version SET version_num = '007_teams'")
        conn.commit()
        print("Stamped alembic_version -> 007_teams")
    else:
        print(f"alembic_version already {version}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
