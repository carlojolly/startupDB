# Backlog — executable specs

Each item is written so that an engineer or coding agent with no memory of
this project can do it without further design work: why, exactly what, which
files, how to know it is done, and the command that proves it. Items are in
recommended order. Sources: the 2026-09-18 audit (`docs/audit/`), the ADRs,
and the owner's constraint that **nothing at runtime calls a model**
(ADR 0005).

Legend — **DB**: needs the shared database (run from an IPv6-capable network or
with the Session-pooler URI). **Offline**: provable with `pytest` / `npm` only.

---

## Operator checklist (no code; do these first)

These are one-off checks the audit could not run because the database was
unreachable. Each is a copy-paste command.

**O1. Which tag runs exist, and is a stub above run 17?** (audit R3)
```sql
SELECT id, model, prompt_version, companies_tagged, finished_at
FROM tag_runs ORDER BY finished_at DESC NULLS LAST;
```
Anything with `DRY RUN STUB` in `model`, or fewer than 9,620 companies and a
newer `finished_at` than run 17, is what the old view rule was showing.

**O2. Apply migration 007 and pin the run.**
```bash
python scripts/init_db.py            # applies sql/007 (seeds the pointer, changes nothing on screen)
python scripts/publish_run.py        # shows what is pinned
python scripts/publish_run.py --run-id 17
```

**O3. RLS and the Data API** (audit R1). In Supabase: Project Settings → Data
API → is `public` exposed? Then:
```sql
SELECT relname, relrowsecurity FROM pg_class
WHERE relnamespace = 'public'::regnamespace AND relkind = 'r';
```
If any `relrowsecurity` is `false` and the Data API is on, run
`ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;` for every table, with no
policies. The dashboard and scripts connect as the owner role over direct
Postgres and are unaffected.

**O4. Backups** (audit R2). Database → Backups: is there any? If on the free
tier there is not. Regardless: keep every weekly raw CSV somewhere off this
laptop and run `pg_dump` weekly (item B10 automates it).

**O5. Live schema matches migrations** (audit R4): `\d company_tags`,
`\dx` (expect `pg_trgm`), `\di *trgm*`.

---

## B1. Read-only database role for the dashboard — DB, small

**Why.** The dashboard connects as the owner role, so any bug in a server
component could write (ADR 0004). This is the cheapest structural fix and
should precede sharing any URL.

**What.**
1. New `sql/008_dashboard_role.sql`, idempotent:
   ```sql
   DO $$ BEGIN
     IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'venture_reader') THEN
       CREATE ROLE venture_reader LOGIN PASSWORD 'CHANGE-ME-AFTER-APPLY';
     END IF;
   END $$;
   GRANT USAGE ON SCHEMA public TO venture_reader;
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO venture_reader;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO venture_reader;
   ```
   Document in the file header that the operator changes the password after
   applying (`ALTER ROLE venture_reader PASSWORD '...'`) and never commits it.
2. `web/lib/db.ts`: read `DASHBOARD_DATABASE_URL` first, fall back to
   `DATABASE_URL` with a one-line `console.warn` in non-production that the
   dashboard is using the owner role. Add the variable to `.env.example`.
3. README "Deploying it": set `DASHBOARD_DATABASE_URL` on the host.

**Done when.** With `DASHBOARD_DATABASE_URL` set to the reader role, the
dashboard renders every page and `INSERT INTO tag_runs DEFAULT VALUES` from
that role fails with `permission denied`.

**Verify.** `cd web && npm run lint && npx tsc --noEmit && npm run build`;
then the two manual checks above.

---

## B2. Make append-only structural — DB, small

**Why.** ADR 0002 is enforced only by review. One trigger makes it a database
guarantee.

**What.** `sql/009_snapshots_immutable.sql`:
```sql
CREATE OR REPLACE FUNCTION refuse_snapshot_mutation() RETURNS trigger AS $$
BEGIN
  IF current_setting('startup_map.allow_snapshot_repair', true) = 'on' THEN
    RETURN COALESCE(NEW, OLD);
  END IF;
  RAISE EXCEPTION 'company_snapshots is append-only (ADR 0002); set startup_map.allow_snapshot_repair = on inside a --force repair transaction';
END $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS snapshots_immutable ON company_snapshots;
CREATE TRIGGER snapshots_immutable BEFORE UPDATE OR DELETE ON company_snapshots
FOR EACH ROW EXECUTE FUNCTION refuse_snapshot_mutation();
```
In `scripts/import_csv.py`, the `--force` path runs
`SET LOCAL startup_map.allow_snapshot_repair = on` at the top of its
transaction (search for the existing `DELETE FROM company_snapshots`).

**Done when.** A plain `DELETE FROM company_snapshots WHERE id = 1` raises;
`import_csv.py --force` on the latest import still succeeds.

**Verify.** Needs Postgres; add the two cases to the fixture in B3.

---

## B3. Ingestion tests against a real Postgres — DB (local), medium

**Why.** Zero tests execute `import_csv.py` end-to-end or any SQL (audit A10).
The three import guards are unit-tested, but nothing would catch removal of
their call sites. This is the single most valuable test investment.

