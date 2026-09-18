# ADR 0003 — Tags attach to the company, live in versioned runs, and are published explicitly

Status: accepted (2026-09-18; the publish step was added by the audit fixes)

## Context

The registry's own classification is too coarse (44% of companies share one
ATECO code). LLM-generated tags fix that, but every prompt or model change
produces different labels, and the labels must be comparable across versions
without destroying earlier results.

## Decision

- Tags attach to the **company**, not to a snapshot. A tag describes what the
  company does, which the weekly registry changes do not affect.
- Every tagging job writes a `tag_runs` row (model, `PROMPT_VERSION`, notes)
  and its `company_tags` rows reference that run. Runs are never overwritten;
  a new prompt is a new run.
- `company_tags` is entity-attribute-value (`tag_type`, `tag_value`, one row
  per value) so a schema change in the vocabulary needs no migration.
- The dashboard reads **one explicitly published run**: the one-row
  `published_run` table (`sql/007`), moved only by
  `scripts/publish_run.py --run-id N` after a human has reviewed the run.
  Finishing a run does not change what is on screen.

## Consequences

- Prompt versions can be graded against each other on the same companies.
- Publishing is a deliberate act, so a 200-company benchmark, a stub run or a
  recovery attempt cannot silently replace the full-registry view (this was
  audit finding C.1-#6 before `007`).
- The EAV shape means every dashboard list query pivots the whole run
  (~9,620 × ~9 rows) before filtering. Fine at this size; at 10× the size,
  materialise one row per company on publish (backlog B9).
- "Current run" must be defined in exactly one place. `export_tags.py` still
  uses `max(id)` (backlog B5); until that is fixed, pass `--run-id`.
