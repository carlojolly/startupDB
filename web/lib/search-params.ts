import { DEFAULT_SORT, isSortKey, type Filters, type SortKey } from "./model";

/** Query-string key for each filter facet. */
export const FILTER_KEYS = [
  "vc",
  "sector",
  "product",
  "customer",
  "region",
  "quality",
] as const;

export type FilterKey = (typeof FILTER_KEYS)[number];

export type RawParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value) ?? "";
}

/** `?vc=high,medium` -> `["high", "medium"]`. Empty entries are dropped. */
export function parseList(value: string | string[] | undefined): string[] {
  return first(value)
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

export function parseFilters(params: RawParams): Filters {
  return {
    q: first(params.q).trim().slice(0, 100),
    vc: parseList(params.vc),
    sector: parseList(params.sector),
    product: parseList(params.product),
    customer: parseList(params.customer),
    region: parseList(params.region),
    quality: parseList(params.quality),
  };
}

export function parseSort(params: RawParams): SortKey {
  const sort = first(params.sort);
  return isSortKey(sort) ? sort : DEFAULT_SORT;
}

export function parsePage(params: RawParams): number {
  const page = Number.parseInt(first(params.page), 10);
  return Number.isFinite(page) && page > 1 ? page : 1;
}

export function countActive(filters: Filters): number {
  return FILTER_KEYS.reduce((total, key) => total + filters[key].length, 0);
}

/**
 * Applies a patch to a query string. `null` removes a key, and any change
 * other than paging itself sends the reader back to page 1 — otherwise a
 * tighter filter can land on an empty page.
 */
export function withParams(
  current: URLSearchParams | ReadonlyURLSearchParamsLike,
  patch: Record<string, string | null>,
): string {
  const next = new URLSearchParams(current.toString());
  for (const [key, value] of Object.entries(patch)) {
    if (value === null || value === "") next.delete(key);
    else next.set(key, value);
  }
  if (!("page" in patch)) next.delete("page");
  const query = next.toString();
  return query ? `?${query}` : "?";
}

type ReadonlyURLSearchParamsLike = { toString(): string };
