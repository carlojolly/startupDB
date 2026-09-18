# Working in this repository

Instructions for any coding agent (Claude Code reads this through `CLAUDE.md`;
Codex and others read it directly). Everything here was verified against the
code on 2026-09-18. When this file and the code disagree, the code is right:
fix this file in the same change.

## What this is

A searchable database of Italian innovative startups, loaded weekly from the
public registry CSV into Postgres **append-only**, enriched offline with
LLM-generated tags, and read by a Next.js dashboard (VentureAtlas).

Two halves, one database, one credential file:

| Half | Where | Runs with | Talks to the DB via |
|---|---|---|---|
| Pipeline | `scripts/`, `sql/`, `tests/` | Python 3.11+ in `.venv` | `scripts/db.py` (psycopg, one `connect()`) |
| Dashboard | `web/` | Node 20.9+ (`npm`) | `web/lib/db.ts` (postgres.js), queries only in `web/lib/companies.ts` |

`DATABASE_URL` lives in the git-ignored root `.env`; both halves read it.
`OPENAI_API_KEY` in the same file is needed only by the tagging scripts.

**There is one database and it is production.** No dev or staging copy exists.
Every script that writes, writes there. Treat it accordingly (see "Hard rules").

## Commands that are safe to run any time

```bash
.venv/bin/python -m pytest -q            # 100+ offline tests, ~3 s, no DB, no network
cd web && npm run lint                   # eslint
cd web && npx next typegen && npx tsc --noEmit   # typecheck (typegen makes the git-ignored type stubs)
cd web && npm run build                  # build; succeeds with no DATABASE_URL
python scripts/import_csv.py FILE --dry-run   # full import, then rollback
python scripts/tag_companies.py --dry-run     # fetch + stub tags, nothing written
python scripts/publish_run.py                 # show which run is on screen
```

Tests marked skipped are expected: `tests/test_dashboard.py` needs a dev
server on :3000, and two tests need the git-ignored raw CSV.

## Commands that change the shared database (ask before running)

| Command | Writes |
|---|---|
| `python scripts/init_db.py` | Applies every `sql/*.sql` in order (idempotent, but it is a migration) |
| `python scripts/import_csv.py FILE` | New import, snapshots, delistings, in one transaction |
| `python scripts/tag_companies.py` (no `--no-write`) | A new `tag_runs` row plus tags for the frozen 200 |
| `python scripts/score_vc_relevance.py --attach-to-run-id N` | VC labels onto run N |
| `python scripts/tag_registry_batch.py run --write` | Full-registry run (~9,620 companies, ~$13 on OpenAI Batch) |
| `python scripts/recover_tag_run.py` | A new run derived from a base run |
| `python scripts/publish_run.py --run-id N` | Moves what the dashboard shows |
| `python scripts/read_feedback.py --handle N` | Marks one reader's note handled (reading is safe) |

Run these only when the user asks for that specific run. Prefer the
`--dry-run` / `--no-write` form first and show its output.

## Hard rules

1. **Append-only history.** Never `UPDATE` or `DELETE` rows in
   `company_snapshots`. The only sanctioned exception is `import_csv.py --force`,
   which replaces the most recent import's snapshots and is a repair tool.
2. **One transaction per import.** All writes in `import_csv.py` happen inside
   the single `with connect() as conn:` block. Any new check must raise inside
   it (rollback), never print-and-continue.
3. **`codice_fiscale` is an 11-character string**, 6,961 of them with a leading
   zero. Never cast to int, never let pandas or Excel touch the CSV.
4. **Migrations are new files.** `sql/001`–`008` have been applied to the live
   database; 007 and 008 were applied on 2026-09-18 and verified against it.
   Do not edit them; add `sql/009_<name>.sql` using `IF NOT EXISTS` /
   `ON CONFLICT` / `CREATE OR REPLACE VIEW` so `init_db.py` stays re-runnable.
   The repo said 007 was applied for months while it was not, so check
   `to_regclass` before trusting this list for anything destructive.
