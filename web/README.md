# Glimpse — dashboard

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

Charcoal surfaces, white type and the yellow Glint symbol define Glimpse.
Selected controls use yellow with dark text; other signals stay neutral.
Urbanist Medium supplies the wordmark and display type, with Inter for UI and data.
The directory keeps search and sorting sticky, collapses filters into a mobile
sheet, and wraps row signals below company information on narrow screens.

## Layout

```
app/                  the list (page.tsx) and the detail view (company/[cf])
components/           list rows, filters, search, the signal chips
lib/db.ts             the one place that opens a connection
lib/companies.ts      every SQL query the dashboard runs
lib/model.ts          shapes and sort keys shared with client components
lib/taxonomy.ts       the tag vocabularies, their labels and their order
components/monogram.tsx  neutral initials for a company with no logo
lib/search-params.ts  URL <-> filter state
```

Filter, sort and page state lives entirely in the URL, so a filtered view is
shareable and the back button works. `lib/taxonomy.ts` is the single source of
truth for both display labels and sort order — the ranking arrays it exports
are passed straight into SQL `array_position`, so the database sorts in exactly
the order that file declares.

See the root README's "The dashboard" section for the data model and the
decisions behind how `unclear` and homepage evidence are presented.
