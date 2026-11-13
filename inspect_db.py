import sqlite3
from pathlib import Path

paths = [
    Path("src/research_agent/data/aspasia.db"),
    Path("data/aspasia.db"),
]

for path in paths:
    print(f"\nDatabase: {path.resolve()}")
    print(f"Exists: {path.exists()}")
    print(f"Size: {path.stat().st_size if path.exists() else 0}")

    if not path.exists():
        continue

    with sqlite3.connect(path) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()

        print("Tables:", [item[0] for item in tables])

        if "alembic_version" in [item[0] for item in tables]:
            version = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()

            print("Alembic version:", version)
