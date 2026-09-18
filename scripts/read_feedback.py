"""Show what readers of the dashboard have written.

    python scripts/read_feedback.py            # everything, newest first
    python scripts/read_feedback.py --new      # only what has not been handled
    python scripts/read_feedback.py --handle 7 # mark note 7 as dealt with

Read-only unless --handle is passed.
"""
from __future__ import annotations

import argparse
import textwrap

from db import connect


def _where(company: str | None, page: str | None) -> str:
    """What the note was written about, in words rather than in a URL path."""
    if company:
        return company
    if not page or page == "/":
        return "the results list"
    return page


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new", action="store_true", help="Only unhandled notes")
    parser.add_argument("--handle", type=int, metavar="ID", help="Mark one note handled")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--database-url", help="Override DATABASE_URL from .env")
    args = parser.parse_args()

    with connect(args.database_url) as conn:
        if args.handle is not None:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE feedback SET handled_at = now() WHERE id = %s AND handled_at IS NULL",
                    (args.handle,),
                )
                if cur.rowcount == 0:
                    raise SystemExit(f"No unhandled note with id {args.handle}.")
            conn.commit()
            print(f"Note {args.handle} marked handled.")
            return

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT f.id, f.created_at, f.message, f.page, f.run_id,
                       f.handled_at, c.denominazione
                FROM feedback f
                LEFT JOIN companies_current c ON c.codice_fiscale = f.codice_fiscale
                WHERE (%s IS FALSE OR f.handled_at IS NULL)
                ORDER BY f.created_at DESC
                LIMIT %s
                """,
                (args.new, args.limit),
            )
            rows = cur.fetchall()

    if not rows:
        print("No feedback yet." if not args.new else "Nothing unhandled.")
        return

    for note_id, created, message, page, run_id, handled, company in rows:
        mark = "" if handled is None else "  (handled)"
        where = _where(company, page)
        print(f"\n#{note_id}  {created:%Y-%m-%d %H:%M}  on {where}  [run {run_id}]{mark}")
        print(textwrap.indent(textwrap.fill(message, 76), "    "))

    print(f"\n{len(rows)} note{'' if len(rows) == 1 else 's'}.")


if __name__ == "__main__":
    main()
