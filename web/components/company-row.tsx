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

/** Items are separated by a trailing dot, so a wrapped line never starts with one. */
const META_LIST =
  "mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs leading-[1.6] " +
  "[&>span:not(:last-child)]:after:ml-2 [&>span:not(:last-child)]:after:text-ink-faint " +
  "[&>span:not(:last-child)]:after:content-['·']";

function PinIcon() {
  return (
    <svg viewBox="0 0 12 12" aria-hidden className="h-3 w-3 shrink-0 text-ink-faint" fill="none" stroke="currentColor" strokeWidth="1.3">
      <path d="M6 10.5S2.5 7.6 2.5 5a3.5 3.5 0 1 1 7 0c0 2.6-3.5 5.5-3.5 5.5Z" />
      <circle cx="6" cy="4.9" r="1.2" />
    </svg>
  );
}

export function CompanyRow({ company, href }: { company: Company; href: string }) {
  // Stored order is meaningful: the first value is the primary one.
  const sectors = labelled(company.parent_sectors, PARENT_SECTOR);
  const products = labelled(company.product_types, PRODUCT_TYPE);
  const customers = labelled(company.customer_models, CUSTOMER_MODEL);
  const place = placeOf(company);

  const meta: { key: string; text: string; lead?: boolean }[] = [];
  if (!isUnclear(company.sector)) {
    meta.push({ key: "sector", text: sentenceCase(company.sector!), lead: true });
  }
  if (sectors.length) meta.push({ key: "parent", text: sectors.join(" + ") });
  if (products.length) meta.push({ key: "product", text: products.join(" + ") });
  if (customers.length) meta.push({ key: "customer", text: customers.join(" + ") });

  return (
    <article className="border-b border-line last:border-b-0">
      <Link
        href={href}
        className="flex items-start gap-3.5 px-4 py-4 transition-colors hover:bg-surface sm:px-6"
      >
        <Monogram name={company.denominazione} seed={company.codice_fiscale} />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <h3 className="display text-[15px] leading-snug">{company.denominazione}</h3>
            {company.in_liquidazione ? (
              <span className="rounded px-1.5 py-px text-2xs font-semibold tracking-wide text-ink-muted uppercase ring-1 ring-inset ring-line-strong">
                In liquidazione
              </span>
            ) : null}
          </div>

          <p className="mt-1 line-clamp-2 text-[13px] leading-[1.5] text-ink-muted">
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

        <div className="flex shrink-0 flex-col items-end gap-2 pt-0.5">
          <RelevanceChip value={company.vc_relevance} />
          <EvidenceMeter value={company.fetch_quality} />
        </div>
      </Link>
    </article>
  );
}
