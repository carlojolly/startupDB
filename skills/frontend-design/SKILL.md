---
name: frontend-design
description: Orchestrates UI-first product design for Claude Code and Cursor — screen inventory, shadcn/21st/Motion/Animate UI/Taste Skill/Impeccable routing, unslop checklist, a11y gates, provenance tagging, and taste-feedback so rejected patterns can be removed from the skill. Use when building or redesigning UI, landing pages, dashboards, components, or when the user rejects a look and wants it gone permanently.
---

# Frontend Design

Orchestrator for frontend and design work. Companions supply craft; this skill owns workflow, gates, project docs, and the living taste ledger.

Read references on demand (do not load everything at once):

- `references/companion-stack.md` — when to use each companion
- `references/provenance.md` — every default pattern → source id (skip `rejected`)
- `references/taste-memory.md` — preferred / rejected / replaced
- `references/screen-inventory.md` — fill before coding screens
- `references/screen-first-workflow.md` — GitHub → UI → docs order
- `references/design-checklist.md` — 20 unslop checks (`source:user-notes`)
- `references/ui-craft-patterns.md` — mockup craft refs (not forced brands)
- `references/motion-stack.md` — Motion Primitives + Animate UI rules
- `references/twentyfirst-dev.md` — 21st CLI/MCP usage
- `references/a11y-responsive.md` — accessibility + responsive review
- `references/definition-of-done.md` — UI approved gates
- `assets/` — quality reference images

Also use backend templates when creating docs: `../backend-engineering/references/project-docs-templates.md`.

## Workflow (ordered)

1. Clarify product, audience, and constraints. If `context.md` exists, read it.
2. Fill a **screen inventory** (`references/screen-inventory.md`) — every screen + empty/loading/error — before markup.
3. Route via `references/companion-stack.md`:
   - Marketing / company site → Taste Skill patterns (and skill if installed)
   - App UI → **shadcn/ui** primitives first
4. Prefer **21st.dev** catalog sections before inventing large blocks (`references/twentyfirst-dev.md`).
5. Add motion only when useful (`references/motion-stack.md`). Do not stack Animate UI + Motion Primitives + flashy 21st motion by default. Honor `prefers-reduced-motion`.
6. Apply craft patterns + `references/design-checklist.md`. Never force FluxEdit / Palmatech / Code XR brand colors onto unrelated products.
7. **Tag provenance** for every non-trivial UI choice:
   - Append `decision.md` with timestamp, `source:…`, `provenance_id:…`
   - Update `agents.md` Components table: path → provenance_id → source
   - Only use patterns with status `active` in `references/provenance.md`
8. If Impeccable is installed: `critique` → `audit` → `polish`; run `npx impeccable detect` on UI paths or the local URL when possible.
9. Run `references/a11y-responsive.md`.
10. Gate on **UI definition of done** (`references/definition-of-done.md`). Get user sign-off before deep backend.
11. Create/update `context.md`, `decision.md`, `agents.md`. If Impeccable is present, sync product narrative into `PRODUCT.md` and after UI approval run document → `DESIGN.md`.

## Taste feedback (when the user rejects a look)

Trigger phrases: “remove this”, “never do that again”, “I don’t like X”, “stop using Y”.

1. Search project `agents.md` / `decision.md` for the component → resolve `provenance_id`.
2. If missing, search `references/provenance.md` by symptom (pill badges, glass everywhere, bounce on inputs, purple gradients, etc.).
3. Show the user: **source**, **skill file path**, **what it recommended**, and ask:
   - Remove from skill permanently?
   - Replace with an alternative (propose from preferred sources / `taste-memory.md`)?
   - One-off for this project only?
4. If they confirm a skill change: edit the skill reference, set the provenance row to `rejected` or `replaced`, append `references/taste-memory.md`, and install the replacement guidance.
5. Fix the current project UI to match.

## Hard rules

- Skip any provenance id with status `rejected`.
- Real product UI in heroes when the product has a UI; no abstract filler as the main visual.
- One job per section; strong primary vs secondary CTA.
- Cover loading, empty, and error states for interactive surfaces.
- Restyle installed catalog components to project tokens.
