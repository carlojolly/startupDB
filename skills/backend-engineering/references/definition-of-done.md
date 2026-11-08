# Definition of done

## UI approved

Owned by `frontend-design`. Do not start deep backend until UI is approved or the user explicitly asks to parallelize. See `../../frontend-design/references/definition-of-done.md`.

## Backend launch-ready

**Source:** `source:user-notes` (+ this pack)

- [ ] Architecture written (diagram or clear breakdown in `agents.md` / docs)
- [ ] Indexes on every column the app filters or searches by
- [ ] Caching for hot, slow-changing reads
- [ ] Images served optimized (e.g. platform image optimization or CDN)
- [ ] Rate limiting on every public endpoint
- [ ] Load test run (k6 / Artillery) **or** deferred with dated reason in `decision.md`
- [ ] Secrets via env; required names listed in `agents.md`
- [ ] `context.md` / `decision.md` / `agents.md` updated (preserve Components provenance table)
- [ ] Critical paths have error handling and empty/loading behavior matching UI contracts
