"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryNav } from "./query-nav";

/**
 * Company-name search. Debounced so typing does not fire a query per keystroke,
 * and kept in sync when the URL changes from elsewhere (back button, clear-all).
 */
export function SearchField({
  variant = "bar",
}: {
  /** `hero` is the primary discovery instrument on the atlas landing. */
  variant?: "bar" | "hero";
}) {
  const { params, patch } = useQueryNav();
  const fromUrl = params.get("q") ?? "";
  const [value, setValue] = useState(fromUrl);
  const latest = useRef(fromUrl);
  const hero = variant === "hero";

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
    <div className={`search-shell relative w-full border ${hero ? "border-brand/35 bg-navy/60" : "border-panel-line bg-panel"}`}>
      <svg
        aria-hidden
        viewBox="0 0 16 16"
        className={`pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-brand ${hero ? "h-5 w-5" : "h-4 w-4"}`}
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
        placeholder={hero ? "Find a company by name…" : "Search by name…"}
        aria-label="Search by company name"
        className={`w-full bg-transparent text-ink placeholder:text-ink-faint focus:outline-none focus-visible:outline-none [&::-webkit-search-cancel-button]:hidden ${
          hero
            ? "h-16 pr-12 pl-12 text-lg sm:h-[4.25rem] sm:text-xl"
            : "h-11 pr-10 pl-11 text-sm"
        }`}
      />
      {value ? (
        <button
          type="button"
          onClick={() => setValue("")}
          aria-label="Clear search"
          className="absolute top-1/2 right-3 flex h-8 w-8 -translate-y-1/2 items-center justify-center text-ink-faint hover:bg-brand/15 hover:text-brand"
        >
          <svg viewBox="0 0 12 12" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="m3 3 6 6M9 3l-6 6" strokeLinecap="round" />
          </svg>
        </button>
      ) : null}
      {hero ? (
        <>
          <span className="atlas-corner atlas-corner-tl" aria-hidden />
          <span className="atlas-corner atlas-corner-tr" aria-hidden />
          <span className="atlas-corner atlas-corner-bl" aria-hidden />
          <span className="atlas-corner atlas-corner-br" aria-hidden />
        </>
      ) : null}
    </div>
  );
}
