import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import Module from "node:module";
import path from "node:path";
import test from "node:test";
import typescript from "typescript";
import { fileURLToPath } from "node:url";

// Transpile this one pure module in memory so the test also runs on Node 20,
// the dashboard's documented minimum. No additional test runner is needed.
const directory = path.dirname(fileURLToPath(import.meta.url));
const filename = path.join(directory, "export-csv.ts");
const { outputText } = typescript.transpileModule(readFileSync(filename, "utf8"), {
  compilerOptions: {
    module: typescript.ModuleKind.CommonJS,
    target: typescript.ScriptTarget.ES2022,
  },
});
const compiled = new Module(filename);
compiled.filename = filename;
compiled.paths = Module._nodeModulePaths(directory);
compiled._compile(outputText, filename);
const { companiesToCsv, EXPORT_COLUMNS } = compiled.exports;

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
