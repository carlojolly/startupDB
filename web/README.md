# VentureAtlas — dashboard

The analyst-facing view of the Italian innovative-startup database. Read-only:
it queries the same Postgres the Python pipeline writes to and changes nothing.

```bash
npm install
npm run dev     # http://localhost:3000
```

`DATABASE_URL` comes from the repo-root `.env`, the same file the Python
scripts use. Override it through the environment or `web/.env.local`.

| | |
|---|---|
| `npm run dev` | dev server |
| `npm run build` / `npm start` | production build and serve |
| `npm run lint` | eslint |
| `npx tsc --noEmit` | typecheck |

## Design

Dark navy carries identity, navigation and search; the data surface below stays
light, because that is where dense small text lives. Blue is the interaction
colour — active filters, buttons, focus. Amber is spent on exactly two things:
the mark, and a `high` VC-relevance chip. Nothing else competes with it, so the
shortlist is visible from across the room.

Type is Plus Jakarta Sans for display (`.display`) and Inter for UI and data.

## Layout

```
app/                  the list (page.tsx) and the detail view (company/[cf])
components/           list rows, filters, search, the signal chips
lib/db.ts             the one place that opens a connection
lib/companies.ts      every SQL query the dashboard runs
lib/model.ts          shapes and sort keys shared with client components
lib/taxonomy.ts       the tag vocabularies, their labels and their order
components/monogram.tsx  initials and tint for a company with no logo
lib/search-params.ts  URL <-> filter state
```

Filter, sort and page state lives entirely in the URL, so a filtered view is
shareable and the back button works. `lib/taxonomy.ts` is the single source of
truth for both display labels and sort order — the ranking arrays it exports
are passed straight into SQL `array_position`, so the database sorts in exactly
the order that file declares.

See the root README's "The dashboard" section for the data model and the
decisions behind how `unclear` and homepage evidence are presented.
