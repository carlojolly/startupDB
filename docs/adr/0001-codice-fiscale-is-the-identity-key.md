# ADR 0001 — `codice_fiscale` is the identity key

Status: accepted (retroactively recorded 2026-09-18)

## Context

The registry export identifies each company by its Italian fiscal code, an
11-digit string, 6,961 of which begin with a zero. Names change, registered
offices move, and the registry itself carries no other stable identifier.

## Decision

`companies.codice_fiscale CHAR(11)` with a `^[0-9]{11}$` CHECK is the primary
key of `companies` and the foreign-key target of `company_snapshots` and
`company_tags`. It is handled as a **string** everywhere: the importer
validates the pattern, the dashboard URL is `/company/<cf>`, the export keeps
the leading zero.

## Consequences

- Nothing in the system ever needs a lookup to find a company; joins are
  direct and the URL is the key.
- The whole schema is Italy-specific. A UK company number (8 alphanumerics) or
  a French SIREN (9 digits) cannot be stored. Multi-country expansion needs a
  surrogate key with `(country, registry_id)` unique, per-country reference
  tables and a per-source cleaner (audit §D.c). That is a deliberate deferral,
  not an oversight.
- Any tool that treats the column as numeric (Excel, pandas default dtype)
  corrupts it. The README forbids re-saving the CSV from Excel for this reason.
