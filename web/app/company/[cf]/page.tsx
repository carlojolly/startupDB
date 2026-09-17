import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { placeOf, sentenceCase } from "@/components/company-row";
import { Monogram } from "@/components/monogram";
import {
  EvidenceMeter,
  NotClassified,
  RelevanceChip,
  TagPill,
} from "@/components/signals";
import { SiteHeader } from "@/components/site-header";
import { getCompany, getProvenance } from "@/lib/companies";
import {
  CUSTOMER_MODEL,
  FETCH_QUALITY_MEANING,
  PARENT_SECTOR,
  PRODUCT_TYPE,
  isUnclear,
  labelled,
} from "@/lib/taxonomy";

export async function generateMetadata({
  params,
}: PageProps<"/company/[cf]">): Promise<Metadata> {
  const { cf } = await params;
  const company = await getCompany(cf);
  return {
    title: company
      ? `${company.denominazione} — VentureAtlas`
      : "Company not found",
  };
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-t border-line py-4 first:border-t-0 first:pt-0">
      <dt className="eyebrow text-ink-muted">{label}</dt>
      <dd className="mt-2 text-sm">{children}</dd>
    </div>
  );
}

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-line">
      <h2 className="eyebrow border-b border-line bg-surface px-4 py-2.5 text-ink-muted">
        {title}
      </h2>
      <div className="p-4">{children}</div>
    </section>
  );
}

function Values({ values }: { values: string[] }) {
  if (!values.length) return <NotClassified />;
  return (
    <span className="flex flex-wrap gap-1.5">
      {values.map((label, index) => (
        <TagPill key={label} emphasis={index === 0}>
          {label}
        </TagPill>
      ))}
    </span>
  );
}

