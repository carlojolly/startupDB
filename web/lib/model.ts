/**
 * Shapes and constants shared by server queries and client controls.
 *
 * Kept apart from lib/companies.ts so that a client component can import a
 * sort key without dragging the database driver into the browser bundle.
 */

export const PAGE_SIZE = 50;

export type Company = {
  codice_fiscale: string;
  denominazione: string;
  comune: string | null;
  pv: string | null;
  provincia: string | null;
  regione: string | null;
  sito_internet_url: string | null;
  in_liquidazione: boolean;
  /** Stored order preserved: the first value is the primary one. */
  parent_sectors: string[];
  product_types: string[];
  customer_models: string[];
  sector: string | null;
  one_line: string | null;
  vc_relevance: string;
  vc_rationale: string | null;
  fetch_quality: string;
  fetch_pass: string | null;
  homepage_chars: number | null;
};

export type Filters = {
  q: string;
  vc: string[];
  sector: string[];
  product: string[];
  customer: string[];
  region: string[];
  quality: string[];
};

export const SORTS = {
  /** VC relevance first, stronger homepage evidence first within a level. */
  relevance: "Most relevant",
  name: "Company name",
  location: "Location",
  sector: "Sector",
  evidence: "Homepage evidence",
} as const;

export type SortKey = keyof typeof SORTS;

export const DEFAULT_SORT: SortKey = "relevance";

export function isSortKey(value: string | undefined): value is SortKey {
  return !!value && value in SORTS;
}

export type Overview = {
  companies: number;
  high: number;
  verified: number;
  regions: number;
};

export type Provenance = {
  run_id: number;
  model: string;
  prompt_version: string | null;
  finished_at: Date;
  companies: number;
};

/** Longest note the feedback box accepts; the table enforces the same bound. */
export const MAX_FEEDBACK = 4000;

export type FeedbackState =
  | { status: "idle" }
  | { status: "sent" }
  | { status: "error"; error: string };
