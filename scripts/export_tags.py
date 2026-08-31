"""Export one tagging run to a CSV for reading through by hand.

    python scripts/export_tags.py                 # newest finished run
    python scripts/export_tags.py --run-id 2

Writes to data/ (git-ignored). One row per company, with the four tag types
pivoted into columns so the file opens sensibly in a spreadsheet.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import pathlib
import re

from db import connect, REPO_ROOT
from tag_companies import CONFIDENCE_TO_NUMERIC

# Invert the mapping tag_companies.py used when writing, so the CSV shows the
# label the model actually produced rather than the numeric we store.
NUMERIC_TO_CONFIDENCE = {v: k for k, v in CONFIDENCE_TO_NUMERIC.items()}

COLUMNS = [
    "codice_fiscale", "denominazione", "ateco", "attivita_label",
    "sector", "business_model", "product_type", "one_line",
    # v1 runs carry `confidence`; v2 onwards carry `evidence_basis` instead.
    # Both columns are emitted for every run so one file shape opens in Excel
    # regardless of which prompt version produced the run; the column that
    # does not apply is simply blank.
    "confidence", "evidence_basis",
    "website_url", "fetch_bucket", "homepage_chars",
]

# The evidence column is free text written by tag_companies.py in the shape
#   "<url> | <n> chars of homepage text | fetch=<bucket>"
# so these two patterns are tied to that writer. If it changes, change these.
_CHARS = re.compile(r"\|\s*(\d+) chars")
_BUCKET = re.compile(r"fetch=(\w+)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", type=int, default=None,
                        help="Which tag_run to export (default: the newest)")
    parser.add_argument("--out", type=pathlib.Path, default=None)
    args = parser.parse_args()

    with connect() as conn, conn.cursor() as cur:
        if args.run_id is None:
            cur.execute("SELECT max(id) FROM tag_runs")
            row = cur.fetchone()
            if not row or row[0] is None:
                raise SystemExit("No tag runs found. Run scripts/tag_companies.py first.")
            run_id = row[0]
        else:
            run_id = args.run_id

        cur.execute("SELECT model, prompt_version, finished_at, companies_tagged "
                    "FROM tag_runs WHERE id = %s", (run_id,))
        meta = cur.fetchone()
        if meta is None:
            raise SystemExit(f"tag_run {run_id} does not exist.")

        cur.execute("""
            SELECT c.codice_fiscale,
                   c.denominazione,
                   c.ateco_raw,
                   c.attivita_label,
                   max(CASE WHEN t.tag_type = 'sector'         THEN t.tag_value END),
                   max(CASE WHEN t.tag_type = 'business_model' THEN t.tag_value END),
                   max(CASE WHEN t.tag_type = 'product_type'   THEN t.tag_value END),
                   max(CASE WHEN t.tag_type = 'one_line'       THEN t.tag_value END),
                   max(CASE WHEN t.tag_type = 'evidence_basis' THEN t.tag_value END),
                   max(t.confidence),
                   c.sito_internet_url,
                   max(t.evidence)
            FROM company_tags t
            JOIN companies_current c USING (codice_fiscale)
            WHERE t.run_id = %s
            GROUP BY c.codice_fiscale, c.denominazione, c.ateco_raw,
                     c.attivita_label, c.sito_internet_url
            ORDER BY c.denominazione
        """, (run_id,))
        rows = cur.fetchall()

    if not rows:
        raise SystemExit(f"tag_run {run_id} has no tags attached to it.")

    out = args.out or (REPO_ROOT / "data" /
                       f"tags_run{run_id}_{datetime.date.today():%Y-%m-%d}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        for (cf, name, ateco, attivita, sector, bm, pt, one_line,
             evidence_basis, confidence, url, evidence) in rows:
            evidence = evidence or ""
            chars = _CHARS.search(evidence)
            bucket = _BUCKET.search(evidence)
            writer.writerow([
                cf, name, ateco, attivita, sector, bm, pt, one_line,
                # v2 stores no numeric confidence, so this is blank there.
                "" if confidence is None
                   else NUMERIC_TO_CONFIDENCE.get(float(confidence), confidence),
                evidence_basis or "",
                url,
                bucket.group(1) if bucket else "",
                chars.group(1) if chars else "",
            ])

    model, prompt_version, finished_at, tagged = meta
    print(f"tag_run {run_id}: model={model} prompt={prompt_version} "
          f"finished={finished_at:%Y-%m-%d %H:%M} companies={tagged}")
    print(f"Wrote {len(rows)} rows x {len(COLUMNS)} columns")
    print(f"\n{out}")


if __name__ == "__main__":
    main()
