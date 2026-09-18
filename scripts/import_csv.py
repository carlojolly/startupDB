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

# The four date columns. A value that is present but does not parse is counted
# and, by default, blocks the import: a silent NULL would change every content
# hash and write a false snapshot for every company in the file.
DATE_FIELDS = (
    "data_iscrizione_sezione_startup", "data_iscrizione_registro_imprese",
    "data_inizio_attivita", "data_dichiarazione",
)

# A normal week delists a few dozen of ~11,500 companies (they age out of the
# five-year window). Anything approaching this share means the file is
# truncated or partial, not that hundreds of companies left the registry.
MAX_DELIST_SHARE = 0.05

# ATECO 2025 replaced ATECO 2007 and existing firms were reclassified by the
# chambers of commerce. A week in which this share of companies change code is
# the coding scheme changing, not the companies.
MAX_ATECO_CHANGE_SHARE = 0.10


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
            for field in DATE_FIELDS:
                raw_value = (raw_row.get(columns[field]) or "").strip()
                if raw_value and row[field] is None:
                    stats["unparsed_dates"] += 1
                    if stats["unparsed_dates"] <= 5:
                        print(f"  ! unparseable date in {field} for {cf}: {raw_value!r}")
            row["codice_fiscale"] = cf
            row["content_hash"] = clean.content_hash(row)
            # Store the original verbatim, minus empty cells, as an escape hatch.
            row["raw_record"] = {k: v for k, v in raw_row.items() if (v or "").strip()}
            cleaned_rows.append(row)
            stats["rows_valid"] += 1

    return cleaned_rows, stats, columns


def check_unparsed_dates(count: int, allow: bool) -> None:
    """Refuse to import a file whose dates stopped parsing.

    If the registry changes its date format, every date in the file would
    otherwise become NULL, every content hash would change, and one week
    would write a false snapshot for every company — rows that the
    append-only rule then forbids removing.
    """
    if count and not allow:
        raise SystemExit(
            f"\nREFUSING TO IMPORT: {count} date value(s) could not be parsed as "
            f"dd/mm/yyyy.\nIf the registry changed its date format, fix "
            f"clean.parse_date first. To load the file anyway with those dates "
            f"stored as NULL, re-run with --allow-unparsed-dates."
        )


def check_delist_share(would_delist: int, active_total: int, allow: bool) -> None:
    """Refuse to mark an implausible share of active companies inactive.

    Delisting is reversible — a company that reappears is revived — but a
    truncated file would still flip `is_active` for thousands of rows and
    overwrite their `delisted_on` history in one transaction.
    """
    if not would_delist or allow or not active_total:
        return
    share = would_delist / active_total
    if share > MAX_DELIST_SHARE:
        raise SystemExit(
            f"\nREFUSING TO IMPORT: this file would delist {would_delist:,} of "
            f"{active_total:,} active companies ({share:.1%}), above the "
            f"{MAX_DELIST_SHARE:.0%} safety limit.\nThat usually means the export "
            f"is truncated or partial. Check the row count against last week's, "
            f"and if the delisting is genuine re-run with --allow-mass-delist."
        )


def check_ateco_change_share(changed: int, compared: int, allow: bool) -> None:
    """Refuse a file in which an implausible share of companies changed ATECO code.

    The content hash cannot tell a reclassification of the coding scheme from
    a company changing its activity. Stopping here lets a human record the
    reclassification (the override is written to imports.notes) instead of it
    being read later as thousands of businesses changing in one week.
    """
    if not changed or allow or not compared:
        return
    share = changed / compared
    if share > MAX_ATECO_CHANGE_SHARE:
        raise SystemExit(
            f"\nREFUSING TO IMPORT: {changed:,} of {compared:,} previously seen "
            f"companies ({share:.1%}) carry a different ATECO code than their last "
            f"snapshot, above the {MAX_ATECO_CHANGE_SHARE:.0%} limit.\nThat looks like "
            f"a reclassification of the coding scheme (e.g. ATECO 2007 -> 2025) rather "
            f"than the companies changing. If so, re-run with "
            f"--allow-ateco-reclassification; the import will record it."
        )


