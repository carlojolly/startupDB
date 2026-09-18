# ADR 0002 — History is append-only, and a snapshot is written only on change

Status: accepted (retroactively recorded 2026-09-18)

## Context

The registry publishes a full CSV every week and keeps no archive. A company
disappears from the export when its five-year innovative-startup status ends.
The reason this project exists is to keep the history the registry discards.

## Decision

- `company_snapshots` is **append-only**. No `UPDATE`, no `DELETE`. The single
  exception is `import_csv.py --force`, a repair tool limited to replacing the
  most recent import's snapshots in place.
- A snapshot row is written only when a company's **content hash changes**
  (`clean.content_hash` over the hashed fields). An unchanged company writes
  nothing. Identity (`companies`) is stable; state (`company_snapshots`) is
  historical.
- Every import runs in **one transaction**; guards raise inside it so a
  refused file leaves nothing behind.
- Every snapshot keeps the full raw row as `raw_record` JSON, so a field the
  schema does not model today can be recovered later.

## Consequences

- ~11,500 companies produce a few hundred snapshot rows a week instead of
  11,500, and "what changed and when" is a direct query (`company_change_log`).
- **Per-release membership is not reconstructable** from snapshots alone:
  "who was listed in import N" is known only for the current import. A
  delist-then-relist overwrites `delisted_on`. Fix, if wanted: an
  `import_companies(import_id, codice_fiscale)` table (backlog item B4).
- A registry-side change that alters every row (date format, ATECO recode)
  would write a snapshot for every company. Three guards in `import_csv.py`
  refuse such files rather than let that happen; each has an override flag so
  an unusual week is a decision.
- Append-only is enforced by convention and review, not by the database. A
  trigger or a write-restricted role would make it structural (backlog B2).
