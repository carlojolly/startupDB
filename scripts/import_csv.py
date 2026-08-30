"""Load a registry CSV export into Postgres.

    python scripts/import_csv.py data/raw/startup_2026-08-30.csv
    python scripts/import_csv.py data/raw/latest.csv --dry-run

Safe to run twice. Three separate mechanisms make sure of it:

  1. Every file is fingerprinted with SHA-256 and recorded in `imports`, which
     has a UNIQUE constraint on that fingerprint. Re-running the identical file
     stops before a single row is parsed.
  2. Snapshots are only written when a company's content hash differs from its
     previous snapshot, so importing a *new* file that happens to contain
     unchanged companies adds nothing for them.
  3. `company_snapshots` has UNIQUE (codice_fiscale, import_id), so even a
     bug in this script cannot double-insert within one import.

The whole load runs inside a single transaction: if anything fails halfway,
nothing is written at all.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import pathlib
import sys
from collections import Counter

from psycopg.types.json import Json

import clean
from db import connect

# The CSV is UTF-8 *with a BOM*; utf-8-sig strips it so the first column name
# is 'denominazione' and not '﻿denominazione'.
CSV_ENCODING = "utf-8-sig"


class _DryRunRollback(Exception):
    """Raised to abort the transaction at the end of a --dry-run.

    psycopg rolls the transaction back when the `with` block exits via an
    exception, which is a stronger guarantee than calling rollback() and
    trusting that the implicit commit on a clean exit does nothing.
    """

SNAPSHOT_COLUMNS = (
    "codice_fiscale", "import_id", "content_hash", "observed_on",
    "denominazione", "natura_giuridica", "in_liquidazione",
    "pv", "comune",
    "data_iscrizione_sezione_startup", "data_iscrizione_registro_imprese",
    "data_inizio_attivita", "data_dichiarazione",
    "ateco_raw", "ateco_division", "settore", "attivita_label",
    "classe_produzione", "classe_addetti", "classe_capitale",
    "req_ricerca_sviluppo", "req_personale_qualificato", "req_brevetto",
    "vocazione_sociale", "alto_valore_tecnologico_energetico",
    "prevalenza_femminile", "prevalenza_giovanile", "prevalenza_straniera",
    "sito_internet_raw", "sito_internet_url", "sito_internet_domain",
    "raw_record",
)


def sha256_of_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_and_clean(path: pathlib.Path) -> tuple[list[dict], Counter]:
    """Parse the CSV and clean every usable row.

    Returns (cleaned_rows, stats). Rows without a valid 11-digit codice fiscale
    are skipped — in the August 2026 export that is 274 completely empty rows
    left behind by the spreadsheet that produced the file.
    """
    stats = Counter()
    cleaned_rows: list[dict] = []
    seen_cf: set[str] = set()

    with path.open(encoding=CSV_ENCODING, newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise SystemExit(f"{path} appears to be empty.")
        columns = clean.resolve_columns(reader.fieldnames)

        for raw_row in reader:
            stats["rows_in_file"] += 1
            cf = (raw_row.get(columns["codice_fiscale"]) or "").strip()

            if not cf:
                stats["skipped_blank"] += 1
                continue
            if not clean.is_valid_codice_fiscale(cf):
                stats["skipped_bad_cf"] += 1
                if stats["skipped_bad_cf"] <= 5:
                    print(f"  ! skipping malformed codice fiscale: {cf!r}")
                continue
            if cf in seen_cf:
                # Two rows for one company inside a single file. Keep the
                # first and report it rather than silently picking one.
                stats["skipped_duplicate_in_file"] += 1
                print(f"  ! duplicate codice fiscale within the file: {cf}")
                continue

            seen_cf.add(cf)
            row = clean.clean_row(raw_row, columns)
            row["codice_fiscale"] = cf
            row["content_hash"] = clean.content_hash(row)
            # Store the original verbatim, minus empty cells, as an escape hatch.
            row["raw_record"] = {k: v for k, v in raw_row.items() if (v or "").strip()}
            cleaned_rows.append(row)
            stats["rows_valid"] += 1

    return cleaned_rows, stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("csv_path", type=pathlib.Path, help="Path to the registry CSV")
    parser.add_argument("--database-url", help="Override DATABASE_URL from .env")
    parser.add_argument(
        "--as-of",
        help="Date this snapshot represents (YYYY-MM-DD). "
             "Defaults to the file's modification date.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Do the whole import, print the summary, then roll back.",
    )
    parser.add_argument(
        "--no-delist", action="store_true",
        help="Skip marking absent companies inactive. Use when loading an old "
             "file after a newer one, which would otherwise delist wrongly.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-import a file already loaded. Deletes the previous import "
             "record and its snapshots first. Repair tool — not routine.",
    )
    args = parser.parse_args()

    path: pathlib.Path = args.csv_path
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    observed_on = (
        datetime.date.fromisoformat(args.as_of) if args.as_of
        else datetime.date.fromtimestamp(path.stat().st_mtime)
    )

    print(f"File      : {path}")
    print(f"As of     : {observed_on}  ({'--as-of' if args.as_of else 'file mtime'})")
    print("Fingerprinting ...", end=" ", flush=True)
    file_hash = sha256_of_file(path)
    print(file_hash[:16] + "...")

    print("Reading CSV ...")
    rows, stats = read_and_clean(path)
    print(f"  {stats['rows_in_file']} rows in file, {stats['rows_valid']} valid companies")
    if stats["skipped_blank"]:
        print(f"  {stats['skipped_blank']} blank rows skipped (spreadsheet padding)")
    if stats["skipped_bad_cf"]:
        print(f"  {stats['skipped_bad_cf']} rows skipped: malformed codice fiscale")
    if not rows:
        raise SystemExit("Nothing to import.")

    try:
        with connect(args.database_url) as conn:
            with conn.cursor() as cur:
                # --- 1. Has this exact file been loaded before? ------------------
                cur.execute(
                    "SELECT id, imported_at FROM imports WHERE file_sha256 = %s", (file_hash,)
                )
                existing = cur.fetchone()
                if existing and not args.force:
                    print(
                        f"\nThis exact file was already imported "
                        f"(import id {existing[0]}, on {existing[1]:%Y-%m-%d %H:%M}).\n"
                        "Nothing to do. Use --force to load it again."
                    )
                    return
                if existing and args.force:
                    print(f"\n--force: removing previous import {existing[0]} and its snapshots")
                    cur.execute("DELETE FROM company_snapshots WHERE import_id = %s", (existing[0],))
                    cur.execute("DELETE FROM imports WHERE id = %s", (existing[0],))

                # --- 2. Open the import record -----------------------------------
                cur.execute(
                    """
                    INSERT INTO imports (source_filename, file_sha256, file_size_bytes,
                                         file_modified_at, rows_in_file, rows_valid, rows_skipped)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        path.name, file_hash, path.stat().st_size,
                        datetime.datetime.fromtimestamp(path.stat().st_mtime),
                        stats["rows_in_file"], stats["rows_valid"],
                        stats["rows_in_file"] - stats["rows_valid"],
                    ),
                )
                import_id = cur.fetchone()[0]
                print(f"\nImport id : {import_id}")

                # --- 3. Make sure lookups cover everything in this file ----------
                # Unknown province codes are inserted with a NULL region rather than
                # failing the foreign key, so an unexpected code cannot break the
                # weekly load. They show up in the warning below so you can fix them.
                file_pvs = {r["pv"] for r in rows if r["pv"]}
                cur.execute("SELECT pv FROM ref_provincia")
                known_pvs = {r[0] for r in cur.fetchall()}
                unknown_pvs = sorted(file_pvs - known_pvs)
                if unknown_pvs:
                    print(f"  ! unknown province codes, added without a region: {unknown_pvs}")
                    cur.executemany(
                        "INSERT INTO ref_provincia (pv, provincia, regione) VALUES (%s, %s, NULL) "
                        "ON CONFLICT (pv) DO NOTHING",
                        [(pv, f"UNKNOWN ({pv})") for pv in unknown_pvs],
                    )

                # ATECO divisions are seeded straight from the data: the letter and
                # number in `attivita` agree with the numeric code in every row.
                divisions = {}
                for r in rows:
                    if r["ateco_division"]:
                        label = r["attivita_label"] or ""
                        _, _, description = clean.parse_attivita(label)
                        divisions[r["ateco_division"]] = (r["ateco_section_letter"], description)
                cur.executemany(
                    """
                    INSERT INTO ref_ateco_division (division, section_letter, label_it)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (division) DO UPDATE
                        SET section_letter = COALESCE(EXCLUDED.section_letter, ref_ateco_division.section_letter),
                            label_it       = COALESCE(EXCLUDED.label_it, ref_ateco_division.label_it)
                    """,
                    [(d, letter, label) for d, (letter, label) in sorted(divisions.items())],
                )

                # --- 4. What do we already know? ---------------------------------
                cur.execute("SELECT codice_fiscale FROM companies")
                known_companies = {r[0] for r in cur.fetchall()}

                cur.execute(
                    """
                    SELECT DISTINCT ON (codice_fiscale) codice_fiscale, content_hash
                    FROM company_snapshots
                    ORDER BY codice_fiscale, observed_on DESC, id DESC
                    """
                )
                latest_hashes = dict(cur.fetchall())

                incoming = {r["codice_fiscale"] for r in rows}
                new_companies = incoming - known_companies

                # --- 5. Upsert the company identity rows -------------------------
                # Note `is_active = TRUE` and `delisted_on = NULL` on conflict: a
                # company that vanished and later came back is correctly revived.
                cur.executemany(
                    """
                    INSERT INTO companies (codice_fiscale, latest_denominazione,
                                           first_seen_import_id, last_seen_import_id,
                                           first_seen_on, last_seen_on)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (codice_fiscale) DO UPDATE SET
                        latest_denominazione = EXCLUDED.latest_denominazione,
                        last_seen_import_id  = EXCLUDED.last_seen_import_id,
                        last_seen_on         = GREATEST(companies.last_seen_on, EXCLUDED.last_seen_on),
                        is_active            = TRUE,
                        delisted_on          = NULL,
                        updated_at           = now()
                    """,
                    [
                        (r["codice_fiscale"], r["denominazione"], import_id, import_id,
                         observed_on, observed_on)
                        for r in rows
                    ],
                )
                print(f"Companies : {len(rows)} seen, {len(new_companies)} new")

                # --- 6. Insert snapshots, but only where something changed -------
                to_insert = [
                    r for r in rows
                    if latest_hashes.get(r["codice_fiscale"]) != r["content_hash"]
                ]
                unchanged = len(rows) - len(to_insert)

                if to_insert:
                    placeholders = ", ".join(["%s"] * len(SNAPSHOT_COLUMNS))
                    cur.executemany(
                        f"INSERT INTO company_snapshots ({', '.join(SNAPSHOT_COLUMNS)}) "
                        f"VALUES ({placeholders}) "
                        f"ON CONFLICT (codice_fiscale, import_id) DO NOTHING",
                        [
                            tuple(
                                Json(r["raw_record"]) if col == "raw_record"
                                else import_id if col == "import_id"
                                else observed_on if col == "observed_on"
                                else r[col]
                                for col in SNAPSHOT_COLUMNS
                            )
                            for r in to_insert
                        ],
                    )
                print(f"Snapshots : {len(to_insert)} written, {unchanged} unchanged (no row needed)")

                # --- 7. Delisting ------------------------------------------------
                delisted = 0
                if not args.no_delist:
                    cur.execute(
                        """
                        UPDATE companies
                           SET is_active   = FALSE,
                               delisted_on = %s,
                               updated_at  = now()
                         WHERE is_active
                           AND last_seen_import_id IS DISTINCT FROM %s
                        """,
                        (observed_on, import_id),
                    )
                    delisted = cur.rowcount
                    print(f"Delisted  : {delisted} companies absent from this file")
                else:
                    print("Delisted  : skipped (--no-delist)")

                # --- 8. Close the import record ----------------------------------
                cur.execute(
                    """
                    UPDATE imports
                       SET snapshots_inserted = %s, companies_new = %s,
                           companies_delisted = %s, completed_at = now()
                     WHERE id = %s
                    """,
                    (len(to_insert), len(new_companies), delisted, import_id),
                )

            if args.dry_run:
                raise _DryRunRollback
            conn.commit()
            print("\nDone. Try:  SELECT count(*) FROM companies_current WHERE is_active;")
    except _DryRunRollback:
        print("\nDRY RUN — everything above was rolled back, nothing was saved.")


if __name__ == "__main__":
    sys.exit(main())
