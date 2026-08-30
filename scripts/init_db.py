"""Create the database schema.

Runs every .sql file in sql/ in filename order. All the SQL is written to be
idempotent, so running this repeatedly is harmless — use it to apply new
reference data or view changes too.

    python scripts/init_db.py
"""
from __future__ import annotations

import argparse

from db import SQL_DIR, connect


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", help="Override DATABASE_URL from .env")
    args = parser.parse_args()

    sql_files = sorted(SQL_DIR.glob("*.sql"))
    if not sql_files:
        raise SystemExit(f"No .sql files found in {SQL_DIR}")

    with connect(args.database_url) as conn:
        for path in sql_files:
            print(f"  applying {path.name} ...", end=" ", flush=True)
            with conn.cursor() as cur:
                cur.execute(path.read_text(encoding="utf-8"))
            print("ok")
        conn.commit()

    print(f"\nSchema ready ({len(sql_files)} files applied).")
    print("Next:  python scripts/import_csv.py data/raw/<your-file>.csv")


if __name__ == "__main__":
    main()
