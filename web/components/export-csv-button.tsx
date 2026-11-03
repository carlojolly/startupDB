"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { exportFilteredCompanies } from "@/app/actions";

export function ExportCsvButton({ count }: { count: number }) {
  const params = useSearchParams();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function download() {
    if (pending || count === 0) return;
    setPending(true);
    setError("");
    try {
      const csv = await exportFilteredCompanies(params.toString());
      const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `glimpse-companies-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (cause) {
      console.error("CSV export failed:", cause);
      setError("Export failed. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={download}
        disabled={pending || count === 0}
        aria-label={`Export ${count.toLocaleString("en-GB")} filtered companies as CSV`}
        className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-line bg-surface px-3 text-xs font-semibold text-ink transition-colors hover:border-brand hover:text-brand disabled:cursor-not-allowed disabled:opacity-50"
      >
        <svg aria-hidden viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M8 2v8m0 0 3-3m-3 3L5 7M2.5 11.5v2h11v-2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {pending ? "Exporting…" : "Export CSV"}
      </button>
      {error ? <span role="alert" className="text-2xs text-red-700">{error}</span> : null}
    </div>
  );
}
