# Agents — design map

Pipeline / DB hard rules live in **`AGENTS.md`** (uppercase). This file is the `/frontend-design` provenance map (`workflow.project-docs`).

## Map — where UI code lives

| Area | Path | Notes |
|------|------|-------|
| UI screens | `web/app/` | `/`, `/company/[cf]`, `not-found` |
| UI components | `web/components/` | Header, filters, rows, signals, feedback |
| Design tokens | `web/app/globals.css` | Charcoal surfaces + yellow brand |
| Data reads | `web/lib/companies.ts` | Server-only |
| Feedback write | `web/lib/feedback.ts`, `web/app/actions.ts` | Server-only |
| Skills (this pack) | `skills/frontend-design`, `skills/backend-engineering` | Linked from `.cursor/skills`, `.claude/skills`, `.agents/skills` |
| Impeccable | `.cursor/skills/impeccable` | Engine bin gitignored; re-run `npx impeccable install` |

## Components (provenance)

| path | role | provenance_id | source |
|------|------|---------------|--------|
| `web/app/layout.tsx` | Root fonts (Urbanist display + Source Sans 3 UI) | anti.inter-everywhere | source:impeccable |
| `web/app/globals.css` | Token system / focus / reduced motion | craft.tight-palette, a11y.baseline | source:our-skill |
| `web/app/page.tsx` | Directory screen | workflow.screen-inventory | source:our-skill |
| `web/components/pending.tsx` | In-flight list refresh feedback | a11y.baseline, checklist.unslop-20 §19 | source:our-skill |
| `web/components/site-header.tsx` | Sticky chrome + feedback entry | craft.tight-palette | source:our-skill |
| `web/components/company-row.tsx` | Result row (product surface) | craft.product-in-hero (directory-as-product) | source:our-skill |
| `docs/screen-inventory.md` | Screen inventory | workflow.screen-inventory | source:our-skill |

## Agents may

- Update this file when UI structure or provenance changes
- Tag new UI with `provenance_id` + `source`
- Append `decision.md` for material design choices
- Run Impeccable critique / audit / polish / detect on `web/`

## Agents must not

- Commit secrets or `.env`
- Remove this Components provenance table
- Rewrite approved UI without updating `docs/screen-inventory.md` / `decision.md`
- Add runtime LLM calls to `web/` (see `AGENTS.md` / ADR 0005)
- Force FluxEdit / Palmatech / Code XR brand colors onto Glimpse
- Run DB write scripts without an explicit operator request (`AGENTS.md`)
