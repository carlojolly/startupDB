import { GlimpseLogo } from "@/components/glimpse-logo";
import Link from "next/link";
import { Suspense } from "react";
import { ActiveFilters } from "@/components/active-filters";
import { CompanyRow } from "@/components/company-row";
import { ExportCsvButton } from "@/components/export-csv-button";
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
import { PAGE_SIZE, SORTS } from "@/lib/model";
import {
  countActive,
  parseFilters,
  parsePage,
  parseSort,
  withParams,
} from "@/lib/search-params";

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

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(raw)) {
    const single = Array.isArray(value) ? value[0] : value;
    if (single) params.set(key, single);
  }

  const query = params.toString();
  const detailHref = (codiceFiscale: string) =>
    `/company/${codiceFiscale}${query ? `?${query}` : ""}`;

  const pastEnd = !rows.length && total > 0;
  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasQuery = Boolean(filters.q || countActive(filters));

  return (
    <div className="flex min-h-full flex-col">
      <SiteHeader />

      {/* First composition: brand + one line + the search instrument. */}
      <section className="atlas-field on-navy text-on-navy">
        <div className="mx-auto max-w-[1440px] px-4 pt-10 pb-10 sm:px-6 sm:pt-16 sm:pb-14">
          <div className="motion-rise flex items-center gap-3">
            <GlimpseLogo className="scale-[1.15] origin-left sm:scale-[1.35]" />
          </div>

          <h1 className="motion-rise motion-rise-delay-1 display mt-8 max-w-[16ch] text-[clamp(2.4rem,6vw,4.75rem)] leading-[0.95]">
            Survey Italy&rsquo;s&nbsp;startups.
          </h1>

          <p className="motion-rise motion-rise-delay-2 mt-4 max-w-xl text-[15px] leading-relaxed text-on-navy-muted sm:text-base">
            A living atlas of the innovative-startup registry — search by name,
            then cut by sector, product, customer, and VC signal.
          </p>

          <div className="motion-rise motion-rise-delay-3 relative mt-8 max-w-3xl">
            <Suspense>
              <SearchField variant="hero" />
            </Suspense>
          </div>

          <div className="motion-rule mt-10 h-px w-full max-w-3xl bg-brand/40" />

          <dl className="mt-6 flex flex-wrap gap-x-10 gap-y-4">
            <div>
              <dt className="eyebrow text-brand/80">In atlas</dt>
              <dd className="tnum display mt-1 text-2xl text-on-navy">
                {overview.companies.toLocaleString("en-GB")}
              </dd>
            </div>
            <div>
              <dt className="eyebrow text-on-navy-faint">High VC signal</dt>
              <dd className="tnum display mt-1 text-2xl text-on-navy">
                {overview.high.toLocaleString("en-GB")}
              </dd>
            </div>
            <div>
              <dt className="eyebrow text-on-navy-faint">Regions</dt>
              <dd className="tnum display mt-1 text-2xl text-on-navy">
                {overview.regions.toLocaleString("en-GB")}
              </dd>
            </div>
            <div>
              <dt className="eyebrow text-on-navy-faint">Homepages read</dt>
              <dd className="tnum display mt-1 text-2xl text-on-navy">
                {overview.verified.toLocaleString("en-GB")}
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <div
        id="results"
        className="on-navy relative z-30 border-y border-brand/20 bg-navy sm:sticky sm:top-14"
      >
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-2.5 px-4 py-3 sm:flex-nowrap sm:px-6">
          <Suspense>
            <div className="w-full min-w-0 sm:max-w-md sm:flex-1">
              <SearchField variant="bar" />
            </div>
            <div className="flex w-full items-center gap-2.5 sm:ml-auto sm:w-auto">
              <MobileFilters regions={regions} />
              <SortSelect />
            </div>
            <PendingBar />
          </Suspense>
        </div>
      </div>

      <div className="mx-auto w-full max-w-[1440px] flex-1">
        <div className="lg:grid lg:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="sticky top-[7.75rem] hidden h-[calc(100dvh-7.75rem)] overflow-y-auto border-r border-line bg-surface/40 px-5 lg:block">
            <Suspense>
              <FilterPanel regions={regions} />
            </Suspense>
          </aside>

          <main className="min-w-0">
            <Suspense>
              <ActiveFilters />
            </Suspense>

            <div className="z-20 flex flex-wrap items-center justify-between gap-3 border-b border-line bg-page/95 px-4 py-3.5 backdrop-blur sm:px-6 lg:sticky lg:top-[7.75rem]">
              <p className="text-[13px]">
                <span className="mono text-[11px] tracking-[0.12em] text-brand uppercase">
                  {hasQuery ? "Filtered plate" : "Full plate"}
                </span>
                <span className="mx-2 text-ink-faint" aria-hidden>
                  /
                </span>
                <span className="tnum display text-[15px]">
                  {total.toLocaleString("en-GB")}
                </span>{" "}
                {total === 1 ? "company" : "companies"}
                <span className="text-ink-muted">
                  {" "}
                  · {SORTS[sort].toLowerCase()}
                </span>
              </p>
              <Suspense>
                <ExportCsvButton count={total} />
              </Suspense>
            </div>

            <PendingDim>
              {rows.length ? (
                <div className="divide-y divide-line">
                  {rows.map((company, index) => (
                    <CompanyRow
                      key={company.codice_fiscale}
                      company={company}
                      href={detailHref(company.codice_fiscale)}
                      index={(page - 1) * PAGE_SIZE + index + 1}
                    />
                  ))}
                </div>
              ) : pastEnd ? (
                <div className="px-4 py-28 text-center sm:px-6">
                  <p className="eyebrow text-brand">Off the map</p>
                  <p className="display mt-3 text-xl">
                    This page is past the end of the results
                  </p>
                  <p className="mx-auto mt-3 max-w-sm text-[13px] text-ink-muted">
                    <span className="tnum">{total.toLocaleString("en-GB")}</span>{" "}
                    {total === 1 ? "company matches" : "companies match"}, on{" "}
                    <span className="tnum">{lastPage.toLocaleString("en-GB")}</span>{" "}
                    {lastPage === 1 ? "page" : "pages"}.{" "}
                    <Link
                      href={withParams(params, { page: null })}
                      className="text-brand underline underline-offset-4"
                    >
                      Return to plate 1
                    </Link>
                  </p>
                </div>
              ) : (
                <div className="px-4 py-28 text-center sm:px-6">
                  <p className="eyebrow text-brand">No fix</p>
                  <p className="display mt-3 text-xl">
                    No companies match these filters
                  </p>
                  <p className="mx-auto mt-3 max-w-sm text-[13px] text-ink-muted">
                    {filters.q
                      ? `No company name contains “${filters.q}”. Try a shorter part of the name.`
                      : countActive(filters)
                        ? "Remove a filter, or widen sector and product type."
                        : provenance
                          ? "The published tag run returned no companies."
                          : "The directory is being prepared. Check back soon."}
                  </p>
                </div>
              )}
            </PendingDim>

            <Pagination page={page} total={total} params={params} />
          </main>
        </div>
      </div>

      <footer className="border-t border-line bg-navy">
        <div className="mx-auto max-w-[1440px] px-4 py-10 text-2xs leading-relaxed text-ink-muted sm:px-6">
          <GlimpseLogo className="mb-5 opacity-90" />
          <p className="max-w-3xl">
            Registry data from{" "}
            <a
              href="https://startup.registroimprese.it"
              className="text-brand underline underline-offset-4"
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
                by{" "}
                <span className="mono text-ink">
                  tag run {provenance.run_id}
                </span>{" "}
                ({provenance.model})
              </>
            ) : null}
            , covering{" "}
            <span className="tnum text-ink">
              {overview.companies.toLocaleString("en-GB")}
            </span>{" "}
            companies with a usable website. Check homepage evidence before
            acting on a label.
          </p>
        </div>
      </footer>
    </div>
  );
}
