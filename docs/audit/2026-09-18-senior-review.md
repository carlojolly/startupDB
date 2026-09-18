# VentureAtlas — senior engineer repository audit

Date: 2026-09-18 · Branch: `audit/senior-review` (created from `main` @ `1df5632`) · Mode: **read-only audit, then fixes**. The authorisation block in the audit prompt was left as `[FILL IN]`, so the audit itself changed nothing; the author then asked for the necessary fixes, which are recorded in section E, one commit each.

Every claim below is labelled with its basis:

- **read** — I opened the file and read the lines cited.
- **executed** — I ran the command and quote its real output.
- **not verified** — I could not check it; the sentence says what would.

The live database could not be reached from this machine (section A.3), so everything about the deployed schema, RLS, query plans and stored rows is **not verified** and is listed in section F with the exact check to run.

---

## A. What I inspected

### A.1 Files read in full

Python: `scripts/db.py`, `init_db.py`, `clean.py`, `import_csv.py`, `tag_companies.py`, `render.py`, `test_websites.py`, `tag_registry_batch.py`, `recover_tag_run.py`, `export_tags.py`, `score_vc_relevance.py`, `eval_batch_quality.py`, `eval_prompt.py`, `build_sample_200.py`, `probe_playwright.py`; all ten files in `tests/`.
SQL: `sql/001_schema.sql`, `003_views.sql`, `004_search_indexes.sql`, `005_tag_fetch_provenance.sql`, `006_import_data_vintage.sql`; `002_reference_data.sql` structure only (CREATE/INSERT/ON CONFLICT lines, not every VALUES row).
TypeScript: `web/lib/{db,companies,model,search-params,taxonomy}.ts`, `web/app/{layout,page,not-found}.tsx`, `web/app/company/[cf]/page.tsx`, all twelve files in `web/components/`, `web/next.config.ts`, `eslint.config.mjs`, `tsconfig.json`, `postcss.config.mjs`, `package.json`.
Docs/config: `README.md`, `web/README.md`, `docs/data-notes.md`, `docs/tagging-contract-v5.md` (v4 and prompt-v3 headings only — both are marked superseded), `.gitignore`, `web/.gitignore`, `.env.example` (variable names only), `.claude/launch.json`, `requirements.txt`.
Data (metadata only, never printed in full): the first 300 bytes and line count of `data/raw/startup_2026-08-30.csv`; headers and row counts of the committed sample/dev-set CSVs; `data/registry_batch/state.json`, `data/batch_quality/quality_gate.json`, `quality_report.txt`, the 30 batch `validated_results.json` files and 20 fetch checkpoints (aggregated programmatically).

Not read: `web/app/globals.css` (style only), the two PNG wordmarks, `web/package-lock.json` beyond its header, `.env` (only checked that its two variables have non-empty values, and derived the host *type* without printing the URL).

### A.2 Commands run and real output (condensed)

| Check | Command | Result (executed) |
|---|---|---|
| Python tests | `.venv/bin/python -m pytest -q` | `91 passed, 24 skipped, 1 warning in 2.50s` (24 skipped = `tests/test_dashboard.py`, needs a dev server on :3000) |
| Python tests on a fresh clone | `git clone . <scratch>/fresh-clone && pytest -q` | `1 failed, 89 passed, 25 skipped` — `tests/test_registry_batch.py::test_registry_pool_is_clean_complete_and_stably_ordered` raises `FileNotFoundError` for the git-ignored `data/raw/startup_2026-08-30.csv` |
| Lint | `cd web && npm run lint` | exit 0, no output |
| Types | `cd web && npx tsc --noEmit` | exit 0, no output |
| Build | `cd web && npm run build` | `✓ Compiled successfully`, routes `/` and `/company/[cf]` dynamic (ƒ), `/_not-found` static |
| npm vulnerabilities | `npm audit` | `found 0 vulnerabilities` |
| Python vulnerabilities | `uvx pip-audit -r <pip freeze of .venv> --no-deps` | `No known vulnerabilities found` (nothing installed into the project) |
| Secrets in tree | grep for `postgres://…:…@`, `sk-…`, `eyJ…` | 0 keys/tokens; the only 2 credential-shaped strings are the README's placeholder connection strings |
| Secrets in history | same patterns over `git log -p --all`; `git log --all -- .env` | 0 keys/tokens; `.env` has never been committed |
| Toolchain | `python --version`, `node --version` | Python 3.14.4 (venv), Node v24.15.0, npm 11.12.1 |
| DB reachability | `scripts/db.connect()` | **failed**: `could not connect … failed to resolve host 'db.<ref>.supabase.co'`. This machine has 0 global IPv6 addresses; `getaddrinfo` returns neither A nor AAAA for that host. The README already documents this hostname as IPv6-only. |
| Registry metadata | `npm view …`, PyPI JSON for each `requirements.txt` package | every package exists under its exact name from its expected publisher; last publish dates 2026-04 → 2026-09 (details in C.2/R-deps) |

### A.3 What I could not access

- **The live Postgres** (Supabase, direct host, port 5432 — the `.env` uses the direct `db.<ref>.supabase.co` form, not the pooler). No schema/RLS/row/plan checks were possible. A read-only inventory script (`db_inventory.py`, sent alongside this report; SELECT-only, sets `conn.read_only = True`) will produce all of them when run from an IPv6-capable network or after switching `DATABASE_URL` to the Session pooler URI.
- The Supabase dashboard (RLS, Data API exposure, backups, plan).
- Any deployment (Vercel or otherwise) and its environment variables. No `.vercel` directory or CI workflow exists in the repo.
- The dashboard at runtime (`tests/test_dashboard.py` needs both the dev server and the database).

### A.4 Reconnaissance summary (section 3 of the brief)

