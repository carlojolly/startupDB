import {
  FETCH_QUALITY,
  FETCH_QUALITY_MEANING,
  FETCH_QUALITY_SHORT,
  UNCLEAR,
  VC_RELEVANCE,
  isUnclear,
} from "@/lib/taxonomy";

/**
 * VC relevance as a survey mark. Amber is spent only on `high`, so the eye
 * lands on the shortlist; every other level is a quiet plate label.
 */
export function RelevanceChip({
  value,
  onDark = false,
}: {
  value: string | null;
  onDark?: boolean;
}) {
  if (isUnclear(value)) {
    return (
      <span
        className={`mono text-[10px] tracking-[0.12em] uppercase ${onDark ? "text-on-navy-faint" : "text-ink-faint"}`}
        title="Too little evidence to assess VC relevance."
      >
        Not assessed
      </span>
    );
  }
  const key = value as string;
  const label = VC_RELEVANCE.labels[key] ?? key;
  const hot = key === "high";
  return (
    <span
      className={`inline-flex items-center gap-1.5 border px-2 py-1 mono text-[10px] font-semibold tracking-[0.14em] uppercase ${
        hot
          ? "border-brand bg-brand text-navy"
          : onDark
            ? "border-panel-line text-on-navy-muted"
            : "border-line text-ink-muted"
      }`}
      title={`${label} VC relevance — an AI-assisted sourcing signal, not a recommendation.`}
    >
      {hot ? (
        <svg viewBox="0 0 10 10" aria-hidden className="h-2 w-2" fill="currentColor">
          <path d="M5 0 6.3 3.7 10 5 6.3 6.3 5 10 3.7 6.3 0 5l3.7-1.3z" />
        </svg>
      ) : null}
      {label}
    </span>
  );
}

const FILLED: Record<string, number> = { OK: 3, THIN: 2, DEAD: 0 };

/**
 * Homepage evidence quality as a three-bar instrument beside the plate code.
 */
export function EvidenceMeter({
  value,
  showLabel = true,
  onDark = false,
}: {
  value: string | null;
  showLabel?: boolean;
  onDark?: boolean;
}) {
  const key = value && isKnownQuality(value) ? value : UNCLEAR;
  const filled = FILLED[key] ?? 0;
  const label = key === UNCLEAR ? "—" : FETCH_QUALITY.labels[key];
  return (
    <span
      className={`inline-flex items-center gap-1.5 ${onDark ? "text-on-navy-muted" : "text-ink-muted"}`}
      title={FETCH_QUALITY_MEANING[key]}
    >
      <span aria-hidden className="flex items-end gap-[3px]">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={`block w-[3px] ${
              i < filled
                ? "bg-brand"
                : onDark
                  ? "bg-panel-line"
                  : "bg-line-strong"
            }`}
            style={{ height: `${7 + i * 3}px` }}
          />
        ))}
      </span>
      {showLabel ? (
        <span className="mono text-[10px] font-semibold tracking-[0.12em] uppercase">
          {label}
        </span>
      ) : null}
      <span className="sr-only">
        Homepage evidence: {label}. {FETCH_QUALITY_SHORT[key] ?? ""}
      </span>
    </span>
  );
}

function isKnownQuality(value: string): boolean {
  return (FETCH_QUALITY.values as readonly string[]).includes(value);
}

/** A stored tag value. `emphasis` marks the primary (first) value. */
export function TagPill({
  children,
  emphasis = false,
}: {
  children: React.ReactNode;
  emphasis?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center border px-2.5 py-1 text-xs ${
        emphasis
          ? "border-brand/40 bg-brand-wash font-medium text-brand-bright"
          : "border-line bg-transparent text-ink-muted"
      }`}
    >
      {children}
    </span>
  );
}

/** What the UI shows wherever the pipeline returned `unclear`. */
export function NotClassified({ children = "Not classified" }: { children?: string }) {
  return <span className="text-ink-faint italic">{children}</span>;
}
