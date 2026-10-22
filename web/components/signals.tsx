import {
  FETCH_QUALITY,
  FETCH_QUALITY_MEANING,
  FETCH_QUALITY_SHORT,
  UNCLEAR,
  VC_RELEVANCE,
  isUnclear,
} from "@/lib/taxonomy";

const PILL =
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-2xs font-semibold tracking-[0.04em] uppercase";

const RELEVANCE_LIGHT: Record<string, string> = {
  high: "bg-amber-wash text-amber ring-1 ring-inset ring-amber-line",
  medium: "bg-surface-sunk text-ink-muted",
  low: "bg-surface-sunk text-ink-muted",
};

const RELEVANCE_DARK: Record<string, string> = {
  high: "bg-amber-wash text-amber ring-1 ring-inset ring-amber-line",
  medium: "bg-surface-sunk text-ink-muted",
  low: "bg-white/10 text-on-navy-muted ring-1 ring-inset ring-panel-line",
};

/**
 * VC relevance as a single chip. Amber is spent only on `high`, so the eye
 * lands on the shortlist; every other level is neutral.
 */
export function RelevanceChip({
  value,
  onDark = false,
}: {
  value: string | null;
  onDark?: boolean;
}) {
  // Missing information is rendered as missing — quiet, lower case, no chip —
  // so it never reads as a fourth level below "low".
  if (isUnclear(value)) {
    return (
      <span
        className={`text-2xs whitespace-nowrap italic ${onDark ? "text-on-navy-faint" : "text-ink-faint"}`}
        title="Too little evidence to assess VC relevance."
      >
        Not assessed
      </span>
    );
  }
  const key = value as string;
  const label = VC_RELEVANCE.labels[key] ?? key;
  const styles = onDark ? RELEVANCE_DARK : RELEVANCE_LIGHT;
  return (
    <span
      className={`${PILL} ${styles[key] ?? ""}`}
      title={`${label} VC relevance — an AI-assisted sourcing signal, not a recommendation.`}
    >
      {key === "high" ? (
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
 * Homepage evidence quality. The three bars read at a glance in a dense list;
 * the code beside them is the exact value the pipeline recorded.
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
      <span aria-hidden className="flex items-end gap-[2px]">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={`block w-[3px] rounded-[1px] ${
              i < filled
                ? onDark
                  ? "bg-on-navy"
                  : "bg-ink"
                : onDark
                  ? "bg-panel-line"
                  : "bg-line-strong"
            }`}
            style={{ height: `${6 + i * 2}px` }}
          />
        ))}
      </span>
      {showLabel ? (
        <span className="text-2xs font-semibold tracking-[0.06em]">{label}</span>
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
      className={`inline-flex items-center rounded-md px-2.5 py-1 text-xs ${
        emphasis
          ? "bg-surface-sunk font-medium text-ink"
          : "bg-surface text-ink-muted ring-1 ring-inset ring-line"
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
