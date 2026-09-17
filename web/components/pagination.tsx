import Link from "next/link";
import { PAGE_SIZE } from "@/lib/model";
import { withParams } from "@/lib/search-params";

export function Pagination({
  page,
  total,
  params,
}: {
  page: number;
  total: number;
  params: URLSearchParams;
}) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (pages <= 1) return null;

  const from = (page - 1) * PAGE_SIZE + 1;
  const to = Math.min(page * PAGE_SIZE, total);
  const href = (target: number) =>
    withParams(params, { page: target === 1 ? null : String(target) });

  const step =
    "flex h-9 items-center gap-1.5 rounded-lg border border-line bg-white px-3 text-[13px] font-medium transition-colors hover:border-line-strong hover:bg-surface";

  return (
    <nav
      aria-label="Pagination"
      className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-4 sm:px-6"
    >
      <p className="tnum text-[13px] text-ink-muted">
        Showing <span className="font-medium text-ink">{from.toLocaleString("en-GB")}–{to.toLocaleString("en-GB")}</span>{" "}
        of {total.toLocaleString("en-GB")}
      </p>
      <div className="flex items-center gap-2">
        {page > 1 ? (
          <Link href={href(page - 1)} className={step} scroll>
            Previous
          </Link>
        ) : (
          <span className={`${step} cursor-default text-ink-faint`} aria-disabled>
            Previous
          </span>
        )}
        <span className="tnum px-1 text-[13px] text-ink-muted">
          Page {page} of {pages.toLocaleString("en-GB")}
        </span>
        {page < pages ? (
          <Link href={href(page + 1)} className={step} scroll>
            Next
          </Link>
        ) : (
          <span className={`${step} cursor-default text-ink-faint`} aria-disabled>
            Next
          </span>
        )}
      </div>
    </nav>
  );
}
