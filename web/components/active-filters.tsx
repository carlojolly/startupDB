"use client";

import {
  CUSTOMER_MODEL,
  FETCH_QUALITY,
  PARENT_SECTOR,
  PRODUCT_TYPE,
  UNCLEAR,
  VC_RELEVANCE,
  type Facet,
} from "@/lib/taxonomy";
import { FILTER_KEYS, type FilterKey } from "@/lib/search-params";
import { useQueryNav } from "./query-nav";

const FACETS: Record<Exclude<FilterKey, "region">, Facet> = {
  vc: VC_RELEVANCE,
  sector: PARENT_SECTOR,
  product: PRODUCT_TYPE,
  customer: CUSTOMER_MODEL,
  quality: FETCH_QUALITY,
};

const MISSING_LABEL: Partial<Record<FilterKey, string>> = {
  vc: "Not assessed",
  sector: "Not classified",
  product: "Not classified",
  customer: "Not classified",
};

const GROUP_LABEL: Record<FilterKey, string> = {
  vc: "Relevance",
  sector: "Sector",
  product: "Product",
  customer: "Customer",
  region: "Location",
  quality: "Evidence",
};

function labelFor(key: FilterKey, value: string): string {
  if (value === UNCLEAR) return MISSING_LABEL[key] ?? "Not classified";
  if (key === "region") return value;
  return FACETS[key].labels[value] ?? value;
}

function Dismiss({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="flex h-4 w-4 items-center justify-center rounded-full text-brand/60 hover:bg-brand hover:text-navy"
    >
      <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="m3 3 6 6M9 3l-6 6" strokeLinecap="round" />
      </svg>
    </button>
  );
}

const CHIP =
  "inline-flex items-center gap-1.5 rounded-md bg-brand-wash py-1 pr-1.5 pl-2.5 text-xs text-brand ring-1 ring-inset ring-brand-line";

/** Everything currently narrowing the list, each removable in one click. */
export function ActiveFilters() {
  const { params, patch, toggle } = useQueryNav();

  const chips = FILTER_KEYS.flatMap((key) =>
    (params.get(key) ?? "")
      .split(",")
      .filter(Boolean)
      .map((value) => ({ key, value })),
  );
  const query = params.get("q")?.trim();

  if (!chips.length && !query) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5 border-b border-line bg-surface px-4 py-2.5 sm:px-6">
      {query ? (
        <span className={CHIP}>
          <span className="opacity-70">Name</span>
          <span className="font-medium">{query}</span>
          <Dismiss onClick={() => patch({ q: null })} label={`Clear name search ${query}`} />
        </span>
      ) : null}

      {chips.map(({ key, value }) => (
        <span key={`${key}:${value}`} className={CHIP}>
          <span className="opacity-70">{GROUP_LABEL[key]}</span>
          <span className="font-medium">{labelFor(key, value)}</span>
          <Dismiss
            onClick={() => toggle(key, value)}
            label={`Remove filter ${labelFor(key, value)}`}
          />
        </span>
      ))}

      <button
        type="button"
        onClick={() =>
          patch({ ...Object.fromEntries(FILTER_KEYS.map((key) => [key, null])), q: null })
        }
        className="ml-1 text-xs text-ink-muted underline underline-offset-2 hover:text-ink"
      >
        Clear all
      </button>
    </div>
  );
}