export default async function CompanyPage({
  params,
  searchParams,
}: PageProps<"/company/[cf]">) {
  const [{ cf }, raw] = await Promise.all([params, searchParams]);
  const [company, provenance] = await Promise.all([
    getCompany(cf),
    getProvenance(),
  ]);
  if (!company) notFound();

  const back = new URLSearchParams();
  for (const [key, value] of Object.entries(raw)) {
    const single = Array.isArray(value) ? value[0] : value;
    if (single) back.set(key, single);
  }
  const backHref = `/${back.toString() ? `?${back.toString()}` : ""}`;

  const sectors = labelled(company.parent_sectors, PARENT_SECTOR);
  const products = labelled(company.product_types, PRODUCT_TYPE);
  const customers = labelled(company.customer_models, CUSTOMER_MODEL);
  const place = placeOf(company);
  const quality = company.fetch_quality ?? "";
  const multiValue =
    sectors.length > 1 || products.length > 1 || customers.length > 1;

  return (
    <div className="flex min-h-full flex-col">
      <SiteHeader provenance={provenance} />

      <section className="on-navy grid-field bg-navy text-on-navy">
        <div className="mx-auto max-w-[1040px] px-4 pt-6 pb-9 sm:px-6">
          <Link
            href={backHref}
            className="inline-flex items-center gap-1.5 text-[13px] text-on-navy-muted transition-colors hover:text-on-navy"
          >
            <svg
              aria-hidden
              viewBox="0 0 12 12"
              className="h-3 w-3"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.9"
            >
              <path
                d="M7.5 2.5 4 6l3.5 3.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Back to results
          </Link>

          <div className="mt-5 flex items-start gap-4">
            <Monogram
              name={company.denominazione}
              seed={company.codice_fiscale}
              size="lg"
            />

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
                <h1 className="display text-2xl leading-[1.15] sm:text-[30px]">
                  {company.denominazione}
                </h1>
                {company.in_liquidazione ? (
                  <span className="mt-1.5 rounded px-2 py-1 text-2xs font-semibold tracking-wide text-on-navy-muted uppercase ring-1 ring-inset ring-panel-line">
                    In liquidazione
                  </span>
                ) : null}
              </div>

              <p className="mt-2 text-sm text-on-navy-muted">
                {place ? (
                  <>
                    {place}
                    {company.regione && company.regione !== place
                      ? `, ${company.regione}`
                      : ""}
                  </>
                ) : (
                  <span className="text-on-navy-faint italic">
                    Location not recorded
                  </span>
                )}
                <span aria-hidden className="mx-2 text-on-navy-faint">
                  ·
                </span>
                <span className="tnum">C.F. {company.codice_fiscale}</span>
              </p>
            </div>

            <div className="hidden shrink-0 flex-col items-end gap-2.5 sm:flex">
              <RelevanceChip value={company.vc_relevance} onDark />
              <EvidenceMeter value={quality} onDark />
            </div>
          </div>

          <p className="mt-6 max-w-2xl text-[15px] leading-relaxed text-on-navy">
            {isUnclear(company.one_line) ? (
              <span className="text-on-navy-faint italic">
                No description — the homepage did not provide enough to
                classify.
              </span>
            ) : (
              company.one_line
            )}
          </p>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            {company.sito_internet_url ? (
              <a
                href={company.sito_internet_url}
                target="_blank"
                rel="noreferrer"
                // A dead homepage still gets a link — an analyst may want to look
                // for themselves — but not the emphasis of the primary action.
                className={`inline-flex h-10 items-center gap-2 rounded-lg px-4 text-[13px] font-semibold transition-colors ${
                  quality === "DEAD"
                    ? "border border-panel-line text-on-navy-muted hover:border-on-navy-faint hover:text-on-navy"
                    : "bg-brand-bright text-white hover:bg-brand"
                }`}
              >
                Open homepage
                <svg
                  aria-hidden
                  viewBox="0 0 12 12"
                  className="h-3 w-3"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                >
                  <path
                    d="M4 2h6v6M10 2 3 9"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </a>
            ) : (
              <span className="text-[13px] text-on-navy-faint italic">
                No homepage on record
              </span>
            )}
            {company.sito_internet_url ? (
              <span className="truncate text-[13px] text-on-navy-muted">
                {company.sito_internet_url.replace(/^https?:\/\//, "")}
              </span>
            ) : null}
            <span className="flex items-center gap-2.5 sm:hidden">
              <RelevanceChip value={company.vc_relevance} onDark />
              <EvidenceMeter value={quality} onDark />
            </span>
          </div>
        </div>
      </section>

      <div className="mx-auto w-full max-w-[1040px] flex-1 px-4 py-8 sm:px-6 sm:py-10">
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
          <dl>
            <Field label="Sector">
              {isUnclear(company.sector) ? (
                <NotClassified />
              ) : (
                <span className="display text-[17px]">
                  {sentenceCase(company.sector!)}
                </span>
              )}
            </Field>
            <Field label="Parent sector">
              <Values values={sectors} />
            </Field>
            <Field label="Product type">
              <Values values={products} />
            </Field>
            <Field label="Customer model">
              <Values values={customers} />
            </Field>

            {multiValue ? (
              <p className="border-t border-line pt-4 text-2xs text-ink-muted">
                Where two values are listed, the first is the primary one, as
                recorded by the pipeline.
              </p>
            ) : null}
          </dl>

          <div className="flex flex-col gap-5">
            <Panel title="VC relevance">
              <RelevanceChip value={company.vc_relevance} />
              <p className="mt-3 text-[13px] leading-relaxed">
                {isUnclear(company.vc_rationale) ? (
                  <NotClassified>No rationale recorded.</NotClassified>
                ) : (
                  company.vc_rationale
                )}
              </p>
              <p className="mt-3 border-t border-line pt-3 text-2xs leading-relaxed text-ink-muted">
                An AI-assisted sourcing signal generated from the homepage. It
                is not an investment recommendation and carries no confidence
                score.
              </p>
            </Panel>

            <Panel title="Homepage evidence">
              <EvidenceMeter value={quality} />
              <p className="mt-3 text-[13px] leading-relaxed">
                {FETCH_QUALITY_MEANING[quality] ??
                  FETCH_QUALITY_MEANING.unclear}
              </p>
              <dl className="tnum mt-3 border-t border-line pt-3 text-2xs text-ink-muted">
                <div className="flex justify-between gap-3 py-0.5">
                  <dt>Text captured</dt>
                  <dd>
                    {(company.homepage_chars ?? 0).toLocaleString("en-GB")}{" "}
                    chars
                  </dd>
                </div>
                <div className="flex justify-between gap-3 py-0.5">
                  <dt>Fetch pass</dt>
                  <dd>{company.fetch_pass ?? "—"}</dd>
                </div>
              </dl>
            </Panel>
          </div>
        </div>
      </div>

      <footer className="border-t border-line bg-surface">
        <div className="mx-auto max-w-[1040px] px-4 py-6 text-2xs leading-relaxed text-ink-muted sm:px-6">
          <p>
            Registry data from{" "}
            <a
              href="https://startup.registroimprese.it"
              className="text-brand underline underline-offset-2"
              target="_blank"
              rel="noreferrer"
            >
              startup.registroimprese.it
            </a>
            . Labels on this page were generated from the company&rsquo;s own
            homepage
            {provenance ? (
              <>
                {" "}
                by <span className="tnum">tag run {provenance.run_id}</span> (
                {provenance.model})
              </>
            ) : null}
            .
          </p>
        </div>
      </footer>
    </div>
  );
}
