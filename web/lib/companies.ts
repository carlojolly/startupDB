import "server-only";
import { cache } from "react";
import { sql } from "./db";
import type { Company, Filters, Overview, Provenance, SortKey } from "./model";
import { PAGE_SIZE } from "./model";
import {
  FETCH_QUALITY_RANK,
  PARENT_SECTOR_RANK,
  VC_RELEVANCE_RANK,
} from "./taxonomy";

/**
 * One row per company: its current registry snapshot plus the tags from the
 * current tag run, pivoted. `array_agg(... ORDER BY id)` is what preserves the
 * pipeline's stored order for multi-value fields — the primary value first.
 */
const tagged = () => sql`
  WITH tagged AS (
    SELECT
      codice_fiscale,
      array_agg(tag_value ORDER BY id) FILTER (WHERE tag_type = 'parent_sector')  AS parent_sectors,
      array_agg(tag_value ORDER BY id) FILTER (WHERE tag_type = 'product_type')   AS product_types,
      array_agg(tag_value ORDER BY id) FILTER (WHERE tag_type = 'customer_model') AS customer_models,
      (array_agg(tag_value ORDER BY id) FILTER (WHERE tag_type = 'sector'))[1]              AS sector,
      (array_agg(tag_value ORDER BY id) FILTER (WHERE tag_type = 'one_line'))[1]            AS one_line,
      (array_agg(tag_value ORDER BY id) FILTER (WHERE tag_type = 'vc_relevance'))[1]        AS vc_relevance,
      (array_agg(tag_value ORDER BY id) FILTER (WHERE tag_type = 'vc_relevance_reason'))[1] AS vc_rationale,
      max(fetch_bucket)   AS fetch_quality,
      max(fetch_pass)     AS fetch_pass,
      max(homepage_chars) AS homepage_chars
    FROM current_company_tags
    GROUP BY codice_fiscale
  ),
  company AS (
    SELECT
      c.codice_fiscale, c.denominazione, c.comune, c.pv, c.provincia, c.regione,
      c.sito_internet_url, c.in_liquidazione,
      coalesce(t.parent_sectors,  '{}') AS parent_sectors,
      coalesce(t.product_types,   '{}') AS product_types,
      coalesce(t.customer_models, '{}') AS customer_models,
      t.sector, t.one_line, t.vc_relevance, t.vc_rationale,
      t.fetch_quality, t.fetch_pass, t.homepage_chars,
      array_position(${VC_RELEVANCE_RANK}::text[], t.vc_relevance)      AS vc_rank,
      array_position(${FETCH_QUALITY_RANK}::text[], t.fetch_quality)    AS evidence_rank,
      array_position(${PARENT_SECTOR_RANK}::text[], t.parent_sectors[1]) AS sector_rank
    FROM companies_current c
    JOIN tagged t USING (codice_fiscale)
  )
`;

// Every sort ends on the company name and then the fiscal code, so paging is
// stable even for the few dozen companies that share a registered name. Within
// whatever the reader asked to sort by, the strongest signal comes first: VC
// relevance, then homepage evidence — the same tie-break the default sort uses.
// NULLS LAST keeps companies with no recorded province out of the top of the
// location sort. Built fresh per query: a postgres.js fragment is consumed when
// it is nested.
const signal = () => sql`vc_rank, evidence_rank, denominazione, codice_fiscale`;

const ORDER_BY: Record<SortKey, () => ReturnType<typeof sql>> = {
  relevance: () => sql`ORDER BY ${signal()}`,
  name: () => sql`ORDER BY denominazione, codice_fiscale`,
  location: () =>
    sql`ORDER BY regione NULLS LAST, provincia NULLS LAST, comune NULLS LAST, ${signal()}`,
  sector: () =>
    sql`ORDER BY sector_rank NULLS LAST, sector NULLS LAST, ${signal()}`,
  evidence: () => sql`ORDER BY evidence_rank, vc_rank, denominazione, codice_fiscale`,
};

/**
 * `%`, `_` and `\` are pattern characters inside ILIKE. The reader means them
 * literally, and a pattern ending in a bare backslash is a Postgres error.
 */
