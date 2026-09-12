"""Export one tagging run using the v5 bake-off CSV contract.

    python scripts/export_tags.py                 # newest run, Codex filename
    python scripts/export_tags.py --run-id 7
    python scripts/export_tags.py --run-id 7 --tool claudecode

Writes to data/ (git-ignored). The output has exactly the columns, ordering,
encoding, line endings, and 200-company row count required by
the shared tagging contract.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import pathlib
import re

from db import connect, REPO_ROOT


COLUMNS = [
    "codice_fiscale", "denominazione", "ateco", "attivita_label",
    "website_url", "parent_sector", "sector", "product_type",
    "customer_model", "one_line", "fetch_pass", "fetch_bucket",
    "homepage_chars",
]

CONTRACT_ROW_COUNT = 200

# New runs have dedicated provenance columns. For runs written before sql/005,
# recover the same values from the evidence string:
#   "<url> | <n> chars of homepage text | fetch=<bucket> | pass=<pass>"
_URL = re.compile(r"^(.*?)\s*\|\s*\d+\s+chars")
_CHARS = re.compile(r"\|\s*(\d+) chars")
_BUCKET = re.compile(r"fetch=(\w+)")
_PASS = re.compile(r"pass=(\w+)")


def _provenance(current_url, fetch_pass, fetch_bucket, homepage_chars,
                evidence) -> tuple[str, str, str, int]:
    """Return complete, contract-valid fetch provenance for one company."""
    evidence = evidence or ""

    match = _URL.search(evidence)
    website_url = match.group(1).strip() if match else (current_url or "")

    if homepage_chars is None:
        match = _CHARS.search(evidence)
        homepage_chars = int(match.group(1)) if match else 0
    else:
        homepage_chars = int(homepage_chars)

    if not fetch_bucket:
        match = _BUCKET.search(evidence)
        if match:
            fetch_bucket = match.group(1)
        elif homepage_chars == 0:
            fetch_bucket = "DEAD"
        elif homepage_chars < 500:
            fetch_bucket = "THIN"
        else:
            fetch_bucket = "OK"

    if not fetch_pass:
        match = _PASS.search(evidence)
        fetch_pass = match.group(1) if match else (
            "http" if homepage_chars else "none"
        )

    return website_url, fetch_pass, fetch_bucket, homepage_chars


def _write_csv(path: pathlib.Path, rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(COLUMNS)
        writer.writerows(rows)


def _require_contract_row_count(rows, run_id: int) -> None:
    if len(rows) != CONTRACT_ROW_COUNT:
        raise SystemExit(
            f"tag_run {run_id} contains {len(rows)} companies; the contract "
            f"requires exactly {CONTRACT_ROW_COUNT}. No file was written."
        )


def _join_multi_value(values, field: str, run_id: int, cf: str) -> str:
    """Join one or two ordered tag values using the contract delimiter."""
    if not 1 <= len(values) <= 2:
        raise SystemExit(
            f"tag_run {run_id}, company {cf}, has {len(values)} values for "
            f"{field}; the v5 contract requires one or two. No file was written."
        )
    return "|".join(values)


def _single_value(values, default: str, field: str,
                  run_id: int, cf: str) -> str:
    """Return a single-valued tag, rejecting ambiguous stored runs."""
    if not values:
        return default
    if len(values) != 1:
        raise SystemExit(
            f"tag_run {run_id}, company {cf}, has {len(values)} values for "
            f"{field}; the v5 contract requires exactly one. No file was written."
        )
    return values[0]


def _export_row(db_row, run_id: int) -> list[object]:
    """Convert one ordered database aggregate into a contract CSV row."""
    (cf, name, ateco, attivita, current_url, parent_sectors, sectors,
     product_types, customer_models, legacy_business_models, one_lines,
     fetch_pass, fetch_bucket, homepage_chars, evidence) = db_row

    parent_sectors = parent_sectors or ["unclear"]
    product_types = product_types or ["unclear"]
    customer_models = customer_models or legacy_business_models or ["unclear"]
    website_url, fetch_pass, fetch_bucket, homepage_chars = _provenance(
        current_url, fetch_pass, fetch_bucket, homepage_chars, evidence
    )
    return [
        str(cf), name, ateco, attivita, website_url,
        _join_multi_value(parent_sectors, "parent_sector", run_id, str(cf)),
        _single_value(sectors, "unclear", "sector", run_id, str(cf)),
        _join_multi_value(product_types, "product_type", run_id, str(cf)),
        _join_multi_value(customer_models, "customer_model", run_id, str(cf)),
        _single_value(
            one_lines,
            "Tagging failed; no classification was produced.",
            "one_line", run_id, str(cf),
        ),
        fetch_pass, fetch_bucket, homepage_chars,
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", type=int, default=None,
                        help="Which tag_run to export (default: the newest)")
    parser.add_argument("--tool", default="codex",
                        help="Tool name used in the contract filename (default: codex)")
    parser.add_argument("--out", type=pathlib.Path, default=None)
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", args.tool):
        raise SystemExit("--tool must contain only lowercase letters, digits, _ or -.")

    with connect() as conn, conn.cursor() as cur:
        if args.run_id is None:
            cur.execute("SELECT max(id) FROM tag_runs WHERE finished_at IS NOT NULL")
            row = cur.fetchone()
            if not row or row[0] is None:
                raise SystemExit("No finished tag runs found. Run scripts/tag_companies.py first.")
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
                   c.sito_internet_url,
                   array_agg(t.tag_value ORDER BY t.id)
                       FILTER (WHERE t.tag_type = 'parent_sector'),
                   array_agg(t.tag_value ORDER BY t.id)
                       FILTER (WHERE t.tag_type = 'sector'),
                   array_agg(t.tag_value ORDER BY t.id)
                       FILTER (WHERE t.tag_type = 'product_type'),
                   array_agg(t.tag_value ORDER BY t.id)
                       FILTER (WHERE t.tag_type = 'customer_model'),
                   array_agg(t.tag_value ORDER BY t.id)
                       FILTER (WHERE t.tag_type = 'business_model'),
                   array_agg(t.tag_value ORDER BY t.id)
                       FILTER (WHERE t.tag_type = 'one_line'),
                   max(t.fetch_pass),
                   max(t.fetch_bucket),
                   max(t.homepage_chars),
                   max(t.evidence)
            FROM company_tags t
            JOIN companies_current c USING (codice_fiscale)
            WHERE t.run_id = %s
            GROUP BY c.codice_fiscale, c.denominazione, c.ateco_raw,
                     c.attivita_label, c.sito_internet_url
            ORDER BY c.codice_fiscale ASC
        """, (run_id,))
        db_rows = cur.fetchall()

    _require_contract_row_count(db_rows, run_id)

    rows = [_export_row(db_row, run_id) for db_row in db_rows]

    out = args.out or (
        REPO_ROOT / "data" /
        f"tags_{args.tool}_r{run_id}_{datetime.date.today():%Y-%m-%d}.csv"
    )
    _write_csv(out, rows)

    model, prompt_version, finished_at, tagged = meta
    finished = finished_at.strftime("%Y-%m-%d %H:%M") if finished_at else "unfinished"
    print(f"tag_run {run_id}: model={model} prompt={prompt_version} "
          f"finished={finished} companies_tagged={tagged}")
    print(f"Wrote {len(rows)} rows x {len(COLUMNS)} columns")
    print(f"\n{out}")


if __name__ == "__main__":
    main()
