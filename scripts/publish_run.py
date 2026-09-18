"""Choose which tag run the dashboard shows.

    python scripts/publish_run.py                 # show what is published
    python scripts/publish_run.py --run-id 17     # publish run 17

Nothing publishes itself: finishing a tag run does not change the dashboard
until this script points `published_run` at it. Needs sql/007_published_run.sql
applied first (python scripts/init_db.py).
"""
from __future__ import annotations

import argparse

import psycopg

from db import connect


def describe(cur, run_id: int):
    cur.execute(
        "SELECT id, model, prompt_version, finished_at, companies_tagged "
        "FROM tag_runs WHERE id = %s",
        (run_id,),
    )
    return cur.fetchone()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--run-id", type=int, default=None,
                        help="Tag run to publish. Omit to only show what is published.")
    parser.add_argument("--note", default=None,
                        help="Why this run is being published; stored with the pointer")
    parser.add_argument("--database-url", help="Override DATABASE_URL from .env")
    args = parser.parse_args()

    with connect(args.database_url) as conn, conn.cursor() as cur:
        try:
            cur.execute("SELECT run_id, published_at, note FROM published_run WHERE id = 1")
        except psycopg.errors.UndefinedTable:
            raise SystemExit(
                "The published_run table does not exist yet. Apply the schema first:\n"
                "    python scripts/init_db.py"
            ) from None
        current = cur.fetchone()
        current_count = None
        if current:
            run = describe(cur, current[0])
            current_count = run[4]
            print(f"Published : run {run[0]} since {current[1]:%Y-%m-%d %H:%M} — "
                  f"{run[1]}, {run[4]} companies, prompt {run[2]}")
            if current[2]:
                print(f"            note: {current[2]}")
        else:
            print("Published : nothing — the dashboard is empty until a run is published")

        if args.run_id is None:
            return

        run = describe(cur, args.run_id)
        if run is None:
            raise SystemExit(f"tag_run {args.run_id} does not exist.")
        if run[3] is None:
            raise SystemExit(f"tag_run {args.run_id} has not finished; refusing to publish it.")
        if "DRY RUN" in (run[1] or ""):
            raise SystemExit(f"tag_run {args.run_id} is a dry-run stub; refusing to publish it.")
        if not run[4]:
            raise SystemExit(f"tag_run {args.run_id} records no tagged companies; "
                             "refusing to publish it.")
        cur.execute("SELECT count(DISTINCT codice_fiscale) FROM company_tags WHERE run_id = %s",
                    (args.run_id,))
        actual = cur.fetchone()[0]
        if actual != run[4]:
            raise SystemExit(
                f"tag_run {args.run_id} records {run[4]} companies but holds tags for "
                f"{actual}; refusing to publish an inconsistent run."
            )
        if current_count and actual < current_count:
            print(f"  ! run {args.run_id} covers {actual} companies, fewer than the "
                  f"{current_count} published now. Publishing anyway, as asked.")

        cur.execute(
            """
            INSERT INTO published_run (id, run_id, note) VALUES (1, %s, %s)
            ON CONFLICT (id) DO UPDATE
                SET run_id = EXCLUDED.run_id, published_at = now(), note = EXCLUDED.note
            """,
            (args.run_id, args.note),
        )
        conn.commit()
        print(f"Published : run {args.run_id} — {run[1]}, {actual} companies. "
              "The dashboard now shows it.")


if __name__ == "__main__":
    main()