function escapeLike(value: string): string {
  return value.replace(/[\\%_]/g, (char) => `\\${char}`);
}

function conditions(filters: Filters) {
  const parts = [];
  if (filters.q)
    parts.push(sql`denominazione ILIKE ${"%" + escapeLike(filters.q) + "%"}`);
  // Overlap: a company matches if any of its values is selected. Multi-value
  // companies therefore show up under both of their sectors.
  if (filters.sector.length)
    parts.push(sql`parent_sectors && ${filters.sector}::text[]`);
  if (filters.product.length)
    parts.push(sql`product_types && ${filters.product}::text[]`);
  if (filters.customer.length)
    parts.push(sql`customer_models && ${filters.customer}::text[]`);
  if (filters.vc.length)
    parts.push(sql`vc_relevance = ANY(${filters.vc}::text[])`);
  if (filters.quality.length)
    parts.push(sql`fetch_quality = ANY(${filters.quality}::text[])`);
  if (filters.region.length)
    parts.push(sql`regione = ANY(${filters.region}::text[])`);
  if (!parts.length) return sql``;
  return parts.reduce((all, part) => sql`${all} AND ${part}`, sql`WHERE true`);
}

export async function searchCompanies(
  filters: Filters,
  sort: SortKey,
  page: number,
): Promise<{ rows: Company[]; total: number }> {
  const rows = await sql<(Company & { total: number })[]>`
    ${tagged()}
    SELECT count(*) OVER () AS total, company.*
    FROM company
    ${conditions(filters)}
    ${ORDER_BY[sort]()}
    LIMIT ${PAGE_SIZE} OFFSET ${(page - 1) * PAGE_SIZE}
  `;
  if (!rows.length && page > 1) {
    // Past the last page: the window count above sees no rows, so count the
    // filtered set on its own rather than reporting a false zero.
    const [{ total }] = await sql<{ total: number }[]>`
      ${tagged()}
      SELECT count(*)::int AS total FROM company ${conditions(filters)}
    `;
    return { rows, total };
  }
  return { rows, total: rows.length ? Number(rows[0].total) : 0 };
}

// Cached so the page and its generateMetadata share one round trip.
export const getCompany = cache(
  async (codiceFiscale: string): Promise<Company | null> => {
    const rows = await sql<Company[]>`
      ${tagged()}
      SELECT * FROM company WHERE codice_fiscale = ${codiceFiscale}
    `;
    return rows[0] ?? null;
  },
);

/** The headline numbers, for the masthead. One query, four counts. */
export async function getOverview(): Promise<Overview> {
  const rows = await sql<Overview[]>`
    ${tagged()}
    SELECT
      count(*)::int                                          AS companies,
      count(*) FILTER (WHERE vc_relevance = 'high')::int      AS high,
      count(*) FILTER (WHERE fetch_quality = 'OK')::int       AS verified,
      count(DISTINCT regione)::int                            AS regions
    FROM company
  `;
  return rows[0];
}

/** Regions that actually have classified companies, largest first. */
export async function getRegions(): Promise<string[]> {
  const rows = await sql<{ regione: string }[]>`
    SELECT c.regione
    FROM companies_current c
    JOIN (SELECT DISTINCT codice_fiscale FROM current_company_tags) t
      USING (codice_fiscale)
    WHERE c.regione IS NOT NULL
    GROUP BY c.regione
    ORDER BY count(*) DESC, c.regione
  `;
  return rows.map((row) => row.regione);
}

/** What produced the tags on screen, so an analyst can see how old they are. */
export async function getProvenance(): Promise<Provenance | null> {
  const rows = await sql<Provenance[]>`
    SELECT r.id AS run_id, r.model, r.prompt_version, r.finished_at,
           count(DISTINCT t.codice_fiscale)::int AS companies
    FROM current_company_tags t
    JOIN tag_runs r ON r.id = t.run_id
    GROUP BY r.id, r.model, r.prompt_version, r.finished_at
  `;
  return rows[0] ?? null;
}
