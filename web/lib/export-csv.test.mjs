import assert from "node:assert/strict";
import test from "node:test";
import { companiesToCsv, EXPORT_COLUMNS } from "./export-csv.ts";

test("exports each company once with stable columns and spreadsheet-safe cells", () => {
  const company = Object.fromEntries(EXPORT_COLUMNS.map((column) => [column, null]));
  Object.assign(company, {
    codice_fiscale: "00123456789",
    denominazione: 'Alfa, "Beta"\nSrl',
    parent_sectors: ["Business software", "Finance & insurance"],
    one_line: "=HYPERLINK(\"https://example.com\")",
    vc_relevance: "high",
    in_liquidazione: false,
  });

  const csv = companiesToCsv([company]);
  assert.ok(csv.startsWith("\uFEFF"));
  assert.ok(csv.endsWith("\r\n"));
  assert.match(csv, /"00123456789"/);
  assert.match(csv, /"Alfa, ""Beta""\nSrl"/);
  assert.match(csv, /"Business software; Finance & insurance"/);
  assert.match(csv, /"'=HYPERLINK\(""https:\/\/example\.com""\)"/);
  assert.match(csv, /"false"/);
  assert.equal(companiesToCsv([]).split("\r\n").length, 2);
});

test("neutralizes formula prefixes after whitespace", () => {
  const company = Object.fromEntries(EXPORT_COLUMNS.map((column) => [column, null]));
  company.denominazione = "  +SUM(1,2)";
  assert.match(companiesToCsv([company]), /"'  \+SUM\(1,2\)"/);
});
