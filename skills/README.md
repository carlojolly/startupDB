# Agent skills (design pack)

Installed from [carlojolly/my-design-code](https://github.com/carlojolly/my-design-code) for UI-first work on Glimpse.

| Skill | Path | Use |
|-------|------|-----|
| `/frontend-design` | `skills/frontend-design` | Screen inventory, companions, unslop, a11y, provenance, taste feedback |
| `/backend-engineering` | `skills/backend-engineering` | Architecture / API / schema after UI sign-off |

Linked from `.cursor/skills/`, `.claude/skills/`, and `.agents/skills/`.

Impeccable is installed under `.cursor/skills/impeccable` (and `.claude/…`). Re-download the engine after clone:

```bash
npx impeccable install --providers=cursor,claude --scope=project
```

Product design docs for this trial: `context.md`, `decision.md`, `agents.md`, `docs/screen-inventory.md`.
