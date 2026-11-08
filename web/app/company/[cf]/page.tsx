import { GlimpseLogo } from "@/components/glimpse-logo";
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
      ? `${company.denominazione} — Glimpse`
      : "Company not found",
  };
}

function Field({
  label,
  children,
  className = "",
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <dt className="eyebrow text-brand/70">{label}</dt>
      <dd className="mt-3 text-sm">{children}</dd>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <dd className="tnum display order-2 text-xl leading-none">{value}</dd>
      <dt className="order-1 mono text-[10px] tracking-[0.14em] text-ink-muted uppercase">
        {label}
      </dt>
    </div>
  );
}

function Dossier({
  title,
  signal,
  footer,
  className = "",
  children,
}: {
  title: string;
  signal?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={`relative border border-line bg-surface/50 ${className}`}>
      <span className="atlas-corner atlas-corner-tl" aria-hidden />
      <span className="atlas-corner atlas-corner-tr" aria-hidden />
      <span className="atlas-corner atlas-corner-bl" aria-hidden />
      <span className="atlas-corner atlas-corner-br" aria-hidden />
      <div className="flex min-h-[48px] items-center justify-between gap-4 border-b border-line px-5 py-3">
        <h2 className="eyebrow text-ink-muted">{title}</h2>
        {signal}
      </div>
      <div className="p-5 sm:p-6">{children}</div>
      {footer ? (
        <div className="border-t border-line px-5 py-3.5 text-2xs leading-relaxed text-ink-muted">
          {footer}
        </div>
      ) : null}
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
      <SiteHeader
        company={{
          name: company.denominazione,
          codiceFiscale: company.codice_fiscale,
        }}
      />

      <section className="atlas-field on-navy text-on-navy">
        <div className="mx-auto max-w-[1120px] px-4 pt-8 pb-12 sm:px-6">
          <Link
            href={backHref}
            className="inline-flex items-center gap-2 mono text-[11px] tracking-[0.14em] text-on-navy-muted uppercase transition-colors hover:text-brand"
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
            Return to plate
          </Link>

          <div className="motion-rise mt-8 flex items-start gap-5">
            <Monogram name={company.denominazione} size="lg" />

            <div className="min-w-0 flex-1">
              <p className="eyebrow text-brand">Company dossier</p>
              <div className="mt-3 flex flex-wrap items-start gap-x-3 gap-y-2">
                <h1 className="display text-[clamp(1.75rem,4vw,2.75rem)] leading-[1.05]">
                  {company.denominazione}
                </h1>
                {company.in_liquidazione ? (
                  <span className="mt-2 mono border border-panel-line px-2 py-1 text-[10px] tracking-[0.1em] text-on-navy-muted uppercase">
                    In liquidazione
                  </span>
                ) : null}
              </div>

              <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-on-navy-muted">
                <span>
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
                </span>
                <span aria-hidden className="text-brand/50">
                  /
                </span>
                <span className="mono text-[12px] tracking-wide">
                  C.F. {company.codice_fiscale}
                </span>
              </p>
            </div>
          </div>

          <p className="motion-rise motion-rise-delay-1 mt-8 max-w-2xl text-base leading-relaxed text-on-navy sm:text-[17px]">
            {isUnclear(company.one_line) ? (
              <span className="text-on-navy-faint italic">
                No description — the homepage did not provide enough to
                classify.
              </span>
            ) : (
              company.one_line
            )}
          </p>

          <div className="motion-rise motion-rise-delay-2 mt-8 flex flex-wrap items-center gap-4">
            {company.sito_internet_url ? (
              <a
                href={company.sito_internet_url}
                target="_blank"
                rel="noreferrer"
                className={`inline-flex h-12 items-center gap-2 px-5 text-[13px] font-semibold transition-colors ${
                  quality === "DEAD"
                    ? "border border-panel-line text-on-navy-muted hover:border-brand hover:text-brand"
                    : "bg-brand text-navy hover:bg-brand-bright"
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
              <span className="mono truncate text-[12px] text-on-navy-muted">
                {company.sito_internet_url.replace(/^https?:\/\//, "")}
              </span>
            ) : null}
          </div>
        </div>
      </section>

      <div className="mx-auto w-full max-w-[1120px] flex-1 px-4 py-8 sm:px-6 sm:py-10">
        <Dossier
          title="Classification"
          footer={
            multiValue
              ? "Where two values are listed, the first is the primary one, as recorded by the pipeline."
              : undefined
          }
        >
          <dl className="grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Sector">
              {isUnclear(company.sector) ? (
                <NotClassified />
              ) : (
                <span className="display text-xl leading-snug">
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
          </dl>
        </Dossier>

        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <Dossier
            title="VC relevance"
            signal={<RelevanceChip value={company.vc_relevance} />}
            footer="An AI-assisted sourcing signal generated from the homepage. It is not an investment recommendation and carries no confidence score."
          >
            <p className="max-w-[64ch] text-[15px] leading-[1.7]">
              {isUnclear(company.vc_rationale) ? (
                <NotClassified>No rationale recorded.</NotClassified>
              ) : (
                company.vc_rationale
              )}
            </p>
          </Dossier>

          <Dossier
            title="Homepage evidence"
            signal={<EvidenceMeter value={quality} />}
          >
            <p className="text-[15px] leading-[1.7]">
              {FETCH_QUALITY_MEANING[quality] ??
                FETCH_QUALITY_MEANING.unclear}
            </p>
            <dl className="mt-6 flex flex-wrap gap-x-10 gap-y-5 border-t border-line pt-5">
              <Stat
                label="Text captured"
                value={`${(company.homepage_chars ?? 0).toLocaleString("en-GB")} chars`}
              />
              <Stat label="Fetch pass" value={company.fetch_pass ?? "—"} />
            </dl>
          </Dossier>
        </div>
      </div>

      <footer className="border-t border-line bg-navy">
        <div className="mx-auto max-w-[1120px] px-4 py-8 text-2xs leading-relaxed text-ink-muted sm:px-6">
          <GlimpseLogo className="mb-4 opacity-90" />
          <p>
            Registry data from{" "}
            <a
              href="https://startup.registroimprese.it"
              className="text-brand underline underline-offset-4"
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
                by{" "}
                <span className="mono text-ink">
                  tag run {provenance.run_id}
                </span>{" "}
                ({provenance.model})
              </>
            ) : null}
            .
          </p>
        </div>
      </footer>
    </div>
  );
}
