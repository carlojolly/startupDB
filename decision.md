# Decisions

Newest first. Design-skill trial decisions for Glimpse. Pipeline / data decisions stay documented in `docs/adr/` and `AGENTS.md`.

| When (ISO 8601 with offset) | Decision | Why | Alternatives rejected | source | provenance_id |
|-----------------------------|----------|-----|----------------------|--------|---------------|
| 2026-11-08T23:20:00+01:00 | Announce list refresh with a polite `aria-live` status in the command bar | Pending dim alone is visual; screen-reader users need the same in-flight state | Rely on `aria-busy` alone | source:our-skill | a11y.baseline |
| 2026-11-08T23:20:00+01:00 | Replace Inter body face with Source Sans 3; keep Urbanist for display / wordmark | Honors anti-Inter default on an Operate/Read directory; avoids other over-used “brand” defaults Impeccable lists; Urbanist stays the geometric brand face | Keep Inter; IBM Plex Sans; Geist as body | source:impeccable | anti.inter-everywhere |
| 2026-11-08T23:15:00+01:00 | Treat Glimpse as **app-ui**: route companions to Impeccable + craft checklist, not Taste Skill marketing flow | Product is a filterable directory, not a company marketing site | Full Taste Skill screen-by-screen marketing rebuild | source:our-skill | workflow.screen-first |
| 2026-11-08T23:15:00+01:00 | Install `/frontend-design` + `/backend-engineering` under `skills/` with Cursor/Claude/Agents links; install Impeccable engine locally (bin gitignored) | Lets agents load the pack in-repo for this trial | Symlink only to external clone; skip companions | source:our-skill | workflow.project-docs |
| 2026-11-08T23:10:00+01:00 | Keep existing charcoal + yellow token system | Already a tight non-purple palette that matches brand mark | FluxEdit dual-glow / Palmatech glass / purple AI defaults | source:user-mockups | craft.tight-palette |
| 2026-11-08T23:10:00+01:00 | Do not overwrite uppercase `AGENTS.md`; add lowercase `agents.md` for design provenance | Repo already uses `AGENTS.md` as the pipeline operator contract | Merge into one file; rename existing | source:our-skill | workflow.project-docs |
