import Link from "next/link";
import { GlimpseLogo } from "./glimpse-logo";
import { Feedback, type FeedbackCompany } from "./feedback";

export function SiteHeader({ company }: { company?: FeedbackCompany }) {
  return (
    <header className="on-navy sticky top-0 z-40 border-b border-brand/15 bg-navy/80 text-on-navy backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-5 px-4 sm:px-6">
        <Link
          href="/"
          aria-label="Glimpse home"
          className="flex shrink-0 items-center rounded-sm"
        >
          <GlimpseLogo />
        </Link>
        <div className="hidden items-center gap-3 sm:flex">
          <span aria-hidden className="h-px w-8 bg-brand/50" />
          <span className="mono text-[11px] tracking-[0.14em] text-on-navy-muted uppercase">
            IT · innovative startups
          </span>
        </div>
        <Feedback company={company} />
      </div>
    </header>
  );
}
