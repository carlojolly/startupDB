import Link from "next/link";
import { GlimpseLogo } from "./glimpse-logo";
import { Feedback, type FeedbackCompany } from "./feedback";

export function SiteHeader({ company }: { company?: FeedbackCompany }) {
  return (
    <header className="on-navy sticky top-0 z-40 border-b border-panel-line/70 bg-navy text-on-navy">
      <div className="mx-auto flex h-14 max-w-[1560px] items-center gap-6 px-4 sm:px-6">
        <Link href="/" aria-label="Glimpse home" className="flex shrink-0 items-center rounded-sm">
          <GlimpseLogo />
        </Link>
        <span className="hidden h-4 w-px bg-panel-line sm:block" />
        <span className="hidden text-xs text-on-navy-muted sm:block">Discover Italian startups</span>
        <Feedback company={company} />
      </div>
    </header>
  );
}
