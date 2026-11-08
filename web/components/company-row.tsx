import Link from "next/link";
import type { Company } from "@/lib/model";
import {
  CUSTOMER_MODEL,
  PARENT_SECTOR,
  PRODUCT_TYPE,
  isUnclear,
  labelled,
} from "@/lib/taxonomy";
import { Monogram } from "./monogram";
import { EvidenceMeter, RelevanceChip } from "./signals";

export function sentenceCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

/** The registry stores town names shouting: MILANO, REGGIO NELL'EMILIA. */
export function titleCase(value: string): string {
  return value
    .toLocaleLowerCase("it")
    .replace(/(^|[\s'\-’/])([\p{L}])/gu, (_, before, letter) =>
      before + letter.toLocaleUpperCase("it"),
    );
}

export function placeOf(company: Company): string | null {
  if (!company.comune) return company.regione;
  const town = titleCase(company.comune);
  return company.pv ? `${town} (${company.pv})` : town;
}

const META_LIST =
  "mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs leading-[1.6] " +
  "[&>span:not(:last-child)]:after:ml-2 [&>span:not(:last-child)]:after:text-ink-faint " +
  "[&>span:not(:last-child)]:after:content-['·']";

function PinIcon() {
  return (
    <svg
      viewBox="0 0 12 12"
      aria-hidden
      className="h-3 w-3 shrink-0 text-brand/70"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.3"
    >
      <path d="M6 10.5S2.5 7.6 2.5 5a3.5 3.5 0 1 1 7 0c0 2.6-3.5 5.5-3.5 5.5Z" />
      <circle cx="6" cy="4.9" r="1.2" />
    </svg>
  );
}

export function CompanyRow({
  company,
  href,
  index,
}: {
  company: Company;
  href: string;
  index?: number;
}) {
  const sectors = labelled(company.parent_sectors, PARENT_SECTOR);
  const products = labelled(company.product_types, PRODUCT_TYPE);
  const customers = labelled(company.customer_models, CUSTOMER_MODEL);
  const place = placeOf(company);
  const hot = company.vc_relevance === "high";

  const meta: { key: string; text: string; lead?: boolean }[] = [];
  if (!isUnclear(company.sector)) {
    meta.push({ key: "sector", text: sentenceCase(company.sector!), lead: true });
  }
  if (sectors.length) meta.push({ key: "parent", text: sectors.join(" + ") });
  if (products.length) meta.push({ key: "product", text: products.join(" + ") });
  if (customers.length) meta.push({ key: "customer", text: customers.join(" + ") });

  return (
    <article className="group/row relative">
      <Link
        href={href}
        className="company-link items-start px-4 py-5 transition-colors hover:bg-brand/[0.04] sm:px-6 sm:py-6"
      >
        <span
          aria-hidden
          className={`mt-1 w-[3px] self-stretch ${hot ? "bg-brand" : "bg-line-strong group-hover/row:bg-brand/50"}`}
        />

        <div className="flex flex-col items-center gap-2">
          <Monogram name={company.denominazione} />
          {typeof index === "number" ? (
            <span className="mono text-[10px] tracking-wider text-ink-faint">
              {String(index).padStart(3, "0")}
            </span>
          ) : null}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
            <h3 className="display text-[17px] leading-snug text-ink group-hover/row:text-brand-bright sm:text-[18px]">
              {company.denominazione}
            </h3>
            {company.in_liquidazione ? (
              <span className="mono rounded-sm px-1.5 py-px text-[10px] tracking-[0.08em] text-ink-muted uppercase ring-1 ring-inset ring-line-strong">
                In liquidazione
              </span>
            ) : null}
          </div>

          <p className="mt-1.5 line-clamp-2 max-w-[62ch] text-[13.5px] leading-[1.55] text-ink-muted">
            {isUnclear(company.one_line) ? (
              <span className="text-ink-faint italic">
                No description — homepage did not provide enough to classify.
              </span>
            ) : (
              company.one_line
            )}
          </p>

          {meta.length || place ? (
            <p className={META_LIST}>
              {meta.map((item) => (
                <span
                  key={item.key}
                  className={item.lead ? "font-medium text-ink" : "text-ink-muted"}
                >
                  {item.text}
                </span>
              ))}
              {place ? (
                <span className="inline-flex items-center gap-1 text-ink-muted">
                  <PinIcon />
                  {place}
                </span>
              ) : null}
            </p>
          ) : null}
        </div>

        <div className="company-signals flex shrink-0 flex-col items-end gap-2.5 pt-1">
          <RelevanceChip value={company.vc_relevance} />
          <EvidenceMeter value={company.fetch_quality} />
        </div>
      </Link>
    </article>
  );
}
