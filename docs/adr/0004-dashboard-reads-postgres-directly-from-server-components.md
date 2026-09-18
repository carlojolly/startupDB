# ADR 0004 — The dashboard reads Postgres directly from server components; no API layer, no auth yet

Status: accepted (retroactively recorded 2026-09-18)

## Context

The dashboard is a read-only analyst view over the same database the pipeline
writes. It is used by a small team and, today, is not public.

## Decision

- Next.js server components call `web/lib/companies.ts` directly, which holds
  every SQL query and is guarded by `import "server-only"`. There are no route
  handlers, API routes or server actions.
- All list state (filters, sort, page, query) lives in the **URL**, so views
  are shareable and the back button works. Client components import only pure
  modules (`taxonomy`, `model`, `search-params`) and never touch env or DB.
- `web/lib/taxonomy.ts` is the single source of display labels and of SQL
  sort order (its arrays are passed to `array_position`).
- No authentication. The registry data is public; the classifications are
  not, so the deployment must sit behind host-level access control or a
  private URL. The README says so.

## Consequences

- Nothing trusts the client: every input is parameterised, so adding auth
  later is a middleware concern, not a re-securing of endpoints.
- The dashboard connects with the **same owner role as the pipeline**. Any
  future bug in a server component could write. A read-only role is the
  cheapest structural fix and is backlog item B1; do it before sharing a URL.
- The direct Supabase host is IPv6-only; deployments must use the pooler
  host. `db.ts` sets `prepare: false` so either pooler port works there.
- TLS to the database is encrypted but the certificate is not verified on
  either side (backlog B6).
