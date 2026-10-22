/**
 * A neutral monogram in place of a logo. The registry has no company logos and
 * fetching favicons would hand every company's domain to a third party, so the
 * initials are derived from the name the registry itself holds.
 */

// Legal form and boilerplate. Registered names are full of it — "SOCIETA' A
// RESPONSABILITA' LIMITATA SEMPLIFICATA" tells you nothing about the company.
const NOISE = new Set([
  "SOCIETA",
  "RESPONSABILITA",
  "LIMITATA",
  "SEMPLIFICATA",
  "SRL",
  "SRLS",
  "SPA",
  "SNC",
  "SAS",
  "SS",
  "SCARL",
  "SCRL",
  "IN",
  "LIQUIDAZIONE",
  "SCIOGLIMENTO",
  "CONCORDATO",
  "PREVENTIVO",
  "START",
  "STARTUP",
  "STARTUPP",
  "UP",
  "COSTITUITA",
  "NORMA",
  "DELLART",
  "COMMA",
  "BIS",
  "DEL",
  "DELLA",
  "DELLE",
  "DEI",
  "DECRETO",
  "LEGGE",
  "GENNAIO",
  "N",
  "SIGLA",
  "ABBREVIABILE",
  "ENUNCIABILE",
  "ANCHE",
  "SIGLABILE",
  "DI",
  "E",
  "IMPRESA",
  "SOCIALE",
  "BENEFIT",
  "CONSORTILE",
  "COOPERATIVA",
  "UNIPERSONALE",
  "SEMPL",
  "SOC",
  "RESP",
  "LTD",
  "LIMITED",
  "OU",
  "GMBH",
  "DELL",
  "ALL",
  "ART",
  "COSTITUITO",
]);

function words(name: string): string[] {
  // Registry names carry a boilerplate tail after "***" quoting the statute the
  // company was incorporated under. Nothing before the marker is lost.
  return name
    .split("***")[0]
    .toUpperCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .split(/[^A-Z0-9]+/)
    .filter(Boolean);
}

export function initials(name: string): string {
  const all = words(name);
  // Single characters are almost always the debris of a punctuated legal form
  // ("S.R.L." -> S, R, L), so they never contribute an initial.
  const significant = all.filter((word) => word.length > 1 && !NOISE.has(word));
  const source = significant.length ? significant : all;
  if (!source.length) return "··";
  if (source.length === 1) return source[0].slice(0, 2);
  return source[0][0] + source[1][0];
}

export function Monogram({
  name,
  size = "md",
}: {
  name: string;
  size?: "md" | "lg";
}) {
  const box =
    size === "lg"
      ? "h-14 w-14 rounded-[12px] text-lg"
      : "h-9 w-9 rounded-[8px] text-xs";
  return (
    <span
      aria-hidden
      className={`${box} bg-surface-sunk text-ink-muted ring-1 ring-inset ring-line flex shrink-0 items-center justify-center font-semibold tracking-tight select-none`}
    >
      {initials(name)}
    </span>
  );
}
