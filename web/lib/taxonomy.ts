/**
 * The closed vocabularies the tagging pipeline writes, and the labels the
 * dashboard shows for them.
 *
 * Source of truth for the codes: docs/tagging-contract-v5.md. Array order here
 * is also the display and sort order, so changing it changes both.
 */

export const UNCLEAR = "unclear";

export type Facet = {
  /** Vocabulary values, in display order. `unclear` is deliberately absent. */
  readonly values: readonly string[];
  readonly labels: Readonly<Record<string, string>>;
};

function facet(entries: readonly (readonly [string, string])[]): Facet {
  return {
    values: entries.map(([value]) => value),
    labels: Object.fromEntries(entries),
  };
}

/** The industry the customer operates in. One or two values per company. */
export const PARENT_SECTOR = facet([
  ["arts_culture_heritage", "Arts, culture & heritage"],
  ["business_software", "Business software"],
  ["climate_energy_circular", "Climate, energy & circular"],
  ["education_workforce", "Education & workforce"],
  ["financial_services_insurance", "Financial services & insurance"],
  ["food_agriculture", "Food & agriculture"],
  ["government_legal_regulatory", "Government, legal & regulatory"],
  ["health_life_sciences", "Health & life sciences"],
  ["hospitality_travel_food_service", "Hospitality, travel & food service"],
  ["industrial_manufacturing_robotics", "Industrial, manufacturing & robotics"],
  ["media_entertainment_gaming_sports", "Media, entertainment, gaming & sport"],
  ["mobility_logistics_supply_chain", "Mobility, logistics & supply chain"],
  [
    "real_estate_construction_smart_cities",
    "Real estate, construction & smart cities",
  ],
  ["retail_commerce_consumer", "Retail, commerce & consumer"],
  ["security_defense_aerospace", "Security, defence & aerospace"],
  ["telecom_cloud_infrastructure", "Telecom & cloud infrastructure"],
  // "other" means understood but outside the taxonomy, so it sorts last among
  // the real values rather than alphabetically in the middle.
  ["other", "Other"],
]);

/** What the company sells. One or two values per company. */
export const PRODUCT_TYPE = facet([
  ["software_product", "Software product"],
  ["marketplace", "Marketplace"],
  ["tech_enabled_service", "Tech-enabled service"],
  ["professional_services", "Professional services"],
  ["hardware_device", "Hardware device"],
  ["physical_product_material", "Physical product or material"],
  ["biotech_pharma_product", "Biotech or pharma product"],
  ["infrastructure_project", "Infrastructure project"],
  ["research_ip_licensing", "Research & IP licensing"],
]);

/** Who pays. One or two values per company. */
export const CUSTOMER_MODEL = facet([
  ["b2b", "B2B"],
  ["b2c", "B2C"],
  ["b2g", "B2G — public sector"],
  ["b2b2c", "B2B2C"],
]);

/** Strongest signal first — this is also the default ranking. */
export const VC_RELEVANCE = facet([
  ["high", "High"],
  ["medium", "Medium"],
  ["low", "Low"],
]);

/** How much homepage text the classification was actually based on. */
export const FETCH_QUALITY = facet([
  ["OK", "OK"],
  ["THIN", "THIN"],
  ["DEAD", "DEAD"],
]);

export const FETCH_QUALITY_MEANING: Record<string, string> = {
  OK: "Homepage read in full — the classification had real text to work from.",
  THIN: "Homepage returned very little text — treat the classification as weak.",
  DEAD: "Homepage could not be reached — nothing was classified from the site.",
  [UNCLEAR]: "No fetch was recorded.",
};

export const FETCH_QUALITY_SHORT: Record<string, string> = {
  OK: "Full homepage text",
  THIN: "Very little text",
  DEAD: "Homepage unreachable",
};

/**
 * Ranking arrays passed straight to SQL `array_position`, so the database
 * sorts in exactly the order this file declares. `unclear` always ranks last:
 * it is missing information, not a level.
 */
export const VC_RELEVANCE_RANK = [...VC_RELEVANCE.values, UNCLEAR];
export const FETCH_QUALITY_RANK = [...FETCH_QUALITY.values, UNCLEAR];
export const PARENT_SECTOR_RANK = [...PARENT_SECTOR.values, UNCLEAR];

/** True when the pipeline declined to classify — render as missing, never as a value. */
export function isUnclear(value: string | null | undefined): boolean {
  return !value || value === UNCLEAR;
}

/** Drops `unclear` and maps the rest to labels, keeping the stored order. */
export function labelled(values: readonly string[] | null, f: Facet): string[] {
  return (values ?? [])
    .filter((v) => !isUnclear(v))
    .map((v) => f.labels[v] ?? v);
}
