# Context

## What it does

Glimpse is a Next.js dashboard over a Postgres copy of Italy’s innovative-startup registry. Operators search and filter companies; offline LLM tag runs enrich sector, product, customer, and VC-relevance labels. The UI reads only the published tag run.

## Who it is for

People exploring or sourcing Italian innovative startups who need filters and evidence quality signals, not a marketing site.

## How it works

- Weekly CSV import appends snapshots (`scripts/`, `sql/`).
- Tagging is offline; `publish_run.py` points the dashboard at a run.
- `web/` is a server-rendered Next app: reads in `web/lib/companies.ts`, feedback write in `web/lib/feedback.ts`. All interactive filter state lives in the URL.

## Out of scope (for now)

- Runtime LLM / embedding calls in `web/`
- Auth / multi-tenant accounts
- Redesigning the product as a marketing landing (this is app-ui)
- Vendoring the heavy Taste Skill asset pack (marketing companion); dashboard path uses this pack + Impeccable
