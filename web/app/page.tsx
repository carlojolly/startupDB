import Image from "next/image";
import { Suspense } from "react";
import wordmarkDark from "@/public/venture-atlas-dark.png";
import { ActiveFilters } from "@/components/active-filters";
import { CompanyRow } from "@/components/company-row";
import { FilterPanel } from "@/components/filter-panel";
import { MobileFilters } from "@/components/mobile-filters";
import { Pagination } from "@/components/pagination";
import { PendingBar, PendingDim } from "@/components/pending";
import { SearchField } from "@/components/search-field";
import { SiteHeader } from "@/components/site-header";
import { SortSelect } from "@/components/sort-select";
import {
  getOverview,
  getProvenance,
  getRegions,
  searchCompanies,
} from "@/lib/companies";
import { SORTS } from "@/lib/model";
import {
  countActive,
  parseFilters,
  parsePage,
  parseSort,
} from "@/lib/search-params";

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="tnum display text-xl leading-none text-on-navy sm:text-2xl">
        {value.toLocaleString("en-GB")}
      </span>
      <span className="text-2xs tracking-[0.08em] text-on-navy-muted uppercase">
        {label}
      </span>
    </div>
  );
}

export default async function DashboardPage({ searchParams }: PageProps<"/">) {
  const raw = await searchParams;
  const filters = parseFilters(raw);
  const sort = parseSort(raw);
  const page = parsePage(raw);

  const [{ rows, total }, regions, provenance, overview] = await Promise.all([
    searchCompanies(filters, sort, page),
    getRegions(),
    getProvenance(),
    getOverview(),
  ]);

  // Rebuilt rather than passed through, so links carry exactly the keys we own.
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(raw)) {
    const single = Array.isArray(value) ? value[0] : value;
    if (single) params.set(key, single);
  }

  // The detail view keeps the query string so "back to results" returns to the
  // same filtered, sorted page.
  const query = params.toString();
  const detailHref = (codiceFiscale: string) =>
    `/company/${codiceFiscale}${query ? `?${query}` : ""}`;

  return (
    <div className="flex min-h-full flex-col">
      <SiteHeader provenance={provenance} />

      {/* Masthead. Dark carries the identity and the search; the data below it
          stays light, which is where dense small text has to be readable. */}
      <section className="on-navy grid-field bg-navy text-on-navy">
        <div className="mx-auto max-w-[1560px] px-4 pt-7 pb-6 sm:px-6 sm:pt-10 sm:pb-8">
          <p className="eyebrow text-amber">
            Italian innovative-startup registry
          </p>
          <h1 className="display mt-3 max-w-3xl text-[27px] leading-[1.1] sm:text-[44px] sm:leading-[1.08]">
            Every innovative startup in Italy, read off its own homepage.
          </h1>
          <p className="mt-3 max-w-2xl text-[13.5px] leading-relaxed text-on-navy-muted sm:mt-4 sm:text-[15px]">
            Sector, product, customer model and VC relevance, classified for the
            whole registry — with the evidence each label was built on shown
            next to it.
          </p>
          <div className="mt-6 flex flex-wrap gap-x-8 gap-y-4 border-t border-panel-line pt-5 sm:mt-8 sm:gap-x-10 sm:gap-y-5 sm:pt-6">
            <Stat value={overview.companies} label="Companies classified" />
            <Stat value={overview.high} label="High VC relevance" />
            <Stat value={overview.verified} label="Homepages read in full" />
            <Stat value={overview.regions} label="Regions" />
          </div>
        </div>
      </section>

      {/* Sticky command bar: reads as part of the masthead at rest, and stays
          within reach once the results scroll. */}
      <div className="on-navy z-30 border-b border-panel-line bg-navy sm:sticky sm:top-14">
        <div className="mx-auto flex max-w-[1560px] flex-wrap items-center gap-2.5 px-4 py-3 sm:flex-nowrap sm:px-6">
          <Suspense>
            <div className="w-full min-w-0 sm:max-w-xl sm:flex-1">
              <SearchField />
            </div>
            <div className="flex w-full items-center gap-2.5 sm:ml-auto sm:w-auto">
              <MobileFilters regions={regions} />
              <SortSelect />
            </div>
            <PendingBar />
          </Suspense>
        </div>
      </div>

      <div className="mx-auto w-full max-w-[1560px] flex-1">
        <div className="lg:grid lg:grid-cols-[288px_minmax(0,1fr)]">
          <aside className="sticky top-[124px] hidden h-[calc(100dvh-124px)] overflow-y-auto border-r border-line px-5 lg:block">
            <Suspense>
              <FilterPanel regions={regions} />
            </Suspense>
          </aside>

          <main className="min-w-0">
            <Suspense>
              <ActiveFilters />
            </Suspense>

            <div className="z-20 border-b border-line bg-page px-4 py-3.5 sm:px-6 lg:sticky lg:top-[124px]">
              <p className="text-[13px]">
                <span className="tnum display text-[15px]">
                  {total.toLocaleString("en-GB")}
                </span>{" "}
                {total === 1 ? "company" : "companies"}
                <span className="text-ink-muted">
                  {" "}
                  · sorted by {SORTS[sort].toLowerCase()}
                </span>
              </p>
            </div>

            <PendingDim>
              {rows.length ? (
                <div>
                  {rows.map((company) => (
                    <CompanyRow
                      key={company.codice_fiscale}
                      company={company}
                      href={detailHref(company.codice_fiscale)}
                    />
                  ))}
                </div>
              ) : (
                <div className="px-4 py-24 text-center sm:px-6">
                  <p className="display text-[17px]">
                    No companies match these filters
                  </p>
                  <p className="mx-auto mt-2 max-w-sm text-[13px] text-ink-muted">
                    {filters.q
                      ? `No company name contains “${filters.q}”. Try a shorter part of the name.`
                      : countActive(filters)
                        ? "Try removing a filter, or widening the sector and product type."
                        : "The tag run behind this view returned no companies."}
                  </p>
                </div>
              )}
            </PendingDim>

            <Pagination page={page} total={total} params={params} />
          </main>
        </div>
      </div>

      <footer className="border-t border-line bg-surface">
        <div className="mx-auto max-w-[1560px] px-4 py-8 text-2xs leading-relaxed text-ink-muted sm:px-6">
          <Image
            src={wordmarkDark}
            alt="VentureAtlas"
            sizes="140px"
            className="mb-4 h-4 w-auto"
          />
          <p className="max-w-3xl">
            Registry data from{" "}
            <a
              href="https://startup.registroimprese.it"
              className="text-brand underline underline-offset-2"
              target="_blank"
              rel="noreferrer"
            >
              startup.registroimprese.it
            </a>
            . Sector, product, customer and VC-relevance labels are generated
            from each company&rsquo;s homepage
            {provenance ? (
              <>
                {" "}
                by <span className="tnum">tag run {provenance.run_id}</span> (
                {provenance.model})
              </>
            ) : null}
            , and cover the{" "}
            <span className="tnum">
              {overview.companies.toLocaleString("en-GB")}
            </span>{" "}
            registry companies with a usable website. Check the homepage
            evidence before acting on a label.
          </p>
        </div>
      </footer>
    </div>
  );
}
