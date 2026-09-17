"use client";

import { useMemo } from "react";
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

type Section = {
  key: FilterKey;
  title: string;
  facet: Facet;
  /** Label for the `unclear` bucket, or undefined when the facet has none. */
  missing?: string;
  note?: string;
  openByDefault?: boolean;
};

function regionFacet(regions: string[]): Facet {
  return {
    values: regions,
    labels: Object.fromEntries(regions.map((region) => [region, region])),
  };
}

export function FilterPanel({
  regions,
  showTitle = true,
}: {
  regions: string[];
  /** The mobile sheet supplies its own title, so it turns this one off. */
  showTitle?: boolean;
}) {
  const { params, patch, toggle } = useQueryNav();

  const sections: Section[] = useMemo(
    () => [
      {
        key: "vc",
        title: "VC relevance",
        facet: VC_RELEVANCE,
        missing: "Not assessed",
        note: "AI-assisted sourcing signal, not an investment recommendation.",
        openByDefault: true,
      },
      {
        key: "sector",
        title: "Parent sector",
        facet: PARENT_SECTOR,
        missing: "Not classified",
        openByDefault: true,
      },
      { key: "product", title: "Product type", facet: PRODUCT_TYPE, missing: "Not classified" },
      { key: "customer", title: "Customer model", facet: CUSTOMER_MODEL, missing: "Not classified" },
      { key: "region", title: "Location", facet: regionFacet(regions) },
      {
        key: "quality",
        title: "Homepage evidence",
        facet: FETCH_QUALITY,
        note: "How much homepage text the classification was based on.",
        openByDefault: true,
      },
    ],
    [regions],
  );

  const active = FILTER_KEYS.reduce(
    (total, key) => total + (params.get(key) ?? "").split(",").filter(Boolean).length,
    0,
  );

  return (
    <div className="pb-10">
      <div
        className={`flex items-center gap-2 ${showTitle ? "h-12 justify-between border-b border-line" : "justify-end pt-3"}`}
      >
        {showTitle ? (
          <h2 className="eyebrow text-ink-muted">Refine</h2>
        ) : null}
        {active > 0 ? (
          <button
            type="button"
            onClick={() => patch(Object.fromEntries(FILTER_KEYS.map((key) => [key, null])))}
            className="text-xs font-medium text-brand hover:underline hover:underline-offset-2"
          >
            Clear all ({active})
          </button>
        ) : null}
      </div>

      {sections.map((section) => {
        const selected = (params.get(section.key) ?? "").split(",").filter(Boolean);
        const options = [
          ...section.facet.values.map((value) => ({
            value,
            label: section.facet.labels[value],
            missing: false,
          })),
          ...(section.missing
            ? [{ value: UNCLEAR, label: section.missing, missing: true }]
            : []),
        ];
        return (
          <details
            key={section.key}
            open={section.openByDefault || selected.length > 0}
            className="group border-b border-line"
          >
            <summary className="flex cursor-pointer list-none items-center gap-2 py-3 text-[13px] font-semibold select-none marker:content-none">
              <svg
                aria-hidden
                viewBox="0 0 12 12"
                className="h-3 w-3 shrink-0 text-ink-faint transition-transform group-open:rotate-90"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.9"
              >
                <path d="m4.5 2.5 3.5 3.5-3.5 3.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {section.title}
              {selected.length > 0 ? (
                <span className="tnum ml-auto rounded-full bg-brand px-1.5 py-px text-2xs font-semibold text-white">
                  {selected.length}
                </span>
              ) : null}
            </summary>

            {section.note ? (
              <p className="mb-1.5 pl-5 text-2xs leading-snug text-ink-muted">{section.note}</p>
            ) : null}

            <ul className="pb-2.5 pl-5">
              {options.map((option) => {
                const isOn = selected.includes(option.value);
                return (
                  <li key={option.value}>
                    <button
                      type="button"
                      aria-pressed={isOn}
                      onClick={() => toggle(section.key, option.value)}
                      className="group/opt flex w-full items-start gap-2.5 rounded py-[5px] text-left"
                    >
                      <span
                        aria-hidden
                        className={`mt-[2px] flex h-[15px] w-[15px] shrink-0 items-center justify-center rounded-[4px] border transition-colors ${
                          isOn
                            ? "border-brand bg-brand"
                            : "border-line-strong bg-white group-hover/opt:border-ink-faint"
                        }`}
                      >
                        {isOn ? (
                          <svg viewBox="0 0 12 12" className="h-2.5 w-2.5 text-white" fill="none" stroke="currentColor" strokeWidth="2.4">
                            <path d="m2.5 6.2 2.4 2.4 4.6-5" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        ) : null}
                      </span>
                      <span
                        className={`text-[13px] leading-[1.35] ${
                          isOn ? "font-medium text-ink" : "text-ink-muted group-hover/opt:text-ink"
                        } ${option.missing ? "italic" : ""}`}
                      >
                        {option.label}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </details>
        );
      })}
    </div>
  );
}
