# Architecture playbook

**Source:** `source:our-skill` (+ `source:user-notes` launch constraints)

## Before coding

Produce a short written design covering:

1. **System architecture** — clients, API, data stores, jobs, third parties  
2. **Component / folder structure** — where code will live (feeds `agents.md`)  
3. **Data flow** — request → validation → domain → persistence → response  
4. **API design** — resources, auth, errors, pagination  
5. **Database schema** — tables/collections, indexes on filter/search columns  
6. **Caching strategy** — what is cached, TTL, invalidation  
7. **Rate limiting** — public endpoints, limits, identity key  
8. **Observability** — structured logs, error reporting (name tools in `agents.md`)

Prefer one deployable app until scale demands splits.

## Minimal scalable implementation

- Start monolithic modular (clear modules/packages), not distributed by default
- Explicit module boundaries; avoid circular imports
- Migrations for schema changes
- Env-based config; never commit secrets
- Match UI contracts from approved screens / `context.md`

## After implementation

- Update `agents.md` (map + allow/deny + keep Components provenance)
- Append `decision.md` with timestamps
- Refresh `context.md` how-it-works
- Run launch-ready checklist in `definition-of-done.md`