**What.**
1. Add `testcontainers[postgres]>=4` under "Development" in
   `requirements.txt`. Tests skip (not fail) when Docker is absent.
2. `tests/conftest.py`: a session fixture `pg_url` that starts
   `postgres:16`, runs every `sql/*.sql` in order through
   `scripts/init_db.py`'s apply function (refactor it into
   `apply_migrations(conn)` if it is only a `main()` today), and yields the
   URL. A function fixture `db` truncates every table between tests.
3. `tests/test_import_end_to_end.py`, each test driving
   `import_csv.main()` (it reads `sys.argv`; set it with `monkeypatch.setattr(sys, "argv", [...])`
   or give `main` an optional `argv` parameter) with `DATABASE_URL` pointed at
   the container and a synthetic CSV written with the **real header names**
   (copy the header block from `tests/test_import_csv.py`). Ten tests, in
   this order:

   | # | Test | Assert |
   |---|---|---|
   | 1 | First import of 3 companies | 3 `companies`, 3 `company_snapshots`, 1 `imports` row with `companies_new = 3` |
   | 2 | Same file again | refused before writing (`file_sha256` UNIQUE); counts unchanged |
   | 3 | Same content, new file name, `--as-of` later | 0 new snapshots; `imports` row written with `snapshots_written = 0` |
   | 4 | One company's `comune` changes | exactly 1 new snapshot; `company_change_log` shows `prev_comune` |
   | 5 | Leading-zero CF `00123456789` | round-trips as the same 11-char string from `companies_current` |
   | 6 | Company absent from the next file | `is_active = false`, `delisted_on` set; present again later → `is_active = true` |
   | 7 | 74% of companies absent | import refused, nothing written; `--allow-mass-delist` writes it |
   | 8 | One unparseable date | refused; `--allow-unparsed-dates` writes and `imports.notes` records the count |
   | 9 | 50% of companies change ATECO | refused; `--allow-ateco-reclassification` writes |
   | 10 | Exception injected after snapshots are written (monkeypatch the delist step to raise) | no `imports` row, no snapshots: the transaction rolled back |

**Done when.** `pytest tests/test_import_end_to_end.py` passes with Docker
running and reports `skipped` without it.

**Verify.** `.venv/bin/python -m pytest -q tests/test_import_end_to_end.py`.

---

## B4. Per-import membership table — DB, medium (schema change: get approval)

**Why.** Snapshot-on-change cannot answer "who was listed in week N" or see a
delist-then-relist (ADR 0002 consequences; audit A1). This is the history the
project exists to keep.

**What.**
1. `sql/010_import_companies.sql`:
   ```sql
   CREATE TABLE IF NOT EXISTS import_companies (
     import_id      BIGINT   NOT NULL REFERENCES imports(id),
     codice_fiscale CHAR(11) NOT NULL REFERENCES companies(codice_fiscale),
     PRIMARY KEY (import_id, codice_fiscale)
   );
   ```
2. `import_csv.py`: after the companies upsert, one `executemany` inserting
   every valid CF of the file (~11.5k rows/week) inside the existing
   transaction. `--dry-run` rolls it back like everything else.
3. A view `company_presence(codice_fiscale, import_id, observed_on)` joining
   `imports`, and a README example: "companies present on 2026-08-30 but not
   on 2026-09-06".
4. Backfill: none is possible for imports whose CSV is gone; note that in the
   migration header.

**Done when.** B3's fixture gets an 11th test: two imports, one company
absent from the second → `import_companies` has 3 + 2 rows.

---

## B5. One definition of "current run" — Offline, small

**Why.** The dashboard reads `published_run`; `scripts/export_tags.py` still
uses `max(id)` (ADR 0003).

**What.** In `export_tags.py`, when `--run-id` is absent, read
`SELECT run_id FROM published_run WHERE id = 1` and print which run is being
exported; exit with a message if the table is missing ("run init_db.py").
Update the README line under "Runs are versioned".

**Verify.** Unit test with a mocked cursor returning a `published_run` row;
`pytest -q`.

---

## B6. Verify the database TLS certificate — DB, small

