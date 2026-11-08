---
name: backend-engineering
description: Architecture-first backend and full-stack engineering for Claude Code and Cursor — schema, APIs, caching, rate limits, launch readiness, reusable engineer modes (MVP, audit, debug, optimize, refactor), and project docs (agents.md, decision.md, context.md). Use after UI is approved or when auditing, debugging, or scaling an existing backend.
---

# Backend Engineering

Use after screens are approved when possible. Read project docs first if they exist.

Read references on demand:

- `references/architecture-playbook.md` — design then minimal scalable implementation
- `references/performance-launch.md` — five launch failure modes (`source:user-notes`)
- `references/engineering-prompts.md` — mode procedures (`source:user-notes`)
- `references/project-docs-templates.md` — `agents.md` / `decision.md` / `context.md`
- `references/definition-of-done.md` — backend launch-ready gates

## Workflow (ordered)

1. Read `context.md`, `decision.md`, and `agents.md` if present. Do not strip the Components (provenance) table from `agents.md`.
2. Ask which **mode** applies (or infer): Build MVP · Audit · Debug · Optimize · Refactor · Design backend · AI engineering team. Follow `references/engineering-prompts.md`.
3. Design before bulk coding: system architecture, file structure, data flow, API design, database schema, caching strategy.
4. Implement the minimal production-minded version that can scale later.
5. Enforce launch readiness from `references/performance-launch.md`:
   - Indexes on filter/search columns
   - Cache hot, slow-changing reads
   - Optimized images
   - Rate limits on public endpoints
   - Load test before real traffic (or defer with a dated reason in `decision.md`)
6. Gate on **backend launch-ready** in `references/definition-of-done.md`.
7. Update docs: architecture map + agent allow/deny in `agents.md`; timestamped decisions in `decision.md`; product/how-it-works in `context.md`.

## Hard rules

- Preserve existing behavior when refactoring unless the user asks to change it.
- Do not guess on production bugs — verify assumptions, fix the root cause.
- Prefer clarity and separation of concerns over premature microservices.
- Never commit secrets; use env vars and document required names in `agents.md`.
