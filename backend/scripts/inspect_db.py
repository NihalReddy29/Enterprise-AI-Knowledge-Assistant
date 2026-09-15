import sqlite3

c = sqlite3.connect("app.db")
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("tables", sorted(tables))
if "alembic_version" in tables:
    print("alembic", list(c.execute("SELECT * FROM alembic_version")))
print("docs", [x[1] for x in c.execute("pragma table_info(documents)")])
