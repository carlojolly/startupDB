# ADR 0006 — The closed vocabularies are declared in three places and cross-checked by a test

Status: accepted 2026-09-18

## Context

`parent_sector`, `product_type`, `customer_model` and the VC relevance levels
exist as Pydantic `Literal`s (what the model may output), as TypeScript
arrays with labels and sort order (what the dashboard filters on), and as the
human contract in `docs/tagging-contract-v5.md`. Before 2026-09-18 nothing
compared them; a value added on one side would be stored and then hidden
from every filter.

The obvious alternative is one generated vocabulary file (JSON) that both
languages import.

## Decision

Keep the three declarations where they are, and add
`tests/test_taxonomy_consistency.py`, which reads all three as text and
fails on any difference (including the deliberate rule that `unclear` is in
the Python and contract sets but not in the TypeScript arrays).

## Why not a shared JSON file

- Each side needs more than the value list: Python needs `Literal` types for
  schema validation, TypeScript needs labels and display order, the contract
  needs prose definitions. A generated file adds a build step to both halves
  and still leaves the prose by hand.
- The bake-off contract freezes the schema; the vocabulary changes rarely and
  deliberately. A failing test at that moment is the right cost.

## Consequences

- Adding a value means editing three files in one commit; the test says which
  one was missed and what it is missing.
- The test parses `taxonomy.ts` and the contract with regular expressions
  keyed to their current layout (`facet([...])` calls; the indented block,
  table and backtick line in the contract). Reformatting those sections
  breaks the reader, not the check: update the reader in the same commit.
- If the vocabulary ever becomes runtime-editable (a `ref_tag_values` table),
  supersede this ADR; the database then becomes the single source and the
  test compares against it.
