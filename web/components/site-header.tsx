import Image from "next/image";
import Link from "next/link";
import type { Provenance } from "@/lib/model";
import wordmark from "@/public/venture-atlas.png";

function formatDate(value: Date | string | null | undefined): string {
  if (!value) return "unknown date";
  return new Date(value).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function SiteHeader({ provenance }: { provenance: Provenance | null }) {
  return (
    <header className="on-navy sticky top-0 z-40 border-b border-panel-line/70 bg-navy text-on-navy">
      <div className="mx-auto flex h-14 max-w-[1560px] items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center rounded-sm">
          {/* White-on-transparent, so it only ever sits on the navy chrome. */}
          <Image
            src={wordmark}
            alt="VentureAtlas"
            priority
            className="h-5 w-auto"
          />
        </Link>

        <span className="hidden h-5 w-px bg-panel-line sm:block" />
        <span className="hidden text-[13px] text-on-navy-muted sm:block">
          Italian innovative-startup registry
        </span>

        {provenance ? (
          <span className="ml-auto hidden items-center gap-2 rounded-full border border-panel-line bg-panel px-3 py-1.5 text-2xs text-on-navy-muted md:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-amber" />
            <span className="tnum">
              Tag run {provenance.run_id} · {formatDate(provenance.finished_at)}
            </span>
          </span>
        ) : null}
      </div>
    </header>
  );
}
