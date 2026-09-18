# ADR 0005 — LLM enrichment is an offline batch step; nothing at runtime calls a model

Status: accepted 2026-09-18

## Context

The tags come from a language model. The project owner does not want ongoing
model spend: the enrichment budget is paid once per run, and the dashboard
must keep working, unchanged in cost, whichever model is or is not available
later. The model used is also a **reported variable** of the bake-off
(`docs/tagging-contract-v5.md` §1), not a fixed part of the system.

## Decision

- Model calls happen only in the pipeline scripts, only when an operator runs
  them, and their cost is recorded in `tag_runs.notes` and the batch state
  file. The last full-registry run cost about $13 on OpenAI Batch.
- The dashboard, the import, and anything scheduled make **no** model,
  embedding or external API calls. Features are built from SQL over the data
  the pipeline has already produced (history, expiry dates, tags, trigram
  similarity).
- Model choice is a per-run parameter with its own pricing entry
  (`tag_companies.MODEL_PRICING`) and its own `tag_runs` row; switching models
  is a new run and a new evaluation, never an edit to the old one.
- Quality of a model or prompt change is judged on the held-out dev set
  (`scripts/eval_prompt.py`, `scripts/eval_batch_quality.py`) before a
  full-registry run, and the per-company cost is reported next to accuracy.

## Consequences

- Operating cost is the database and the host. A change of model vendor
  touches only `scripts/`, and only the request-building code
  (`eval_batch_quality.request_body`, `tag_companies.tag_one`,
  `score_vc_relevance`).
- Ideas that need a model per request (natural-language search, on-demand
  dossiers, weekly narrative digests) are out of scope unless this ADR is
  superseded. Their SQL-only counterparts are in the backlog (B7, B8).
- Because a full run is cheap relative to the value of the tags, "re-run with
  a different model" is always available as a later decision; nothing in the
  schema assumes one vendor.
