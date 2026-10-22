"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { FILTER_KEYS } from "@/lib/search-params";
import { FilterPanel } from "./filter-panel";
import { useQueryNav } from "./query-nav";

/** The filter sidebar, as a full-height sheet on screens too narrow for it. */
export function MobileFilters({ regions }: { regions: string[] }) {
  const { params } = useQueryNav();
  const [open, setOpen] = useState(false);

  const active = FILTER_KEYS.reduce(
    (total, key) => total + (params.get(key) ?? "").split(",").filter(Boolean).length,
    0,
  );

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-expanded={open}
        className="flex h-11 flex-1 items-center justify-center gap-2 rounded-lg border border-panel-line bg-panel px-3.5 text-sm text-on-navy hover:border-on-navy-faint sm:flex-none lg:hidden"
      >
        <svg aria-hidden viewBox="0 0 16 16" className="h-4 w-4 text-on-navy-muted" fill="none" stroke="currentColor" strokeWidth="1.7">
          <path d="M2 4h12M4.5 8h7M7 12h2" strokeLinecap="round" />
        </svg>
        Filters
        {active > 0 ? (
          <span className="tnum rounded-full bg-brand px-1.5 py-px text-2xs font-semibold text-navy">
            {active}
          </span>
        ) : null}
      </button>

      {/* Portalled to the body: the sticky command bar this button sits in creates
          a stacking context, which would otherwise trap the sheet beneath it. */}
      {open
        ? createPortal(
            <div className="fixed inset-0 z-50 lg:hidden">
              <button
                type="button"
                aria-label="Close filters"
                onClick={() => setOpen(false)}
                className="absolute inset-0 bg-navy/60"
              />
              <div className="absolute inset-y-0 right-0 flex w-[min(340px,88vw)] flex-col bg-page shadow-2xl">
                <div className="flex h-14 shrink-0 items-center justify-between border-b border-line px-4">
                  <span className="display text-[15px]">Refine</span>
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    className="-mr-1 flex h-9 w-9 items-center justify-center rounded-lg text-ink-muted hover:bg-surface hover:text-ink"
                    aria-label="Close filters"
                  >
                    <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8">
                      <path d="m4 4 8 8M12 4l-8 8" strokeLinecap="round" />
                    </svg>
                  </button>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto px-4">
                  <FilterPanel regions={regions} showTitle={false} />
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