1. **Repo shape (read).** Python scripts in `scripts/` (flat modules, imported by `sys.path` insertion, no package), tests in `tests/`, SQL in `sql/`, Next.js app in `web/`. Manifests: `requirements.txt` (floor pins, `>=`, no lockfile), `web/package.json` + `package-lock.json` (lockfile v3; `next 16.3.5`, `react 19.2.8` exact, others `^`). No `pyproject.toml`, no `.python-version`, no `.nvmrc`. README says Python 3.10+ (wrong, see C.1-#11).
2. **Documentation (read).** README (613 lines), `web/README.md`, `docs/data-notes.md` (measured data profile — excellent), tagging contracts v4/v5.1, prompt v3. No `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING`, ADRs. Doc/code disagreements: Python version; `--dry-run` "no cost" implies no write but it writes (C.1-#1); README project layout lists 8 of 15 scripts and only `tests/test_clean.py`; "pinned to run 17" is not a pin (C.1-#6); "91 tests, none need a database" — one needs a git-ignored file.
3. **Schema (read from migrations; live DB not verified).** Inventory in A.5.
4. **Ingestion trace (read).** `scripts/import_csv.py`: SHA-256 of raw bytes → `csv.DictReader` (utf-8-sig, comma) → `clean.resolve_columns` (header aliasing) → per-row: strip CF, validate `^[0-9]{11}$`, in-file dedupe, `clean.clean_row`, `content_hash` → data vintage = max section-registration date → `with connect() as conn:` (**one transaction opens here, line 195**) → duplicate-file check → vintage-ordering guard → `INSERT imports` → seed `ref_provincia` unknowns and `ref_ateco_division` → read known companies + latest hashes → upsert `companies` → insert changed snapshots → delist absent → `UPDATE imports … completed_at` → **`conn.commit()` line 387**; `--dry-run` raises `_DryRunRollback` inside the block so psycopg rolls back. Every write is inside that one transaction.
5. **Enrichment trace (read).** `tag_registry_batch.py prepare` → `build_sample_200.eligible_companies` (9,620 rows with a URL surviving `clean_website`) → `tag_companies.fetch_all` (pass 1 httpx via `test_websites.check_one`; pass 2 Playwright via `render.render_many` for <500-char pages; pass 3 up to 3 same-site follow-up pages for compact sites) → JSON checkpoints of 500 → `submit`: canonical request bodies from `eval_batch_quality.request_body` (system prompt + user message, strict JSON schema from the Pydantic model) uploaded as OpenAI Batch jobs in parts of 400/200 → `check`: outputs parsed with `CompanyTags.model_validate_json` / `VCRelevance`; invalid ones get one corrective batch; DEAD pages never reach the model and get the deterministic `unclear` result → all 9,620 validated → `write_database`: one transaction, `tag_runs` row + ~9 `company_tags` rows per company (evidence string = URL, char count, bucket, pass). `recover_tag_run.py` then copies a base run into a new run and replaces only re-fetched improvements (run 17 per README, from base run 14 per `state.json`).
6. **Dashboard data access (read).** All queries live in `web/lib/companies.ts` (guarded by `import "server-only"`), called only from the two server components `web/app/page.tsx` and `web/app/company/[cf]/page.tsx`. No route handlers, no API routes, no server actions. Seven client components (`sort-select`, `search-field`, `active-filters`, `mobile-filters`, `filter-panel`, `pending`, `query-nav`) import only `lib/taxonomy`, `lib/model`, `lib/search-params` — pure modules with no env or DB access. `process.env` is read only in `web/lib/db.ts`; there is no `NEXT_PUBLIC_*` variable anywhere.
7. **Tests (executed + read).** 91 offline unit tests + 24 skipped HTTP tests. Coverage is strong for `clean.py` scalar cleaners, homepage extraction/redirect rules and the tagging output contract; **zero tests exercise `import_csv.py` or any SQL** (section C.1-#12 and 16-analysis in C.3-A10).
8. **CI/automation (read).** None: no `.github/`, no pre-commit, no linters/type-checkers configured for Python, `.git/hooks` are the samples. eslint + tsc exist for the web app and pass.
9. **Configuration/secrets (read).** `DATABASE_URL` read in `scripts/db.py:25-26` and `web/lib/db.ts:10-13` (the latter loads the *whole* root `.env` into the Node process via `dotenv`, so `OPENAI_API_KEY` is also present in the dashboard process locally — server-side only, never bundled). `OPENAI_API_KEY` read in `tag_companies.py:46-47`, `tag_registry_batch.py:711-712`, `eval_batch_quality.py:541-542`. Nothing reaches the browser.

### A.5 Schema inventory (from `sql/001` + `005` + `006`; live DB not verified)

| Table | Key / uniqueness | Notable columns & constraints | FKs (ON DELETE) | Indexes |
|---|---|---|---|---|
| `imports` | `id BIGSERIAL PK`; `file_sha256 CHAR(64) NOT NULL UNIQUE` | `imported_at/completed_at/file_modified_at TIMESTAMPTZ`; counts `rows_in_file, rows_valid, rows_skipped, snapshots_inserted, companies_new, companies_delisted INTEGER` (nullable); `data_vintage DATE` (006); `notes TEXT` | — | PK, unique |
| `companies` | `codice_fiscale CHAR(11) PK` + `CHECK (~ '^[0-9]{11}$')` | `latest_denominazione TEXT`, `first/last_seen_on DATE NOT NULL`, `is_active BOOL NOT NULL DEFAULT TRUE`, `delisted_on DATE`, `created_at/updated_at TIMESTAMPTZ NOT NULL` | `first_seen_import_id`, `last_seen_import_id` → `imports(id)` (**no action**) | `is_active`, `last_seen_on DESC`, `latest_denominazione` B-tree (004), trigram GIN (004, if `pg_trgm`) |
| `company_snapshots` | `id BIGSERIAL PK`; `UNIQUE (codice_fiscale, import_id)` | `content_hash CHAR(64) NOT NULL`, `observed_on DATE NOT NULL`; all business columns nullable except `in_liquidazione`, three `req_*` (BOOL NOT NULL DEFAULT FALSE), `raw_record JSONB NOT NULL`; identifiers are text (`pv CHAR(2)`, `ateco_raw TEXT`, `ateco_division CHAR(2)`); `classe_capitale SMALLINT` (a 1–11 band code, not an identifier) | `codice_fiscale` → `companies` (**no action**), `import_id` → `imports` (no action), `pv`, `ateco_division`, `classe_produzione`, `classe_addetti`, `classe_capitale`, three `prevalenza_*` → ref tables (no action) | `(codice_fiscale, observed_on DESC)`, `import_id`, `pv`, `ateco_division`, `data_iscrizione_sezione_startup DESC`, `sito_internet_domain`, trigram GIN on `denominazione` and `comune` (004) |
| `tag_runs` | `id PK` | `model TEXT NOT NULL`, `prompt_version TEXT`, `started_at TIMESTAMPTZ NOT NULL`, `finished_at TIMESTAMPTZ`, `companies_tagged INTEGER`, `notes TEXT` | — | PK |
| `company_tags` | `id PK`; `UNIQUE (codice_fiscale, run_id, tag_type, tag_value)` | `tag_type/tag_value TEXT NOT NULL` (**no CHECK — vocabulary enforced only in Python**), `confidence NUMERIC(3,2) CHECK 0..1` (always NULL in practice), `evidence TEXT`, `source CHECK IN ('llm','manual','rule')`, `fetch_pass CHECK IN ('http','browser','none') OR NULL` (005), `fetch_bucket TEXT` (**no CHECK**), `homepage_chars INTEGER` | `codice_fiscale` → `companies` **ON DELETE CASCADE**, `run_id` → `tag_runs` **ON DELETE CASCADE** | `codice_fiscale`, `(tag_type, tag_value)`, `run_id`, `fetch_pass` |
| `ref_classe_produzione`, `ref_classe_addetti`, `ref_classe_capitale`, `ref_prevalenza`, `ref_provincia`, `ref_ateco_division` | natural-key PKs | integer/`NUMERIC` bounds, labels; `ref_provincia.regione` nullable (unknown codes are inserted with NULL region by the importer) | — | PK |

Views (003): `companies_current` (LATERAL latest snapshot per company, decoded), `company_change_log` (LAG over 6 columns — **not ATECO**), `current_company_tags` (`run_id = latest finished_at`), `import_history`.

Verdicts on the section-5 checklist (read): no identifier is numeric; money/counts are integer bounds, no floats; all timestamps are `TIMESTAMPTZ`; one-row-per-CF is DB-enforced (PK + CHECK); no cascade reaches `company_snapshots` (deleting a company is blocked by the snapshot FK; deleting a tag run cascades only to its tags, by design); migrations are idempotent, run in filename order, contain no DROP/ALTER TYPE/RENAME, have no rollback scripts and no migration ledger; applied files were never edited after their first commit (`git log` per file). `init_db.py` applies everything to whatever `DATABASE_URL` points at with no confirmation or environment guard (C.3-A2).

---

## B. Assumptions I made

| Assumption | Basis | Would confirm / refute |
|---|---|---|
| The production database matches the six migration files. | The README says everyone runs `init_db.py`; the files are idempotent. | Run `db_inventory.py`; compare with A.5. |
| The dashboard's current run is the recovery run written by `recover_tag_run.py` (README says run 17; `state.json` says the batch write was run 14). | Read. | `SELECT id, model, companies_tagged, finished_at FROM tag_runs ORDER BY id`. |
| Only one CSV has been imported so far (only `startup_2026-08-30.csv` is on disk). | Inference from `data/raw/`. | `SELECT * FROM import_history`. |
| Supabase's default privileges and RLS-off-for-SQL-created-tables apply to this project. | Supabase documented defaults. | RLS query in section F. |
| The registry export still carries ATECO 2007 codes (header says `ateco 2007`; ATECO 2025 has been in force since 2025). | Read from the file header. | Compare the next download's header and a sample of codes against the ISTAT 2025 tables. |
| Nobody has run `tag_companies.py --dry-run` without `--no-write` against the shared DB. | Cannot tell. | `SELECT id FROM tag_runs WHERE model LIKE '%DRY RUN%'`. |
| Deployment (if any) is on Vercel with `DATABASE_URL` pointing at a pooler host, as the README instructs. | README. | Check the host's environment variables. |

---

## C. Findings

Severity is by blast radius as the brief defines it: data integrity → security → analyst-facing correctness → reliability → performance → maintainability.

### C.1 Confirmed defects

**1. `--dry-run` of the tagging pipeline writes fabricated stub tags to the production database as a finished run.** — HIGH · basis: read
`scripts/tag_companies.py:816-817` calls `write_results(results, args.dry_run)` whenever `--no-write` is absent; `write_results` (`:639-679`) inserts a `tag_runs` row labelled `"<model> (DRY RUN STUB)"`, ~5 `company_tags` rows per company holding `stub_tags()` values (`:552-559`: `"STUB sub-sector"`, `"STUB one-line description for …"`), and sets `finished_at = now()`. Because `current_company_tags` (`sql/003_views.sql:133-137`) is "the run with the latest `finished_at`", the dashboard flips to the stub run the moment the command finishes. The README describes `--dry-run` as "whole pipeline, no API calls, no cost" and contrasts it with the non-dry command that "writes to the database", which reads as a promise of no write.
*Consequence:* synthetic rows in the research database; the analyst-facing view shows 200 companies with invented labels until a real run supersedes it (rule 4 of the brief, violated by existing code).
*Smallest safe fix:* in `main()` make `--dry-run` imply `--no-write` (`if not args.no_write and not args.dry_run:`), and make `write_results` raise if `dry_run` is true. Two lines, no behaviour lost. Then check the database for an existing stub run (section F).

**2. Delisting has no safety threshold.** — HIGH by the brief's own criterion (§8); practical impact medium because it is reversible · basis: read
`scripts/import_csv.py:355-370` marks every active company absent from the current file inactive, whatever the count. The only guard is vintage ordering (`:219-229`), which a truncated file with a plausible newest date passes. The next good import revives them (`:313-318` sets `is_active = TRUE, delisted_on = NULL`), so nothing is lost, but `delisted_on` history is overwritten and `imports.companies_delisted` is the only trace. `--dry-run` prints the count, which is the current (manual) control. The dashboard does not filter on `is_active` (`web/lib/companies.ts` has no such predicate), so it is unaffected today.
*Smallest safe fix:* before the UPDATE, `SELECT count(*) FROM companies WHERE is_active AND last_seen_import_id IS DISTINCT FROM %s`; refuse (raise `SystemExit` inside the transaction → rollback) when the count exceeds a percentage of active companies (5% would have allowed every real week so far) unless `--allow-mass-delist`; also refuse when `rows_valid` is below ~90% of the previous import's. Python only, inside the existing transaction.

**3. Unparseable dates are silently nulled, and a date-format change would rewrite history.** — MEDIUM (latent) · basis: read + executed
`scripts/clean.py:129-137` returns `None` for any non-`dd/mm/yyyy` value; `import_csv.read_and_clean` (`:72-117`) counts blank rows, bad CFs and in-file duplicates but never parse failures. All four dates are in `HASHED_FIELDS` (`clean.py:58-69`). If the registry switches to ISO dates, every row's dates become NULL, every hash changes, ~11,500 snapshots with NULL dates are written in one week and cannot be removed under the append-only rule; `data_vintage()` returns None so `observed_on` silently falls back to the file's mtime (`import_csv.py:177-180`). Today's file has 0 unparseable non-blank dates (executed). Note `resolve_columns` *does* fail loudly on a renamed column, so this only bites when the header stays and the values change.
*Smallest safe fix:* count non-blank values that fail `parse_date`, print and store the count in `imports.notes`, and refuse the import when it is non-zero unless `--allow-unparsed-dates`.

**4. Change detection cannot separate a registry-side ATECO reclassification from a company change; no ATECO scheme version is stored.** — MEDIUM · basis: read
`clean.py:58-69` hashes `ateco_raw`, `ateco_division`, `settore`, `attivita_label`; `sql/001_schema.sql:182-185` has no version column; the export's header literally reads `ateco 2007` (executed, first 300 bytes of the file). When the registry moves to ATECO 2025 codes under the same header, every reclassified company gets a snapshot that week, indistinguishable from a real change, and `company_change_log` (`sql/003_views.sql:107-126`) does not even expose the ATECO columns, so an analyst cannot see why the row exists. Attribution *is* recoverable afterwards through `import_id` on every snapshot, so this is a detection/labelling defect, not loss.
*Smallest safe fix (Python only):* record the ATECO header seen and the set of distinct codes' length profile in `imports.notes`, and refuse/warn when the header or the share of changed ATECO codes jumps (e.g. >10% of unchanged-otherwise companies). Proper fix needs approval: `ateco_version TEXT` on snapshots, and ATECO columns in `company_change_log`.

**5. Database connections are encrypted but the server certificate is not verified.** — MEDIUM-LOW (security) · basis: read
`web/lib/db.ts:36` sets `ssl: { rejectUnauthorized: false }`. The Python side's URL carries no `sslmode` (executed: query string empty), so libpq's default `prefer` applies — also encrypted, also unverified. The comment in `db.ts` that this "matches what the Python scripts already do" is therefore accurate. A network attacker positioned between a laptop and Supabase (public Wi-Fi) could impersonate the server and capture the credential and data.
*Smallest safe fix:* download the Supabase CA certificate, pass it as `ssl: { ca }` in `db.ts`, and add `?sslmode=verify-full&sslrootcert=<path>` to the Python URL (documented in `.env.example`).

**6. The dashboard shows whichever run finished last, not a chosen run.** — HIGH (analyst-facing correctness; it is also what makes #1 visible) · basis: read
`sql/003_views.sql:133-137` picks `ORDER BY finished_at DESC LIMIT 1`; `web/lib/companies.ts:31` reads only that view. Any finished run — the 200-company benchmark in `tag_companies.py`, a stub run, a recovery run — silently replaces the 9,620-company population, and the masthead count changes with it. The README's "pinned to the newest finished tag run — run 17 at the time of writing" is a description, not a pin. `export_tags.py:178` uses a *different* rule (`max(id)`), so two parts of the system can disagree on "current".
*Smallest safe fix:* an explicit pointer. Without a schema change: a `tag_runs.notes` marker is too fragile; recommend (needs approval) a one-row `published_run(run_id)` table that `current_company_tags` joins, written by hand after a run is reviewed. Interim rule: never run `tag_companies.py` against the shared DB without `--no-write`.

**7. `--force` re-import cannot succeed for any import that introduced companies.** — MEDIUM (recovery path broken) · basis: read
`scripts/import_csv.py:211-212` deletes the `imports` row, but `companies.first_seen_import_id` / `last_seen_import_id` reference `imports(id)` with no `ON DELETE` (`sql/001_schema.sql:128-129`), so Postgres raises a foreign-key violation and the transaction rolls back. The first import (all 11,542 companies point at it) and every weekly file that added a company hit this. When it does run (an import with zero new companies) it performs the codebase's only `DELETE` against `company_snapshots` (`:211`), which the README forbids.
*Smallest safe fix:* remove `--force` and print the manual procedure instead, or keep the `imports` row (mark it in `notes`) and only delete its snapshots. Either way the FK stays as it is — it did its job.

**8. Out-of-range pages render a false "no results", and paging is unstable for companies that share a name.** — LOW-MEDIUM · basis: read + executed
`web/lib/companies.ts:96-102` derives `total` from `count(*) OVER ()` on the returned rows, so `?page=999` on a non-empty result returns no rows and `total = 0`; `web/app/page.tsx:148-160` then says "No companies match these filters" and hides the pagination. Separately, every `ORDER BY` in `companies.ts:51-66` ends on `denominazione`, which is not unique: 38 names are shared by 81 companies in the current file (executed), so those rows can repeat or vanish across page boundaries.
*Smallest safe fix:* append `codice_fiscale` as the last sort key in every `ORDER BY`; when `rows` is empty and `page > 1`, show "page N is past the end" (or redirect to page 1) instead of the no-match copy.

**9. A search ending in a backslash crashes the page.** — LOW · basis: read (Postgres semantics, not executed)
`web/lib/companies.ts:70` builds `ILIKE '%' || q || '%'`. Postgres rejects a LIKE pattern that ends with the escape character (`LIKE pattern must not end with escape character`), so `?q=foo\` yields Next's generic server-error page. `%` and `_` inside `q` also act as wildcards. The value is parameterised, so there is no injection.
*Smallest safe fix:* escape `\`, `%`, `_` in `q` before interpolating.

**10. A VC-scoring API failure is stored as "Homepage unavailable" with `source = 'llm'`.** — LOW · basis: read
`scripts/score_vc_relevance.py:154-159` substitutes `unreadable_relevance()` (whose reason text says the homepage was unavailable) on any exception; `db_tag_rows` (`:250`) sets `source = 'llm'` because the bucket is not DEAD; the error goes only to the review CSV. On the `--attach-to-run-id` path an analyst then reads a rationale that contradicts the OK evidence meter beside it. The full-registry and recovery paths abort on any failure (`tag_registry_batch.py:553`, `recover_tag_run.py:229-231`), so run 14/17 are not affected.
*Smallest safe fix:* `attach_to_tag_run` refuses when any result has `error`; or store a distinct reason ("Scoring failed; not assessed").

**11. The documented Python floor is wrong; the code needs 3.11+.** — LOW · basis: read + executed grep
README says 3.10+. `datetime.UTC` (`tag_registry_batch.py:134,206,276,571,595,677`; `eval_batch_quality.py:270,492`) exists only from 3.11. `render.py:171` `except TimeoutError` catches `asyncio.wait_for` timeouts only from 3.11 (before that `asyncio.TimeoutError` is a distinct class), so on 3.10 one slow site would abort the entire render batch instead of being recorded as `total-timeout`.
*Smallest safe fix:* README + a `sys.version_info >= (3, 11)` check in `db.py`.

**12. `pytest` fails on a fresh clone.** — LOW · basis: executed
`tests/test_registry_batch.py:18-23` reads the git-ignored raw CSV unconditionally. Fresh clone: `1 failed, 89 passed, 25 skipped`. README: "none of which need a database" is true, but one needs a 2.7 MB file that is not in the repo.
*Smallest safe fix:* `pytest.mark.skipif(not build_sample_200.SOURCE.exists(), …)`, as `test_clean.py:177` already does.

**13. File mtime is stored as naive local time in a `TIMESTAMPTZ` column.** — LOW (provenance only) · basis: read
`scripts/import_csv.py:245` passes `datetime.datetime.fromtimestamp(st_mtime)` (naive, Europe/Rome) to `imports.file_modified_at`; the server interprets it in the session time zone (UTC on Supabase), so the stored value is off by one or two hours. Fix: `fromtimestamp(st_mtime, tz=datetime.timezone.utc)`.

### C.2 Plausible risks requiring verification

**R1. Every table may be readable and writable through Supabase's auto-generated REST API with the public anon key.** — HIGH impact if true
Tables created by `init_db.py` via plain SQL get Supabase's default grants (`anon`, `authenticated`, `service_role` receive privileges on new `public` tables through default privileges) and RLS is **off** unless someone turned it on. The repo never uses PostgREST and contains no anon key (executed grep), so the exposure is entirely a project-configuration question. Because the app connects as the owner role over direct Postgres, enabling RLS on all tables with no policies costs nothing and blocks the REST path completely.
*Check:* `SELECT relname, relrowsecurity FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relkind = 'r';` and `SELECT grantee, table_name, privilege_type FROM information_schema.role_table_grants WHERE table_schema = 'public' AND grantee IN ('anon','authenticated');` (both in `db_inventory.py`), plus Project Settings → Data API (exposed schemas).

**R2. There may be no backup of the only copy of the history.** — HIGH impact
Supabase's free tier does not include automated backups; the raw CSVs are git-ignored and only one exists on this disk. If the project is on the free tier and the weekly files are not archived, the snapshot history cannot be rebuilt.
*Check:* the project's plan and Database → Backups; whether every imported CSV still exists somewhere. *Mitigation regardless of plan:* archive each raw CSV (2.7 MB/week) to object storage and run `pg_dump` weekly.

**R3. A stub or 200-company run may already sit above run 17.** — depends on #1/#6
*Check:* `SELECT id, model, prompt_version, companies_tagged, finished_at FROM tag_runs ORDER BY finished_at DESC NULLS LAST;`

**R4. The live schema may differ from the migration files** (e.g. `pg_trgm` unavailable → no trigram indexes; 005/006 not yet applied).
*Check:* `db_inventory.py` (columns, constraints, indexes, extensions) against A.5.

**R5. List-query cost.** Every list render runs four queries in parallel (`web/app/page.tsx:46-51`), two of which (`searchCompanies`, `getOverview`) each pivot the whole current run (~9,620 companies × ~9 tag rows) before filtering; no index can serve the array-overlap and rank predicates because they are computed in the query. Fine at this size, not at 10×.
*Check:* `EXPLAIN (ANALYZE, BUFFERS)` on the `searchCompanies` SQL with `vc_relevance = ANY('{high}')`, `parent_sectors && '{health_life_sciences}'`, relevance sort, `LIMIT 50 OFFSET 0` (the rank arrays are in `web/lib/taxonomy.ts:103-105`). Expect a hash aggregate over `company_tags` via `company_tags_run_idx`, 11.5k lateral index probes on `snapshots_cf_observed_idx`, then a sort. Report the total time.

**R6. The single `DATABASE_URL` has two incompatible requirements.** README says the Transaction pooler (6543) breaks the Python importer (prepared statements) but works for the dashboard (`prepare: false`). If the deployment and the local `.env` are ever aligned on 6543, the weekly import fails mid-run (transactionally, so no partial state).
*Check:* which host/port each environment uses.

**R7. Off-site redirect acceptance may attribute another company's website to a company.** `scripts/test_websites.py:193-237` accepts a cross-domain redirect when the destination contains the fiscal code or full registered name (strong), or when hostnames share a ≥5-character "brand" label or the new host starts with a distinctive name token (weak). 280 `verified_offsite_redirect` + 72 `…_little_text` pages in the full run (executed, checkpoint notes).
*Check:* hand-review 20 of those 352 (`fetch_note` in `data/registry_batch/…/fetch_chunks/*.json`) for a wrong company.

**R8. THIN pages reach the model.** 1,312 companies had 1–499 characters of text (executed). They are labelled from very little evidence; the dashboard shows THIN and ranks them lower, and there is no confidence score to over-trust, which is the right honesty. Whether ~500 characters is the right floor is unmeasured.
*Check:* accuracy on the dev set split by bucket (the dev-set run already has per-company buckets in `data/batch_quality/…/fetch_snapshot.json`).

**R9. No hard spend cap in code.** Retries are bounded (2 attempts per company in `tag_one`, one corrective batch, six queue-limit resubmits) and the last full run recorded ≈ $13.36 estimated (`state.json`), but nothing stops a mis-configured `--limit` or a repeated `run` from spending again.
*Check:* an organisation-level monthly limit in the OpenAI dashboard.

**R10. Prompt-injection surface.** `TextExtractor` (`test_websites.py:118-132`) drops `script/style/noscript/template/nav/footer/aside/dialog/form`, `hidden`, `aria-hidden` and inline `display:none`, and lxml's `text_content()` excludes HTML comments; it does **not** detect class-based or off-screen hiding, and it deliberately *adds* meta descriptions when a page is thin (`:144-149`). The system prompts state that page text is untrusted (`tag_companies.py:104-105`, `score_vc_relevance.py:73`), output is constrained by a strict JSON schema, and the model has no tools — so the worst case is a wrong label or one-line. Executed: a scan of all 9,620 fetched texts for instruction-like phrases found 6 matches, all legitimate marketing copy from AI companies ("system prompt", "as an AI enthusiast"); no injection attempt observed in this run.
*Check:* nothing further needed now; keep the schema-only output contract if the prompt is ever given tools.

**R11. SSRF if the fetcher ever runs in the cloud.** `clean_website` rejects IP literals (TLD must be letters) but `check_one`/Playwright follow redirects to any host (`max_redirects=5`) before the same-site check rejects the *content*; a hostname resolving to a private range is not blocked. On a laptop this is harmless; on a cloud runner with a metadata endpoint it is not.
*Check:* only relevant for readiness (a); add a private-range guard before moving the fetch to CI.

**R12. Personal data is retained without a decision having been recorded.** `raw_record` keeps every CSV cell in every snapshot forever; ownership-prevalence flags (female/youth/foreign majority) are demographic indicators about owners and directors; the local fetch checkpoints hold full homepage text for 9,620 sites (up to 301,230 characters for one site — executed) which routinely contains founder names, emails and phone numbers. The database stores only the evidence summary, not the text.
*Check:* a human decision on retention of the fetch checkpoints and on whether `raw_record` needs a retention rule. No legal conclusion is offered here.

**R-deps. Dependencies.** All eleven runtime/dev packages exist under their exact names from their expected publishers (psycopg — Daniele Varrazzo; openai — OpenAI; playwright — Microsoft; trafilatura/courlan — Adrien Barbaresi; lxml — lxml dev team; httpx — Tom Christie; python-dotenv; pytest; next/react/react-dom/postgres/dotenv/server-only from their known repositories). Last publishes between 2026-04 and 2026-09-18; `server-only` last published 2022 by design (a one-line marker package from the React team). One unexpected package in the venv, `httpx2 2.12.0`, is a transitive requirement of the `openai` SDK (`pip show` → `Required-by: anthropic, openai`) and is imported by nothing in this repo. Python pins are floors only (no lockfile) — reproducibility risk, not a security finding.

### C.3 Architectural concerns

**A1. Snapshot-on-change records changes, not observations — per-release membership is not reconstructable.**
Because an unchanged company writes no row, "who was listed in release N" is recoverable only for the *current* release (`companies.last_seen_import_id`). `delisted_on` is set to NULL on revival (`import_csv.py:317-318`), so a delist-then-relist leaves no trace. The point-in-time query the brief asks for can only answer "last known attributes as of D":
```sql
SELECT DISTINCT ON (codice_fiscale) *
FROM company_snapshots
WHERE observed_on <= DATE '2026-08-14'
ORDER BY codice_fiscale, observed_on DESC, id DESC;
```
It cannot say whether each company was *present* on D. Since observing companies leave the registry is the stated reason for keeping history, this matters.
*Cost of leaving:* churn analysis is approximate; the false-delist scenario in C.1-#2 becomes invisible after the next import. *Cost of fixing:* one table `import_companies(import_id, codice_fiscale)` (~11.5k rows/week, one `executemany` inside the existing transaction) plus archiving raw CSVs so earlier releases can be backfilled. *Recommendation:* add it (schema change → approval).

**A2. One shared database is development, staging and production, and every script writes to it unguarded.**
`init_db.py` applies migrations with no confirmation; `tag_companies.py` writes a run by default; there is no migration ledger and no `--production` flag. *Recommendation:* a second free-tier project for development, an environment guard in `db.py` (refuse to write when the host matches production unless `--production`), and a `schema_migrations` table.

**A3. The taxonomy is defined in three places with no cross-check.** `tag_companies.CompanyTags` literals, `docs/tagging-contract-v5.md`, `web/lib/taxonomy.ts` (executed: the three agree today; TS deliberately omits `unclear`). The database has no CHECK on `tag_value`, and `fetch_bucket` has none either while `fetch_pass` does. The "current run" rule is also duplicated with different logic (view: latest `finished_at`; `export_tags.py:178`: `max(id)`). *Recommendation:* a single JSON vocabulary file read by both sides, a test that compares them, and one definition of "current".

**A4. EAV tag storage forces a full pivot on every dashboard query.** Flexible for experiments, but every list/overview call re-aggregates the whole run and no index can help the filters. *Recommendation:* when a run is published, materialise one row per company (`company_tags_current`) with array columns and GIN indexes; the view stays for ad-hoc SQL.

**A5. Append-only is enforced by convention only.** The same owner role that imports can `UPDATE`/`DELETE` snapshots; the only such statement is the broken `--force` path. *Recommendation:* a trigger that raises on UPDATE/DELETE of `company_snapshots`, or a dedicated app role with those privileges revoked. Cheap, DB-level, no application change.

**A6. No authentication, and the dashboard holds owner-level write credentials.** The README states there is no auth. Less obvious: the web app connects with the same role as the pipeline, so any future bug in a server component could write. *Recommendation:* a read-only role for the dashboard now; host-level access control before the URL is shared (see D-b).

**A7. Evidence text is not stored anywhere durable.** A tag's provenance chain is: `company_tags.run_id` → `tag_runs` (model, prompt label, notes) → `evidence` string (URL, char count, bucket, pass) → the actual text only in git-ignored JSON on one laptop. The prompt is versioned by a label, not a content hash; recovering the exact wording for an old label means finding the right commit. *Recommendation:* store a SHA-256 of the extracted text and of the system prompt on the run, and archive the checkpoints.

**A8. Fetch etiquette.** The fetcher presents a Chrome User-Agent (`test_websites.py:41-47`, deliberately, to avoid false 403s), ignores `robots.txt`, and runs 16–24 concurrent connections across hosts; the browser pass accepts invalid TLS (`render.py:155`, recorded in run notes). At one to four requests per site this is light, but it is an undisclosed crawl. *Recommendation:* decide and document; an identifying UA with a contact address is the usual compromise.

**A9. Italy is baked into the identity layer** (see D-c for the list). Changing the primary key later touches three tables' FKs and every script.

**A10. The tests give false confidence about ingestion.** Not one test runs `import_csv.py` or touches Postgres. Missing, in the brief's order: overwrite-of-history detection (the single most important), re-import → zero snapshots, leading-zero round trip through the DB, malformed row counted, interrupted import leaves nothing, absent company delisted and revived, unknown reference code, empty CSV, changed column order / extra column, mass-delist refusal. The existing tests are real (no tautologies of note; `test_prompt_matches_multi_value_contract` and the `PROMPT_VERSION` literal check are change detectors rather than behaviour tests), mocks are used only for OpenAI and HTTP transports, and no test writes to a database. Coverage was not measured; a line-coverage number would not measure the gap above anyway. *Recommendation:* a `testcontainers`-style Postgres (or a throwaway Supabase project) fixture and the ten tests above.

### C.4 Optional improvements (lowest priority)

- Distinguish AI output from registry facts on the list row: the row mixes name/place/`in liquidazione` (registry) with sector/product/customer/one-line (model) on one line; the detail page and footers explain it, the row does not. A small "AI" marker on the meta line would do. The masthead's "classified for the whole registry" overstates coverage (9,620 of 11,542; the footer is accurate).
- `web/app`: add `error.tsx` and `loading.tsx`; set a `statement_timeout`/`connect_timeout` on the pool; cache `getOverview`/`getRegions`/`getProvenance` per run (they do not depend on filters).
- `tag_companies.py:595` never closes the `AsyncOpenAI` client (`score_vc_relevance.py:174` does).
- `imports` could store the unchanged count and the skip-reason breakdown that `read_and_clean` already computes.
- Naming: `fetch_bucket` (Python/DB) vs `fetch_quality` (TS) vs "Homepage evidence" (UI); `vc_relevance_reason` vs `vc_rationale`; the 500-character THIN threshold is a literal again in `export_tags.py:61`.
- README project layout omits seven scripts and nine test files; `probe_playwright.py` is a superseded measurement tool.
- No `mypy`/`pyright`; type hints are decorative.
- ADRs do not exist; the five decisions most worth one: CF as identity key; snapshot-on-change vs per-release rows; tags attached to the company rather than a snapshot; "current run = latest finished"; direct Postgres from Next with no API layer or auth.

---

## D. Readiness assessment

**(a) Scheduled ingestion.** Blockers, concrete:
1. There is no programmatic source: the code has no download URL; a human fetches the CSV in a browser (README step 4). Automation needs a stable URL and a check that the download is complete (size/row-count sanity).
2. C.1-#2: without a delist threshold an unattended truncated file rewrites `is_active` for thousands of companies before anyone looks.
3. C.1-#3: a silent date-format change fills history with NULL-dated snapshots.
4. No notification: success or failure is an exit code and stdout. Minimum: exit non-zero on any skipped-row category above a threshold, and a message to the team on both outcomes.
5. Concurrent-run prevention: `file_sha256 UNIQUE` stops the same file twice, but two *different* files run at once both read `latest_hashes` before either commits and can both write a snapshot for the same unchanged content. One `pg_advisory_xact_lock` at the top of the transaction fixes it.
6. Secrets in CI: `DATABASE_URL` must be a repository secret; the runner needs IPv4 → the pooler host, and the Session pooler specifically (C.2-R6).
7. Runtime: Python ≥ 3.11 image (C.1-#11); Playwright is *not* needed for the import.
8. R2 (backups) becomes urgent once nobody is watching.

**(b) Multi-user team access with authentication.** Blockers:
1. No identity: no auth library, no user table, no session. Since the app is server-rendered with one DB role, auth is an application/host concern: Next middleware with an OIDC provider, or the host's password/SSO protection.
2. The dashboard's DB role can write (A6) — create a read-only role first; RLS is irrelevant to the dashboard path but must be enabled for the REST path (R1).
3. No audit log of who viewed what; if the VC rationales are considered sensitive (the README says the classifications are not public), add request logging with user identity.
4. Nothing currently trusts the client (no API routes, all inputs parameterised), which is the good news: adding auth does not require re-securing endpoints.

**(c) Multi-country expansion.** What is hardcoded to Italy, by file:
- `sql/001_schema.sql:121-122` — `codice_fiscale CHAR(11)` with an 11-digit CHECK is the primary key of `companies` and the FK target of `company_snapshots` and `company_tags`. A UK company number (8 alphanumerics) or a French SIREN (9 digits) cannot be stored without a schema change; `companies` cannot hold a non-Italian entity today.
- `sql/001_schema.sql:169`, `002_reference_data.sql` — `pv CHAR(2)` FK to an Italian province table; `ref_ateco_division` (ATECO vs NACE/SIC); the size-band legends.
- `scripts/clean.py` — Italian header aliases (`COLUMN_ALIASES`), `_CF` regex, `dd/mm/yyyy`, `_ATTIVITA` label grammar, "IN LIQUIDAZIONE" heuristic.
- `scripts/import_csv.py` — delisting semantics assume one national registry with weekly full exports; `data_vintage()` relies on the Italian section-registration date.
- `scripts/tag_companies.py:87-106`, `score_vc_relevance.py:35-36` — prompts say "Italian companies", locale `it-IT` in `render.py:149`.
- `web/` — copy ("Italian innovative-startup registry"), region facet from `ref_provincia`, `it` locale in `titleCase`.
- Currency: bands are euro integers; other registries publish different fields.
The minimal viable change is a surrogate key with `(country, registry_id)` unique, per-country reference tables, and a per-source cleaner module; everything downstream (snapshots, tags, dashboard) keys on the surrogate.

---

## E. Changes I made

Authorised by the author after reading the report ("make the fixes necessary"). One commit per fix on `audit/senior-review`, nothing pushed, **nothing applied to the database**. Tests were run before (91 passed, 24 skipped) and after every commit; final state 98 passed, 24 skipped locally and 96 passed, 26 skipped on a fresh clone with no `.env` and no registry CSV. `npm run lint`, `npx tsc --noEmit` and `npm run build` pass. Every diff was read line by line before its commit; no dependency was added; no test was weakened or changed (seven were added).

| Commit | Fixes | What changed | Verified by | What could still break |
|---|---|---|---|---|
| `Never write stub tags to the database on --dry-run` | C.1-#1 | `tag_companies.py`: a dry run skips the write; `write_results()` raises on `dry_run=True`; help text and README say "nothing written". | New test `test_dry_run_results_are_never_written` (fails if either guard is removed: the mocked `connect` would be reached). | Nothing; the only behaviour removed was writing stubs. |
| `Pin the dashboard to an explicitly published tag run` | C.1-#6 | New `sql/007_published_run.sql` (one-row `published_run` table, FK to `tag_runs`, seeded once from the newest finished run; `current_company_tags` redefined to read it). New `scripts/publish_run.py` (show / set the pointer; refuses unfinished runs, dry-run stubs, runs whose tag rows disagree with `companies_tagged`). Dashboard empty state and 404 copy say "published". README. | `py_compile`, lint, tsc, full suite. **Not applied**: the migration runs on the next `python scripts/init_db.py`, and the script is untested against a live database. | If a stub run currently has the newest `finished_at`, the seed pins it — check R3 first, then `publish_run.py --run-id 17`. |
| `Refuse a registry file whose dates no longer parse; record skip reasons` | C.1-#3, #13, reconciliation | `import_csv.py`: counts non-blank dates that fail `parse_date`; `check_unparsed_dates()` refuses unless `--allow-unparsed-dates`; skip breakdown, unparsed count and unchanged count written to `imports.notes`; `file_modified_at` stored as aware UTC; `--as-of` help corrected. New `tests/test_import_csv.py`. | Three new tests over a synthetic export with the real header names (skip counts, leading zero preserved, blank vs junk dates, guard). | The `notes` write happens only in step 8; an import refused earlier records nothing, which is the intended "loud failure". |
| `Refuse to delist more than 5% of active companies in one import` | C.1-#2 | `check_delist_share()` + a count query before the UPDATE, inside the transaction; `--allow-mass-delist`; README. | Unit test of the threshold (0.35% passes, 5% passes, 74% refuses, override honoured). | The guard function is tested; its call site is not (needs Postgres). Removing the call would not be caught by a test. |
| `Make --force replace an import in place instead of deleting its row` | C.1-#7 | `--force` keeps the `imports` row (the FKs from `companies` made deleting it impossible), deletes only that import's snapshots, resets the row's counts and reuses its id; limited to the most recent import. README. | Suite passes; **path not exercised against a database**. | A `--force` on the newest import when that import created companies leaves `companies_new` reporting 0 on the re-run; recorded in `notes`. |
| `Stop an ATECO reclassification from being read as company changes` | C.1-#4 | The latest-snapshot query also fetches `ateco_raw`; companies whose code differs are counted; `check_ateco_change_share()` refuses above 10% unless `--allow-ateco-reclassification`; the count, the ATECO header seen and any override go into `imports.notes`. README. | Unit test of the threshold. | Same caveat as the delist guard: the call site needs a database to exercise. A genuine gradual recode under 10% per week passes silently, which is acceptable — it is then attributable via `notes`. |
| `Keep paging stable, say when a page is past the end, escape search patterns` | C.1-#8, #9 | `web/lib/companies.ts`: `codice_fiscale` as final sort key in every `ORDER BY`; `escapeLike()` for `\ % _`; a separate count when a page beyond the end returns no rows. `page.tsx`: "past the end" state with a link back. `pagination.tsx`: past-end wording and "Previous" lands on the last real page. | lint, tsc, build. Not exercised in a browser (no database reachable). `tests/test_dashboard.py` will cover paging once a dev server and database are available. | None expected; the SQL shape is unchanged apart from the extra sort key. |
| `State the real Python floor: 3.11` | C.1-#11 | README; `db.py` exits with a message below 3.11. | Suite (on 3.14). | None. |
| `Skip the registry-pool test when the raw export is not on disk` | C.1-#12 | `tests/test_registry_batch.py`: `skipif` on the CSV's existence. | Fresh-clone run: 96 passed, 26 skipped (was 1 failed). | None. |
| `Refuse to attach VC scores when any company's API call failed` | C.1-#10 | `score_vc_relevance.attach_to_tag_run` stops before the database when any result carries `error`. | New test with the frozen 200 and one injected error (fails if the guard is removed: the mocked `connect` would be reached). | None. |

Not changed, deliberately: TLS verification (C.1-#5) needs the Supabase CA certificate file and a decision on where it lives; the membership table (A1), a dev/prod split (A2) and a read-only dashboard role (A6) are architectural and await the author's call.

**Rolling this out, in order:** (1) run R3's query and confirm which run should be on screen; (2) `python scripts/init_db.py` to apply `007` (seeds the pointer; nothing else changes); (3) `python scripts/publish_run.py` to confirm, or `--run-id 17` to set it; (4) redeploy `web/`; (5) the next weekly import now has three guard rails — expect zero refusals on a normal week.

---

## F. What the human must check personally

1. **RLS and Data API** (R1): run `db_inventory.py` from an IPv6 network or with the Session-pooler URI; in the Supabase dashboard confirm whether the Data API is enabled and `public` is exposed. If RLS is off, enable it on all eleven tables with no policies.
2. **Backups and plan** (R2): Database → Backups; plan tier; where the imported CSVs live. Start archiving raw CSVs and a weekly `pg_dump` regardless.
3. **Existing stub or partial runs** (R3): `SELECT id, model, companies_tagged, finished_at FROM tag_runs ORDER BY finished_at DESC NULLS LAST;` — anything above run 17 with fewer than 9,620 companies is what the dashboard is showing.
4. **Production matches migrations** (R4): the inventory output vs A.5, including whether `pg_trgm` and the trigram indexes exist.
5. **Deployment environment**: is there a public URL; which `DATABASE_URL` host/port it uses; whether host-level access control is on. The README itself warns the site is open.
6. **Registry format on the next download**: header still `ateco 2007`; comma delimiter and UTF-8 BOM (the pipe/latin-1 variant in `data-notes.md` will fail loudly in `resolve_columns`); a sample of codes against ATECO 2025.
7. **Query plan and latency** (R5): the `EXPLAIN (ANALYZE, BUFFERS)` described there.
8. **Licensing/terms**: the terms under which `startup.registroimprese.it` data may be stored and re-published; the OpenAI Batch data-use terms for company website text; the decision on retaining fetched homepage text and `raw_record` (R12).
9. **OpenAI spend cap** (R9).
10. **Off-site redirect spot-check** (R7).

---

## G. Mandatory self-review (section 19 of the brief)

1. **Files opened and read:** listed in A.1. Every `file:line` in this report was opened.
2. **Read vs inferred:** each finding carries a basis label. Inference-only claims: Supabase default grants/RLS state (R1), backup availability by plan (R2), Postgres's trailing-escape LIKE error (C.1-#9, from documented semantics), the mtime time-zone effect (C.1-#13, from psycopg/Postgres adaptation rules). Everything else is read or executed.
3. **Checks run:** table A.2 with real output, repeated after every commit in section E. Not runnable: anything needing the database.
4. **Changes:** section E. Tests before: 91 passed / 24 skipped. After: 98 passed / 24 skipped; fresh clone 96 passed / 26 skipped. Each diff was read line by line before committing; the read of the importer diff caught one stale return annotation, fixed in the final docs commit.
5. **Tests changed:** none of the existing 91 were edited; seven were added. Two of them fail if their bug is reintroduced by construction (the dry-run and VC-attach tests reach a mocked `connect` that raises). The three guard-function tests would **not** catch removal of the guard's call site — that needs a database-backed test, listed in A10.
6. **Exception handlers, defaults, fallbacks added:** one handler, in `publish_run.py`, catches `UndefinedTable` only to re-raise as a `SystemExit` telling the operator to run `init_db.py`; nothing is swallowed. No default values or fallbacks were added; every new guard fails loudly and rolls the transaction back.
7. **Dependencies added:** none. Dependency existence and maintenance were checked against PyPI and npm (A.2, R-deps).
8. **Schema, migrations, live DB:** one new migration file, `sql/007_published_run.sql`, written and **not applied**; it is idempotent (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`, `CREATE OR REPLACE VIEW`) and contains no destructive statement. Nothing else touches the schema. The inventory script is SELECT-only and could not connect anyway.
9. **Not checked, and why:** live schema, RLS, grants, row counts, `tag_runs` contents, `EXPLAIN` plans, the point-in-time query's output, and the in-database provenance trace — no database reachable from this machine (IPv6-only host, no IPv6 here). The provenance trace was done instead against the local batch artifacts: company `06882060822` → taxonomy/VC labels in `validated_results.json` → batch part 12 (`batch_6aa9bdea…`, no retry) → fetch checkpoint `00010.json` (http pass, OK, 840 chars, text begins "BIKE TOUR Hop on our bike…") → models `gpt-5.6-terra`/`gpt-5.6-luna`, prompts `v5.1-product-boundaries-2026-09-13`/`vc-relevance-v1-2026-09-13`, written as run 14 on 2026-09-17; not replaced by the recovery run. Also not checked: the dashboard at runtime (needs the DB), `docs/tagging-contract-v4.md` and `prompt-v3` bodies (superseded), the deployment.
10. **Most likely to be wrong:** the severity I gave C.1-#2 (mass delisting). The brief calls a missing threshold high-severity; because it is fully reversible on the next good import and the dashboard ignores `is_active`, a reasonable reviewer could call it medium. The second candidate is R1: if RLS was enabled in the dashboard when the project was created, that whole risk evaporates — which is exactly why it is listed as "verify", not "defect".

### Measured accuracy of the enrichment (for the record)

The dev set (`data/devset_labels_2026-09-07.csv`, 40 hand-labelled companies) is the only ground truth. From `data/batch_quality/quality_report.txt` (executed read), exact set-match accuracy of the production prompt/model: `parent_sector` 28/40, `product_type` 28–29/40, `customer_model` 28–30/40 — roughly 70–75% per field with a ±14-point confidence interval at n=40. The free-text `sector` and the VC-relevance label have **no measured accuracy** (VC relevance has no ground truth at all; the gate only checks run-to-run agreement). Any analysis built on the tags inherits roughly one wrong categorical label in four, and an unknown error on VC relevance. Neither number appears in the dashboard.
