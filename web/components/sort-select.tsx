"use client";

import { DEFAULT_SORT, SORTS } from "@/lib/model";
import { useQueryNav } from "./query-nav";

export function SortSelect() {
  const { params, patch } = useQueryNav();
  const value = params.get("sort") ?? DEFAULT_SORT;

  return (
    <label className="flex min-w-0 flex-1 items-center gap-2 sm:flex-none">
      <span className="hidden text-2xs tracking-[0.08em] text-on-navy-muted uppercase lg:inline">
        Sort
      </span>
      <span className="relative min-w-0 flex-1 sm:flex-none">
        <select
          value={value}
          onChange={(event) =>
            patch({ sort: event.target.value === DEFAULT_SORT ? null : event.target.value })
          }
          aria-label="Sort companies"
          className="h-11 w-full appearance-none border border-panel-line bg-panel py-0 pr-9 pl-3.5 text-sm text-on-navy hover:border-brand/50 focus:border-brand-bright focus:outline-none sm:w-auto"
        >
          {Object.entries(SORTS).map(([key, label]) => (
            <option key={key} value={key} className="text-ink">
              {label}
            </option>
          ))}
        </select>
        <svg
          aria-hidden
          viewBox="0 0 12 12"
          className="pointer-events-none absolute top-1/2 right-3 h-3 w-3 -translate-y-1/2 text-on-navy-muted"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
        >
          <path d="m2.5 4.5 3.5 3.5 3.5-3.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    </label>
  );
}
