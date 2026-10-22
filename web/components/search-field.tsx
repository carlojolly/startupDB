"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryNav } from "./query-nav";

/**
 * Company-name search. Debounced so typing does not fire a query per keystroke,
 * and kept in sync when the URL changes from elsewhere (back button, clear-all).
 */
export function SearchField() {
  const { params, patch } = useQueryNav();
  const fromUrl = params.get("q") ?? "";
  const [value, setValue] = useState(fromUrl);
  const latest = useRef(fromUrl);

  useEffect(() => {
    if (fromUrl !== latest.current) {
      latest.current = fromUrl;
      setValue(fromUrl);
    }
  }, [fromUrl]);

  useEffect(() => {
    if (value === latest.current) return;
    const timer = setTimeout(() => {
      latest.current = value;
      patch({ q: value.trim() || null });
    }, 250);
    return () => clearTimeout(timer);
  }, [value, patch]);

  return (
    <div className="relative w-full">
      <svg
        aria-hidden
        viewBox="0 0 16 16"
        className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-ink-faint"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
      >
        <circle cx="7" cy="7" r="4.5" />
        <path d="M10.5 10.5 14 14" strokeLinecap="round" />
      </svg>
      <input
        type="search"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Search companies by name…"
        aria-label="Search by company name"
        className="h-11 w-full rounded-lg border border-panel-line bg-panel pr-10 pl-10 text-sm text-ink placeholder:text-ink-faint focus:border-brand-bright focus:outline-none focus-visible:outline-none [&::-webkit-search-cancel-button]:hidden"
      />
      {value ? (
        <button
          type="button"
          onClick={() => setValue("")}
          aria-label="Clear search"
          className="absolute top-1/2 right-2.5 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded text-ink-faint hover:bg-surface-sunk hover:text-ink"
        >
          <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="m3 3 6 6M9 3l-6 6" strokeLinecap="round" />
          </svg>
        </button>
      ) : null}
    </div>
  );
}
