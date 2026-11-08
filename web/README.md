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

**Night atlas** direction: charcoal field, yellow Glint mark and grid/index
language. Urbanist for the wordmark and display type; Source Sans 3 for UI
and plate/code labels (tabular nums — no typewriter mono). Search is the hero
instrument; company rows read as numbered plates; detail pages are dossiers
with corner ticks. Sticky filters/sort remain; mobile uses a filter sheet.

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

The results header has an **Export CSV** button. It downloads every company
matching the current search and filters in the current sort order, including
results on later pages. The CSV includes the registry identifier, location,
website, AI tags, VC signal and homepage evidence quality. It uses UTF-8 with a
BOM; when opening it in a spreadsheet, import `codice_fiscale` as text to keep
leading zeros. The server action shares the dashboard query and does not add a
new API route. Run its offline CSV test with `npm test`.

See the root README's "The dashboard" section for the data model and the
decisions behind how `unclear` and homepage evidence are presented.
