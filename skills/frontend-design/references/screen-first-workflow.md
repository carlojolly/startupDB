# Screen-first workflow

**Source:** `source:our-skill` · provenance: `workflow.screen-first`, `workflow.project-docs`

Goal: ship apps faster with Claude Code / Cursor by locking UI before deep backend.

## Steps

1. **Create a GitHub (or forge) project** and connect it to Claude Code / Cursor.
2. **Build the UI first.** Create every screen in the inventory. Iterate until the user is happy. Defer deep backend, auth complexity, and premature infrastructure.
3. Use companions as routed in `companion-stack.md` (Taste Skill / shadcn / 21st / motion / Impeccable).
4. Tag provenance in `decision.md` and `agents.md` while building.
5. Pass UI definition of done (`definition-of-done.md`) including a11y + checklist.
6. On the repo root, create three markdown files (templates in backend skill):

| File | Purpose |
|------|---------|
| `agents.md` | Where code lives; what agents may / may not do; Components provenance table |
| `decision.md` | Every decision with timestamps + `source:` + `provenance_id:` |
| `context.md` | What the app does, who it is for, how it works |

7. Hand off to `/backend-engineering` for architecture and implementation that matches the approved screens.
8. If Impeccable is installed: `/impeccable init` / `document` so `PRODUCT.md` and `DESIGN.md` stay aligned with `context.md`.

## Agent boundaries during UI phase

**Allowed:** screens, components, design tokens, mock/fixture data, client routing, empty/loading/error states.  
**Avoid unless asked:** production DB schema migrations, payment providers, multi-region infra, rewriting approved screens without inventory update.