**Why.** Both sides encrypt but do not verify (audit C.1-#5); on public
Wi-Fi the credential can be captured.

**What.** Download the Supabase CA (`prod-ca-2021.crt`, from Project
Settings → Database → SSL) into `certs/supabase-ca.crt` (commit it; it is
public). Python: append `?sslmode=verify-full&sslrootcert=certs/supabase-ca.crt`
in `.env.example` and README. `web/lib/db.ts`: replace
`ssl: { rejectUnauthorized: false }` with
`ssl: { ca: fs.readFileSync(path.join(process.cwd(), "..", "certs/supabase-ca.crt"), "utf8") }`,
with a `DATABASE_SSL_CA` env override for hosts where the relative path does
not exist.

**Done when.** Both halves connect with verification on, and a deliberately
wrong CA file makes both fail.

---

## B7. Company timeline on the detail page — Offline for the UI, DB to see data; small

**Why.** The change log view is queried by nobody; the history is the
product's differentiator (ADR 0002). No model call needed (ADR 0005).

**What.**
1. `web/lib/companies.ts`: `getTimeline(cf)` selecting from
   `company_change_log` for one CF, oldest first, plus `first_seen_on`,
   `delisted_on`, `is_active` from `companies_current`.
2. `web/components/timeline.tsx`: a vertical list; one entry per snapshot
   with the fields whose `prev_*` differs, labels from the `ref_*` values
   already in `companies_current` (add the band labels to the change-log
   query with the same `LEFT JOIN ref_*` pattern as `companies_current`).
   Entries: "First seen", "Name changed", "Moved from X to Y", "Revenue band
   A → C", "Website changed", "Delisted", "Back in the registry".
3. Render under the tags on `web/app/company/[cf]/page.tsx`. With one
   snapshot, show a single "First seen" entry, not an empty section.

**Done when.** A company with two snapshots shows two dated entries; lint,
tsc, build pass; `tests/test_dashboard.py` gets one test asserting the
"First seen" text on a known company page.

---

## B8. Status-expiry clock — Offline for logic, DB to see data; small

**Why.** Innovative-startup status lasts five years from
`data_iscrizione_sezione_startup`, which every row carries. "Who leaves the
registry next" is the most domain-specific fact the data can state, and it
needs no model.

**What.**
1. `sql/011_expiry.sql`: `CREATE OR REPLACE VIEW companies_current` is
   defined in `003` and already applied, so **do not edit 003**; add
   `status_ends_on` as a new view `companies_current_ext` selecting
   `companies_current.*, (data_iscrizione_sezione_startup + INTERVAL '5 years')::date AS status_ends_on`,
   and switch `web/lib/companies.ts` to it. Exclude
   `days_in_startup_section < 0` (the ~327 re-registrations) from any
   "expiring" predicate.
2. Filter `expires=6m|12m|past` in `web/lib/search-params.ts` (round-trips
   like the others), a predicate in `conditions()`, a chip on the row when
   `status_ends_on` is within 12 months, and one masthead count
   ("N leave the registry within a year").
3. Unit test in TypeScript is not set up; test the URL round-trip in
   `tests/test_dashboard.py` and the SQL predicate against B3's fixture if
   present, else document as DB-verified.

**Done when.** `?expires=6m` returns only companies whose `status_ends_on` is
between today and +6 months and whose section age is non-negative.

---

## B9. Materialise the published run — DB, medium (do only when lists get slow)

**Why.** Every list query pivots ~9,620 × ~9 EAV rows before filtering
(ADR 0003, audit R5). Measure first: `EXPLAIN (ANALYZE, BUFFERS)` on the
`searchCompanies` SQL; if under ~150 ms, skip this item.

**What.** `publish_run.py` also refreshes a `company_tags_current` table
(one row per company: `parent_sectors text[]`, `product_types text[]`,
`customer_models text[]`, `sector`, `one_line`, `vc_relevance`,
`vc_reason`, `fetch_bucket`, `fetch_pass`, `homepage_chars`) with GIN
indexes on the arrays, inside the same transaction as the pointer move.
`companies.ts` reads the table; the view stays for ad-hoc SQL.

---

## B10. Weekly backup and CSV archive — Offline, small

**Why.** Audit R2: possibly no backup of the only copy of the history.

**What.** `scripts/backup.py`: runs `pg_dump --format=custom` of
`DATABASE_URL` to `backups/startup_map_<date>.dump` and copies any new
`data/raw/*.csv` alongside; prints sizes; exits non-zero on failure. README
section "Backups" with a one-line cron example. Requires `pg_dump` on PATH;
say so in the error when missing.

---

## B11. Concurrent-import lock — DB, tiny

**Why.** Two different files imported at once can both write a snapshot for
the same unchanged content (audit D.a.5).

**What.** First statement inside the import transaction:
`SELECT pg_advisory_xact_lock(hashtext('startup_map_import'));`. Add to the
README's description of the transaction.

---

## B12. Larger ground truth for the tags — human work, model optional

**Why.** Accuracy is measured on 40 companies (±14 points), and `sector` and
VC relevance have no ground truth at all. Nothing about model or prompt
choice can be decided at this precision.

**What.** Hand-label the committed 200-company sample
(`data/sample_200_2026-09-06.csv`) with the four closed fields, into
`data/sample_200_labels_<date>.csv` using the dev-set label file's columns.
A model may draft the labels once to speed this up (one-off, not runtime),
but every row is reviewed by a person. Then `scripts/eval_prompt.py` gains
`--labels PATH` so either set can be scored.

**Done when.** `eval_prompt.py --labels data/sample_200_labels_*.csv`
prints per-field accuracy with n=200.

---

## Not planned

- Natural-language search, on-demand company dossiers, narrative weekly
  digests: each needs a model call per request or per week. Out of scope
  under ADR 0005 unless it is superseded.
- Multi-country support: requires the surrogate-key change described in
  ADR 0001; not started.
- Authentication: host-level protection is the documented interim; an OIDC
  middleware is the path if the app itself must know who the viewer is.
