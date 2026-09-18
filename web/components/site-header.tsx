import Image from "next/image";
import Link from "next/link";
import wordmark from "@/public/venture-atlas.png";
import { Feedback, type FeedbackCompany } from "./feedback";

export function SiteHeader({ company }: { company?: FeedbackCompany }) {
  return (
    <header className="on-navy sticky top-0 z-40 border-b border-panel-line/70 bg-navy text-on-navy">
      <div className="mx-auto flex h-14 max-w-[1560px] items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center rounded-sm">
          {/* White-on-transparent, so it only ever sits on the navy chrome. */}
          {/* Explicit width/height, not just the utility classes: the <img>
              attributes then size the logo on their own, so a CSS hiccup cannot
              let a 1261px-wide asset loose in a 56px bar. */}
          <Image
            src={wordmark}
            alt="VentureAtlas"
            priority
            width={158}
            height={20}
            className="h-5 w-auto"
          />
        </Link>

        <span className="hidden h-5 w-px bg-panel-line sm:block" />
        <span className="hidden text-[13px] text-on-navy-muted sm:block">
          Italian innovative-startup registry
        </span>

        <Feedback company={company} />
      </div>
    </header>
  );
}
