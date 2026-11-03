import type { Company } from "./model";

export const EXPORT_COLUMNS = [
  "codice_fiscale", "denominazione", "comune", "pv", "provincia", "regione",
  "sito_internet_url", "in_liquidazione", "parent_sectors", "product_types",
  "customer_models", "sector", "one_line", "vc_relevance", "vc_rationale",
  "fetch_quality", "fetch_pass", "homepage_chars",
] as const;

function cell(value: unknown): string {
  const raw = Array.isArray(value) ? value.join("; ") : value == null ? "" : String(value);
  // Spreadsheet applications can execute formulas from untrusted registry or
  // homepage text. Keep the content visible while forcing it to be plain text.
  const safe = /^[\s\uFEFF]*[=+\-@]/u.test(raw) ? `'${raw}` : raw;
  return `"${safe.replaceAll('"', '""')}"`;
}

/** UTF-8 BOM makes accented Italian names readable in common spreadsheet apps. */
export function companiesToCsv(companies: Company[]): string {
  const header = EXPORT_COLUMNS.map(cell).join(",");
  const rows = companies.map((company) =>
    EXPORT_COLUMNS.map((column) => cell(company[column])).join(","),
  );
  return `\uFEFF${[header, ...rows].join("\r\n")}\r\n`;
}
