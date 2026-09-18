import Image from "next/image";
import Link from "next/link";
import wordmark from "@/public/venture-atlas.png";

/**
 * Where "Feedback" goes. A mail link needs no backend, no migration and no
 * third-party form, which keeps the dashboard free of runtime services;
 * change the address here if feedback should reach someone else.
 */
const FEEDBACK_EMAIL = "carlojolly@icloud.com";

export function SiteHeader({
  feedbackAbout,
}: {
  /** The thing the reader is looking at, so a mail arrives with context. */
  feedbackAbout?: { label: string; path: string };
}) {
  const subject = feedbackAbout
    ? `VentureAtlas feedback: ${feedbackAbout.label}`
    : "VentureAtlas feedback";
  const body = feedbackAbout
    ? `Page: ${feedbackAbout.path}\n\n`
    : "";
  const mailto = `mailto:${FEEDBACK_EMAIL}?subject=${encodeURIComponent(subject)}${
    body ? `&body=${encodeURIComponent(body)}` : ""
  }`;

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

        <a
          href={mailto}
          className="ml-auto inline-flex h-8 items-center gap-2 rounded-full border border-panel-line bg-panel px-3 text-[12px] font-medium text-on-navy-muted transition-colors hover:border-on-navy-faint hover:text-on-navy"
        >
          <svg
            aria-hidden
            viewBox="0 0 14 14"
            className="h-3.5 w-3.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
          >
            <path
              d="M2.5 3.5h9a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H6l-2.5 2v-2h-1a1 1 0 0 1-1-1v-5a1 1 0 0 1 1-1Z"
              strokeLinejoin="round"
            />
          </svg>
          Feedback
        </a>
      </div>
    </header>
  );
}