5. **The dashboard shows the published run only** (`published_run` table,
   `sql/007`). Finishing a tag run changes nothing on screen until
   `publish_run.py --run-id N` is run by a human. True of the live database
   since 2026-09-18; run 17 is published.
6. **No LLM calls at runtime.** Enrichment is an offline batch step whose cost
   is paid once per run. Do not add a model call to a request path in `web/`
   or to anything scheduled. See `docs/adr/0005`.
7. **Frozen experiment inputs.** `data/sample_200_2026-09-06.csv`, the 40-company
   dev set, and the v5.1 schema are fixed by `docs/tagging-contract-v5.md`.
   Do not change them mid-comparison; record gaps for a future version.
8. **Bump `PROMPT_VERSION`** in `scripts/tag_companies.py` whenever the prompt
   or output schema changes. Runs are compared by that label.
9. **Vocabularies are declared three times** (`tag_companies.CompanyTags`,
   `web/lib/taxonomy.ts`, `docs/tagging-contract-v5.md`).
   `tests/test_taxonomy_consistency.py` fails if they drift. Change all three.
10. **Fail loudly.** No new `except: pass`, no silent defaults, no fallback
    values. Every guard in this repo refuses and rolls back; keep it that way.
11. **Secrets.** `.env` is never committed. `web/` has no `NEXT_PUBLIC_*`
    variable and must not get one; `process.env` is read only in `web/lib/db.ts`.
12. **Server-only data access.** Every read stays in `web/lib/companies.ts`
    and the one write in `web/lib/feedback.ts`, both guarded by
    `import "server-only"`. Client components import only `lib/taxonomy`,
    `lib/model`, `lib/search-params`. The feedback box reaches the database
    through the server action in `web/app/actions.ts`. No API routes exist and
    none are needed — add a server action, not a route.

## Facts about the data you will otherwise get wrong

- The registry CSV is UTF-8 **with BOM**, CRLF, comma-delimited, 24 columns,
  and three headers contain literal newlines. `clean.resolve_columns()`
  matches headers by a normalised form; never match them by exact string.
- Dates are `dd/mm/yyyy`. An unparseable non-blank date refuses the whole
  import unless `--allow-unparsed-dates`, because a format change would
  otherwise NULL every date and write 11,500 false snapshots.
- The ATECO header currently reads `ateco 2007`. A jump of more than 10% of
  companies changing code in one week is treated as a reclassification and
  refused unless `--allow-ateco-reclassification`.
- Delisting more than 5% of active companies in one import is refused unless
  `--allow-mass-delist` (a normal week delists a few dozen).
- The direct Supabase host `db.<ref>.supabase.co` **no longer resolves at
  all**. It was documented here as IPv6-only, but as of 2026-09-18 it returns
  no A, AAAA or CNAME record from any public resolver, so no network reaches
  it and the IPv4/IPv6 question is moot. `.env` uses the **Session pooler**
  URI instead (`aws-<n>-<region>.pooler.supabase.com`, port 5432, username
  `postgres.<ref>`), which is what the Supabase dashboard now hands out.
  **Never** use the Transaction pooler (6543) for the Python scripts: it
  rejects prepared statements. The dashboard tolerates both (`prepare: false`).
  A `getaddrinfo ENOTFOUND db.<ref>.supabase.co` in the dev server means the
  old direct host has come back from somewhere — check `.env` first.
- Size bands come as opaque codes (`classe_produzione = 'A'`); the `ref_*`
  tables decode them. Query `companies_current`, not the raw tables.
- `unclear` is a valid model output for every closed field and means "not
  understood". The dashboard renders it as missing, never as a value, and it
  is deliberately absent from `taxonomy.ts` value arrays.
- Fetch buckets: `OK` ≥ 500 characters of homepage text, `THIN` 1–499,
  `DEAD` 0. DEAD companies never reach the model and get `unclear` by rule.