def data_vintage(rows: list[dict]) -> datetime.date | None:
    """The newest registration date in the file — the data's own vintage.

    This is a far better `observed_on` than the file's mtime. The registry
    export lags: a file downloaded on 30 August contained data only up to
    14 August. mtime is also fragile — it records when the file was last
    written to disk, so unzipping it, or copying it into data/raw/, resets it
    to the time of that operation rather than anything about the data.
    """
    dates = [r["data_iscrizione_sezione_startup"] for r in rows
             if r.get("data_iscrizione_sezione_startup")]
    return max(dates) if dates else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("csv_path", type=pathlib.Path, help="Path to the registry CSV")
    parser.add_argument("--database-url", help="Override DATABASE_URL from .env")
    parser.add_argument(
        "--as-of",
        help="Date this snapshot represents (YYYY-MM-DD). Defaults to the "
             "newest registration date in the file, then to the file's "
             "modification date.",
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
        "--allow-unparsed-dates", action="store_true",
        help="Load the file even if some date values do not parse (they are "
             "stored as NULL). By default that refuses the import.",
    )
    parser.add_argument(
        "--allow-mass-delist", action="store_true",
        help=f"Permit delisting more than {MAX_DELIST_SHARE:.0%} of active "
             "companies in one import. By default that refuses the import, "
             "because it almost always means a truncated file.",
    )
    parser.add_argument(
        "--allow-ateco-reclassification", action="store_true",
        help=f"Permit more than {MAX_ATECO_CHANGE_SHARE:.0%} of companies to change "
             "ATECO code in one import, and record on the import that a "
             "reclassification was accepted. By default that refuses the import.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-import a file already loaded by replacing that import in "
             "place: its snapshots are deleted and rewritten under the same "
             "import id. Only the most recent import can be replaced. Repair "
             "tool — not routine.",
    )
    args = parser.parse_args()

    path: pathlib.Path = args.csv_path
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    print(f"File      : {path}")
    print("Fingerprinting ...", end=" ", flush=True)
    file_hash = sha256_of_file(path)
    print(file_hash[:16] + "...")

    print("Reading CSV ...")
    rows, stats, columns = read_and_clean(path)

    # Prefer the data's own vintage over any filesystem timestamp.
    vintage = data_vintage(rows)
    if args.as_of:
        observed_on, source = datetime.date.fromisoformat(args.as_of), "--as-of"
    elif vintage:
        observed_on, source = vintage, "newest registration date in the file"
    else:
        observed_on, source = datetime.date.fromtimestamp(path.stat().st_mtime), "file mtime"
    mtime_date = datetime.date.fromtimestamp(path.stat().st_mtime)
    print(f"As of     : {observed_on}  ({source})")
    if vintage and not args.as_of:
        print(f"            file was last written {mtime_date}, "
              f"so the export lags by {(mtime_date - vintage).days} days")
    print(f"  {stats['rows_in_file']} rows in file, {stats['rows_valid']} valid companies")
    if stats["skipped_blank"]:
        print(f"  {stats['skipped_blank']} blank rows skipped (spreadsheet padding)")
    if stats["skipped_bad_cf"]:
        print(f"  {stats['skipped_bad_cf']} rows skipped: malformed codice fiscale")
    if stats["skipped_duplicate_in_file"]:
        print(f"  {stats['skipped_duplicate_in_file']} rows skipped: duplicate codice fiscale")
    if stats["unparsed_dates"]:
        print(f"  {stats['unparsed_dates']} date values could not be parsed")
    check_unparsed_dates(stats["unparsed_dates"], args.allow_unparsed_dates)
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
                import_id = None
                if existing and args.force:
                    # The imports row cannot be deleted: companies.first_seen_import_id
                    # and last_seen_import_id reference it, so the delete would fail
                    # the foreign key. Replace the load in place instead — drop this
                    # import's snapshots and reuse its id — and only for the newest
                    # import, so the change comparison below runs against the
                    # snapshots that preceded it rather than ones taken later.
                    cur.execute("SELECT max(id) FROM imports")
                    if cur.fetchone()[0] != existing[0]:
                        raise SystemExit(
                            f"\n--force can only replace the most recent import, and "
                            f"import {existing[0]} is not the newest.\nRe-importing an "
                            "older file would compare its rows against snapshots taken "
                            "after it."
                        )
                    print(f"\n--force: replacing import {existing[0]} in place — its "
                          "snapshots are deleted and rewritten")
                    cur.execute("DELETE FROM company_snapshots WHERE import_id = %s",
                                (existing[0],))
                    import_id = existing[0]

                # --- 2b. Is this file older than what we already hold? -----------
                # Delisting marks every company absent from THIS file as inactive.
                # Running that with an older export would wrongly delist everything
                # registered since. Checked before the import row is created so a
                # refusal does not consume an id.
                cur.execute("SELECT max(observed_on) FROM company_snapshots")
                newest_held = cur.fetchone()[0]
                if newest_held and observed_on < newest_held and not args.no_delist:
                    raise SystemExit(
                        f"\nREFUSING TO IMPORT: this file's data vintage is "
                        f"{observed_on}, but the database already holds data as of "
                        f"{newest_held}.\n"
                        f"Delisting would mark every company registered since "
                        f"{observed_on} as inactive.\n"
                        f"If you meant to load an older file, re-run with --no-delist."
                    )
                if newest_held and observed_on == newest_held:
                    print(f"  note: same data vintage ({observed_on}) as data already "
                          f"held — the registry may not have refreshed since last time.")

                # --- 2. Open (or, with --force, reset) the import record ---------
                import_values = (
                    path.name, file_hash, path.stat().st_size,
                    datetime.datetime.fromtimestamp(path.stat().st_mtime,
                                                    tz=datetime.timezone.utc),
                    stats["rows_in_file"], stats["rows_valid"],
                    stats["rows_in_file"] - stats["rows_valid"], vintage,
                )
                if import_id is None:
                    cur.execute(
                        """
                        INSERT INTO imports (source_filename, file_sha256, file_size_bytes,
                                             file_modified_at, rows_in_file, rows_valid,
                                             rows_skipped, data_vintage)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        import_values,
                    )
                    import_id = cur.fetchone()[0]
                else:
                    cur.execute(
                        """
                        UPDATE imports
                           SET source_filename = %s, file_sha256 = %s, file_size_bytes = %s,
                               file_modified_at = %s, rows_in_file = %s, rows_valid = %s,
                               rows_skipped = %s, data_vintage = %s,
                               imported_at = now(), completed_at = NULL,
                               snapshots_inserted = NULL, companies_new = NULL,
                               companies_delisted = NULL, notes = NULL
                         WHERE id = %s
                        """,
                        (*import_values, import_id),
                    )
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
                    SELECT DISTINCT ON (codice_fiscale) codice_fiscale, content_hash, ateco_raw
                    FROM company_snapshots
                    ORDER BY codice_fiscale, observed_on DESC, id DESC
                    """
                )
                latest = {cf: (content_hash, ateco)
                          for cf, content_hash, ateco in cur.fetchall()}
                latest_hashes = {cf: content_hash for cf, (content_hash, _ateco) in latest.items()}

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

                # A registry-wide reclassification would look like thousands of
                # companies changing business in one week. Count it and stop
                # above the limit; the operator's override is recorded below.
                compared = sum(1 for r in rows if r["codice_fiscale"] in latest)
                ateco_changed = sum(
                    1 for r in to_insert
                    if r["codice_fiscale"] in latest
                    and latest[r["codice_fiscale"]][1] != r["ateco_raw"]
                )
                if ateco_changed:
                    print(f"  {ateco_changed} companies carry a different ATECO code "
                          f"than their last snapshot")
                check_ateco_change_share(ateco_changed, compared,
                                         args.allow_ateco_reclassification)

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
                    # Count first, inside the transaction: a refusal here rolls
                    # everything back, so nothing is half-applied.
                    cur.execute(
                        """
                        SELECT count(*) FILTER (WHERE last_seen_import_id IS DISTINCT FROM %s),
                               count(*)
                          FROM companies
                         WHERE is_active
                        """,
                        (import_id,),
                    )
                    would_delist, active_total = cur.fetchone()
                    check_delist_share(would_delist, active_total, args.allow_mass_delist)
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
                # The counts a later reader needs to reconcile this load, so a
                # silent loss is visible from the imports table alone.
                notes = (
                    f"skipped: blank={stats['skipped_blank']}, "
                    f"bad_cf={stats['skipped_bad_cf']}, "
                    f"duplicate_in_file={stats['skipped_duplicate_in_file']}; "
                    f"unparsed_dates={stats['unparsed_dates']}; "
                    f"unchanged={unchanged}; ateco_changed={ateco_changed}; "
                    f"ateco_header={columns['ateco_raw']!r}"
                )
                if args.allow_ateco_reclassification:
                    notes += "; ATECO reclassification accepted by the operator"
                if existing and args.force:
                    notes += "; re-imported with --force (companies_new counts only " \
                             "companies unseen before this re-run)"
                cur.execute(
                    """
                    UPDATE imports
                       SET snapshots_inserted = %s, companies_new = %s,
                           companies_delisted = %s, completed_at = now(),
                           notes = %s
                     WHERE id = %s
                    """,
                    (len(to_insert), len(new_companies), delisted, notes, import_id),
                )

            if args.dry_run:
                raise _DryRunRollback
            conn.commit()
            print("\nDone. Try:  SELECT count(*) FROM companies_current WHERE is_active;")
    except _DryRunRollback:
        print("\nDRY RUN — everything above was rolled back, nothing was saved.")


if __name__ == "__main__":
    sys.exit(main())
