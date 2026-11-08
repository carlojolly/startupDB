/**
 * A survey plate mark in place of a logo. The registry has no company logos and
 * fetching favicons would hand every company's domain to a third party, so the
 * initials are derived from the name the registry itself holds.
 */

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
      ? "h-16 w-16 text-xl"
      : "h-11 w-11 text-[11px]";
  return (
    <span
      aria-hidden
      className={`${box} relative flex shrink-0 items-center justify-center border border-line bg-navy font-semibold tracking-[0.08em] text-brand select-none`}
    >
      <span className="atlas-corner atlas-corner-tl !w-2 !h-2" />
      <span className="atlas-corner atlas-corner-br !w-2 !h-2" />
      {initials(name)}
    </span>
  );
}
