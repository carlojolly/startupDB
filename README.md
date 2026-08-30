# Startup Map

A searchable database of Italian innovative startups, built from the public
registry published at [startup.registroimprese.it](https://startup.registroimprese.it).

The registry publishes a fresh CSV every week. This repo loads those exports
into Postgres **append-only**: each import adds new snapshot rows rather than
overwriting, so the database accumulates history the registry itself does not
keep. That matters because a company drops out of the registry once its
five-year innovative-startup status expires — the weekly CSV is a snapshot of
who qualifies *today*, not an archive.

Current state: **data ingestion only.** No frontend yet.

---

## Quick start

You need **Python 3.10+** and a Postgres database. Nothing runs locally except
Python — the database is hosted.

### 1. Get a database

Either provider works and both have a free tier that is far more than enough
for ~11,500 companies.

**Supabase** — create a project at [supabase.com](https://supabase.com), then
Project Settings → Database → Connection string → URI. Take the **Session
pooler** URI (port 5432) and substitute your password.

**Neon** — create a project at [neon.tech](https://neon.tech), then Connection
Details → copy the connection string. Keep the `?sslmode=require` on the end.

> Everyone on the team can share one database. If you would rather each have
> your own, just create one project each — the setup below is identical.

#### Supabase: direct connection vs. pooler (read this before you debug a hang)

Supabase shows you a **direct** connection string that looks like
`postgresql://postgres:...@db.<ref>.supabase.co:5432/postgres`. That hostname
resolves to **IPv6 only** — it has no A record. It works fine on a network with
IPv6, and fails with a confusing timeout on one without. University and
corporate networks frequently do not route IPv6.

If the direct string times out for you, switch to the **Session pooler** string
from the same dashboard page. It is IPv4-compatible and otherwise identical:

```
postgresql://postgres.<ref>:PASSWORD@aws-0-<region>.pooler.supabase.com:5432/postgres
```

Note the different username format (`postgres.<ref>`, not `postgres`).

**Do not use the Transaction pooler on port 6543** for these scripts. It does
not support prepared statements, which psycopg uses by default, so the import
will fail partway through.

#### Passwords with special characters

The connection string is a URL, so `@ : / ? # [ ] %` in your password must be
percent-encoded. This prints the encoded form without echoing what you type
and without putting it in your shell history:

```bash
python3 -c "import urllib.parse,getpass;print(urllib.parse.quote(getpass.getpass('password: '),safe=''))"
```

### 2. Set up the project

```bash
git clone <your-repo-url>
cd startup-map

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
```

Open `.env` and paste your connection string after `DATABASE_URL=`.
`.env` is git-ignored — never commit it.

### 3. Create the tables

```bash
python scripts/init_db.py
```

This applies every file in `sql/` in order. It is safe to re-run at any time:
all the SQL uses `IF NOT EXISTS` / `ON CONFLICT`, so running it again after
someone adds a column or a lookup value just applies the new bits.

### 4. Get the data

Download the CSV export from
[startup.registroimprese.it](https://startup.registroimprese.it) and save it
into `data/raw/`. Name it with the date you downloaded it:

```
data/raw/startup_2026-08-30.csv
```

**Do not open it in Excel and re-save.** 6,961 of the codice fiscale values
and 70 of the ATECO codes start with a leading zero, and Excel silently
destroys those by treating the column as a number. If you need to look at it,
use a text editor or `head`.

### 5. Import

Try it first without writing anything:

```bash
python scripts/import_csv.py data/raw/startup_2026-08-30.csv --dry-run
```

Then for real:

```bash
python scripts/import_csv.py data/raw/startup_2026-08-30.csv
```

You should see roughly:

```
Import id : 1
Companies : 11542 seen, 11542 new
Snapshots : 11542 written, 0 unchanged (no row needed)
Delisted  : 0 companies absent from this file
```

---

## The weekly update

Download the new CSV into `data/raw/` with the new date in the filename, then
run the same import command. Nothing else to do.

The second and later runs will look more like `Snapshots: 180 written, 11400
unchanged` — only companies whose data actually changed get a new row.

**Running the same file twice is safe.** The importer fingerprints each file
with SHA-256 and refuses to load one it has already seen:

```
This exact file was already imported (import id 3, on 2026-08-30 14:22).
Nothing to do. Use --force to load it again.
```

Three independent mechanisms prevent duplicates, so a mistake here cannot
corrupt the history:

1. `imports.file_sha256` is `UNIQUE` — the same file is rejected before parsing.
2. Snapshots are written only when a company's content hash changes.
3. `company_snapshots` has `UNIQUE (codice_fiscale, import_id)`.

The whole import runs in **one transaction**. If it fails halfway, nothing is
written at all — there is no half-loaded state to clean up.

### Useful flags

| Flag | What it does |
|---|---|
| `--dry-run` | Runs the entire import, prints the summary, then rolls back. |
| `--as-of 2026-08-30` | Sets the snapshot date. Defaults to the file's modification time. |
| `--no-delist` | Skips marking absent companies inactive. Use when loading an **older** file after a newer one, which would otherwise delist everyone wrongly. |
| `--force` | Re-imports a file already loaded, deleting the previous import and its snapshots first. Repair tool — not part of the normal workflow. |

---

## What's in the database

### Tables

| Table | Rows | What it holds |
|---|---|---|
| `companies` | one per company, forever | Stable identity keyed on `codice_fiscale`, plus `first_seen_on` / `last_seen_on` / `is_active`. Never gets a second row for the same company. |
| `company_snapshots` | append-only | One row per *observed change*. Never updated, never deleted. |
| `imports` | one per CSV loaded | Audit log: which file, when, how many rows, how many changed. |
| `company_tags` | filled in later | LLM-generated labels, attached to the company. |
| `tag_runs` | one per tagging job | Which model and prompt version produced a batch of tags. |
| `ref_*` | small lookups | Decode the registry's coded bands into real numbers. |

The split between `companies` and `company_snapshots` is the important idea:
**identity is stable, state is historical.** Ask "does this company exist and
is it still listed" against `companies`; ask "what did we know about it, and
when" against `company_snapshots`.

### Views — query these, not the raw tables

| View | Use it for |
|---|---|
| `companies_current` | **Start here.** One row per company with its latest snapshot, every coded band already decoded, and the region joined in. This is what a frontend should query. |
| `company_change_log` | Every recorded change with the previous value alongside it. |
| `current_company_tags` | Tags from the most recent tagging run only. |
| `import_history` | Health check on the weekly loads. |

### The reference tables earn their keep

The registry encodes size as opaque letters and numbers: revenue class `A`,
capital class `3`. The `ref_*` tables decode those into actual bounds, which
is what makes this work:

```sql
-- Typo-tolerant company name search (needs pg_trgm, see 004_search_indexes.sql)
SET pg_trgm.similarity_threshold = 0.25;
SELECT latest_denominazione, similarity(latest_denominazione, 'BIOTECNOLOGIE') AS s
FROM companies
WHERE latest_denominazione %% 'BIOTECNOLOGIE'
ORDER BY s DESC LIMIT 20;

-- Plain substring search also uses the trigram index, so a leading
-- wildcard stays fast:
SELECT latest_denominazione FROM companies
WHERE latest_denominazione ILIKE '%ENERGIA%';
```

```sql
-- Companies with revenue over €1M, sorted by size.
-- Without ref_classe_produzione you would be writing
-- `WHERE classe_produzione IN ('D','E','F','G','H')` and getting it wrong.
SELECT denominazione, comune, classe_produzione_label
FROM companies_current
WHERE produzione_min_eur >= 1000000
ORDER BY produzione_min_eur DESC;
```

`ref_provincia` also supplies the **region**, which the CSV does not contain at
all — it only has two-letter province codes.

---

## Example queries

```sql
-- How many active companies do we have?
SELECT count(*) FROM companies_current WHERE is_active;

-- Deeptech in Lombardia, biggest first
SELECT denominazione, comune, sito_internet_url, classe_produzione_label
FROM companies_current
WHERE regione = 'Lombardia'
  AND req_brevetto                      -- qualified via patent
  AND is_active
ORDER BY produzione_min_eur DESC NULLS LAST;

-- Registrations per region per year
SELECT regione,
       date_part('year', data_iscrizione_sezione_startup) AS anno,
       count(*)
FROM companies_current
GROUP BY 1, 2 ORDER BY 1, 2;

-- Recently incorporated, female-led, still active
SELECT denominazione, comune, regione, data_iscrizione_sezione_startup
FROM companies_current
WHERE prevalenza_femminile IN ('Forte', 'Esclusiva')
  AND data_iscrizione_sezione_startup > CURRENT_DATE - INTERVAL '12 months'
  AND is_active AND NOT in_liquidazione
ORDER BY data_iscrizione_sezione_startup DESC;

-- Who disappeared from the registry, and when?
SELECT codice_fiscale, latest_denominazione, first_seen_on, delisted_on
FROM companies WHERE NOT is_active ORDER BY delisted_on DESC;

-- What changed in the most recent import?
SELECT codice_fiscale, denominazione, prev_denominazione,
       classe_addetti, prev_classe_addetti
FROM company_change_log
WHERE snapshot_number > 1
ORDER BY observed_on DESC LIMIT 50;
```

---

## Known data quirks

The registry export is messier than it looks. The full findings are in
[`docs/data-notes.md`](docs/data-notes.md); the ones that bite hardest:

- **The CSV is UTF-8 with a BOM**, uses CRLF, and three of its column headers
  contain literal newline characters (`"1° req.\n(6)"`). Parse it with
  `encoding="utf-8-sig"`.
- **274 completely empty trailing rows.** Any row without a codice fiscale is
  spreadsheet padding and is skipped.
- **`ateco 2007` is not always 6 digits** — 4% are 2–5 digits and 58 rows are
  the literal string `NC`. Short codes are genuinely coarser levels of the
  hierarchy, **not** truncated 6-digit codes. Never zero-pad them.
- **44% of companies share one ATECO code** (`621000`, software production).
  The official classification is too coarse to be useful on its own — which is
  what the LLM tagging is for.
- **The three `req.` columns are `SI`-or-blank, never `NO`.** Blank means the
  criterion does not apply, so it is stored as `false`, not `NULL`.
- **`classe di addetti` is missing for 65% of companies.** Headcount is not a
  usable filter for most of the database. Revenue is missing for 34%.
- **327 companies have a startup-section date earlier than their registry
  date**, usually a re-registration after moving registered office. Any
  "time to startup status" metric goes negative for these.
- **There is no company status column.** 286 companies are detectable as
  winding down only because their *name* contains "IN LIQUIDAZIONE" or
  "IN SCIOGLIMENTO", which is what `in_liquidazione` is derived from.
- **Websites are dirty** — missing schemes, spaces inside domains, several
  domains crammed into one cell, and values like `non presente`. The cleaner
  salvages 99.7%; the 25 it cannot are kept verbatim in `sito_internet_raw`.
- **One website is shared by 14 different companies** (an accountant's own
  site, filled into clients' filings). Do not treat a domain as an identity.

Every snapshot also stores the original CSV row verbatim in `raw_record`
(JSONB). If a value looks wrong, the source is still in the database and you
can fix it with SQL rather than re-importing.

---

## Project layout

```
.
├── README.md
├── requirements.txt
├── .env.example          # template; copy to .env and fill in
├── .gitignore            # excludes .env and all data files
│
├── sql/                  # applied in filename order by init_db.py
│   ├── 001_schema.sql        tables, constraints, indexes
│   ├── 002_reference_data.sql the registry's legend as lookup tables
│   ├── 003_views.sql         companies_current and friends
│   └── 004_search_indexes.sql trigram indexes for name/town search
│
├── scripts/
│   ├── db.py             # the one place that knows how to connect
│   ├── init_db.py        # applies sql/
│   ├── clean.py          # CSV string -> typed value. No database code.
│   └── import_csv.py     # the weekly import
│
├── tests/
│   └── test_clean.py     # runs without a database
│
├── data/raw/             # git-ignored. Put the CSV exports here.
└── docs/
    └── data-notes.md     # full data-quality findings
```

`clean.py` deliberately contains **no database code** — every function in it
is a plain function you can call in a REPL. When a value looks wrong in the
database, that is the file to open first.

---

## Running the tests

```bash
pytest
```

35 tests, none of which need a database. Most of the website cases are real
values copied out of the registry export. There is also a whole-file smoke
test that runs only if you have a CSV in `data/raw/`, and is skipped otherwise.

---

## Contributing

- **Never commit `.env` or anything from `data/`.** Both are git-ignored;
  please keep it that way.
- **Schema changes go in a new numbered file** in `sql/` (`004_...`), not by
  editing an existing one. Other people have already applied the old files.
  Keep new SQL idempotent so `init_db.py` stays re-runnable.
- **Never `UPDATE` or `DELETE` in `company_snapshots`.** It is append-only;
  that is the whole point of the design.
- If the registry changes its export format, the fix is usually one entry in
  `COLUMN_ALIASES` at the top of `scripts/clean.py`. The importer fails with a
  readable message listing the headers it found, rather than a `KeyError`.
- Add a test to `tests/test_clean.py` when you touch the cleaning logic.