- Measured accuracy of the published tags on the 40-company dev set is about
  70–75% per closed field (±14 points at n=40). Free-text `sector` and VC
  relevance have no measured accuracy. Do not present tags as facts.
- Full profile of the export: `docs/data-notes.md`. Trust it over intuition.

## Where things are

```
scripts/db.py               connect(), DATABASE_URL, Python ≥ 3.11 check
scripts/clean.py            header aliasing, scalar cleaners, content hash
scripts/import_csv.py       weekly import: guards, snapshots, delisting
scripts/init_db.py          applies sql/*.sql in order
scripts/tag_companies.py    CompanyTags schema, SYSTEM_PROMPT, PROMPT_VERSION,
                            fetch (http → Playwright), sync tagging of the 200
scripts/score_vc_relevance.py  VCRelevance schema and separate VC pass
scripts/eval_batch_quality.py  request_body(): the one canonical request shape
scripts/tag_registry_batch.py  resumable full-registry OpenAI Batch job
scripts/recover_tag_run.py     targeted re-fetch/re-tag into a new run
scripts/publish_run.py         the pointer the dashboard reads
scripts/export_tags.py         CSV export per the contract's 13 columns
scripts/read_feedback.py       what readers wrote in the dashboard's feedback box
scripts/test_websites.py, render.py   fetch pass 1 (httpx) and pass 2 (Chromium)
sql/001 schema · 002 reference data · 003 views · 004 trigram indexes ·
    005 fetch provenance · 006 import vintage · 007 published_run ·
    008 feedback
web/lib/companies.ts        every SQL read the dashboard runs
web/lib/feedback.ts         the one SQL write: a reader's note
web/app/actions.ts          the server action behind the feedback box
web/components/feedback.tsx the header's feedback popover
web/lib/taxonomy.ts         vocabularies, labels, and SQL sort order
web/lib/search-params.ts    URL ⇄ filter state (all UI state is in the URL)
docs/tagging-contract-v5.md the frozen experiment contract
docs/data-notes.md          measured facts about the export
docs/adr/                   why the big decisions were made
docs/BACKLOG.md             what to do next, as executable specs
docs/audit/                 the 2026-09-18 senior review (findings + fixes)
```

## How to make a change

1. Read `docs/BACKLOG.md` first if the task is one of the listed items; each
   has acceptance criteria and a verify command. Read the relevant ADR before
   changing something it covers.
2. Smallest safe diff. One concern per commit. No new dependency without
   saying why in the commit body; check the package exists under that exact
   name from its expected publisher before adding it.
3. Add or extend a test next to the change. Existing tests are not edited to
   make a change pass; if one must change, say why in the commit.
4. Update `README.md` when a command, flag, or behaviour changes. The README
   is the operator manual and is expected to be accurate.
5. Before finishing, run the full offline check and paste real output:
   ```bash
   .venv/bin/python -m pytest -q && (cd web && npm run lint && npx next typegen && npx tsc --noEmit && npm run build)
   ```
   Anything that needs the database is **not verified** from this machine.
   Say so explicitly rather than implying it was run.
6. Commit messages: an imperative sentence describing the behaviour change
   ("Refuse a registry file whose dates no longer parse"), a body with the why.
   No "fix bug" / "update code".

## What not to do

- Do not touch `data/` contents; they are git-ignored artefacts of real runs.
- Do not run any command from the write table above on your own initiative.
- Do not add an LLM call, embedding call, or external API to the dashboard.
- Do not add `sslmode` or SSL changes casually; C.1-#5 in the audit explains
  what is needed (a CA file) and is tracked in the backlog.
- Do not "clean up" `raw_record` JSON or the `unclear` handling; both are
  deliberate (ADR 0002, README "Known data quirks").
- Do not write new bake-off prompts into `tag_companies.py` without a
  `PROMPT_VERSION` bump and a dev-set evaluation (`scripts/eval_prompt.py`).
