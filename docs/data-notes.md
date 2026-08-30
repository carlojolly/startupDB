# Data notes — Italian innovative startups registry

Findings from profiling the export downloaded **2026-08-30**
(`startupcsv.csv`, 2.7 MB, MD5 `325302210607d35460c98b1860b4e66e`).

Re-check these when the registry changes its export format. Everything below
was measured, not assumed.

---

## File mechanics

| Property | Value |
|---|---|
| Encoding | UTF-8 **with BOM** — open with `encoding="utf-8-sig"` |
| Line endings | CRLF |
| Delimiter | Comma, quoted fields |
| Raw rows parsed | 11,816 |
| **Valid companies** | **11,542** |
| Columns | 24 |

Three headers contain **literal newline characters**:
`"1° req.\n(6)"`, `"2° req.\n(6)"`, `"3° req.\n(6)"`, `"data dichiarazione\n(7)"`.
This is why `clean.resolve_columns()` matches headers by a normalised form
rather than by exact string.

### A second export format exists

The registry also publishes a **pipe-delimited** variant (seen as
`startup_17082026.csv`, ~12 MB, latin-1). It carries extra columns the comma
export lacks — `regione`, `sezione attività` — and names the three requirement
columns explicitly (`spese in ricerca e sviluppo`, `forza lavoro con titoli`,
`possesso di brevetti`).

We do **not** depend on it: region is supplied by `ref_provincia` instead.
`COLUMN_ALIASES` in `scripts/clean.py` already contains that format's header
names, so it would mostly parse if anyone needs it.

---

## Column inventory

Fill rates are against the 11,542 valid rows.

| Column | Filled | Distinct | Notes |
|---|---:|---:|---|
| `denominazione` | 100% | 11,499 | **Not unique** — 38 names shared by 2–3 companies |
| `nat.giuridica` | 100% | 9 | 94.6% are `SOCIETA' A RESPONSABILITA' LIMITATA` |
| `codice fiscale` | 100% | 11,542 | Unique, all exactly 11 digits. **6,961 start with `0`** |
| `pv` | 100% | 104 | Two uppercase letters, always valid |
| `comune` | 100% | 1,786 | 62 values need trimming |
| `data iscrizione alla sezione delle startup` | 100% | 2,049 | 2013-06-12 → 2026-08-14 |
| `data iscrizione al Registro Imprese` | 100% | 2,121 | 2013-06-04 → 2026-08-14 |
| `data inizio esercizio effettivo` | 99.4% | 2,208 | 2001-01-01 → 2026-08-14 |
| `ateco 2007` | 100% | 539 | **Ragged — see below** |
| `settore` | 99.5% | 5 | Blank for exactly the 58 `NC` rows + 1 |
| `attività` | 100% | 75 | Labels truncated at ~57 chars by the source |
| `classe di produzione` | 65.7% | 7 | A–G observed; legend defines A–H |
| `classe di addetti` | **35.2%** | 5 | A–E observed; legend defines A–F |
| `impresa a vocazione sociale` | 2.5% | 1 | Only ever `SI` |
| `alto valore tecnologico energetico` | 100% | 2 | Real `SI`/`NO` |
| `classe di capitale` | 99.5% | 11 | Codes 1–11, all present |
| `sito internet` | 83.6% | 9,617 | Dirty — see below |
| `1° / 2° / 3° req.` | 64/20/17% | 1 | Only ever `SI`, never `NO` |
| `data dichiarazione` | 99.9% | 1,759 | |
| `prevalenza femminile/giovanile/straniera` | 93/92/94% | 4 | `NO`, `Maggioritaria`, `Forte`, `Esclusiva` |

All four date columns parse cleanly as `dd/mm/yyyy` — **zero** unparseable
values, and zero dates in the future.

---

## Problems, in order of how much they matter

### 1. 274 empty trailing rows

The file ends with 274 rows that are completely blank (`,,,,,...`). A
spreadsheet export artifact. **Filter: any row with no codice fiscale.**

### 2. ATECO codes are ragged, and must not be zero-padded

| Length | Rows | Share |
|---|---:|---:|
| 6 digits | 11,011 | 95.4% |
| 5 digits | 212 | 1.8% |
| 4 digits | 100 | 0.9% |
| 3 digits | 158 | 1.4% |
| 2 digits | 3 | <0.1% |
| literal `NC` | 58 | 0.5% |

The obvious hypothesis — that Excel stripped trailing zeros — **was tested and
is false**. Zero of the 71 distinct short codes zero-pad to a 6-digit code that
appears anywhere else in the file. They are genuinely coarser levels of the
ATECO hierarchy (`471` is group 47.1), and a few like `7411` look like legacy
ATECO 2002 codes carried on older companies.

**The 2-digit division is reliable.** It agrees with the letter+number prefix
of the `attività` label in **100%** of rows (0 mismatches / 11,542). That is
the level to group by.

The 58 `NC` rows carry `attività = 'N.S.'` and a blank `settore`. Nothing is
recoverable from them; they get a `NULL` division, which is correct.

### 3. The classification is too coarse to be useful alone

| ATECO | Companies | Share |
|---|---:|---:|
| `621000` software production | 5,087 | 44.1% |
| `721029` other R&D in natural sciences | 1,323 | 11.5% |
| `639100` news agencies | 486 | 4.2% |
| `629009` other IT services | 394 | 3.4% |
| `622010` IT consulting | 368 | 3.2% |

Nearly half the database is one code. This is the reason for the planned LLM
tagging layer.

### 4. Leading zeros are fragile

6,961 codice fiscale values and 70 ATECO codes begin with `0`. Opening the CSV
in Excel and re-saving destroys them. Treat both as text, always.

### 5. Size data is largely absent

- `classe di addetti` blank for **64.8%** — headcount is unusable as a filter
  for two-thirds of the database.
- `classe di produzione` blank for 34.3%.
- `classe di capitale` blank for only 0.5% — the one size field you can rely on.

No company in this file is in the top band of either scale: revenue reaches
`G` (€10–50M): 16 companies at `F`, 6 at `G`, 22 in total above €5M.
Headcount reaches `E` (50–249).

### 6. Qualifying criteria

Companies must meet at least one of three criteria. Blank never means "no
data" here — it means the criterion does not apply.

| Criterion | Companies | Share |
|---|---:|---:|
| R&D spend ≥15% only | 7,206 | 62.4% |
| Qualified staff only | 2,083 | 18.0% |
| Patent / registered software only | 1,835 | 15.9% |
| Two criteria | 359 | 3.1% |
| All three | 48 | 0.4% |
| **None** | **11** | **0.1%** |

Those 11 with no criterion should not legally exist. Worth investigating.

### 7. Dates can be out of order

**327 companies** have a startup-section date *earlier* than their business
registry date — e.g. WIDE VR S.R.L., registry 28/10/2025, section 12/01/2023.
Not a parse error: it is what happens when a company re-registers after moving
its registered office. Any elapsed-time metric between the two goes negative.

### 8. No status column

The export has no field for whether a company is winding down. The only signal
is the name. **286 companies** are flagged in total:

- 277 contain `IN LIQUIDAZIONE`, 7 contain `IN SCIOGLIMENTO` — but one company
  contains *both* (`AMATO1926 S.R.L. IN SCIOGLIMENTO ... IN LIQUIDAZIONE`), so
  that is 283 distinct companies, not 284.
- 3 more are only caught after whitespace normalisation, because the phrase is
  split by a long run of spaces (`... SPIN OFF ACCADEMICO IN        LIQUIDAZIONE`).

This is what the derived `in_liquidazione` column is built from. It is a
heuristic on the company name, not an authoritative status field.

### 9. Websites

83.6% filled (9,645 rows). The cleaner salvages **9,620 (99.7%)**.

Failure modes actually present:

| Shape | Example |
|---|---|
| Space inside the domain | `www. siepegrande.it` |
| Leading punctuation | `: www.kriton.cloud` |
| Several domains in one cell | `eidoslab.io - eidoslab.eu - eidoslab.it` |
| Italian conjunction as separator | `www.langaponica.it e www.langaponica.com` |
| Mangled scheme | `htps://`, `http//`, `ps://`, `//sostenia.net/` |
| Not a URL at all | `non presente`, `assente`, `in costruzione`, `roma` |
| Email address | `hotelsalina@hotelsalina.com` |
| Missing TLD | `www.012factory`, `faf-it` |

The 25 unrecoverable values are kept verbatim in `sito_internet_raw`.

**A domain is not an identity.** `www.healthybusinessadvisory.com` appears for
**14 different companies** — an accountancy filling its own site into clients'
filings. 15 domains in total are shared by more than one company.

### 10. Geography

104 distinct provinces. The registry uses **legacy codes**: `FO` for
Forlì-Cesena (now `FC`) and `PS` for Pesaro e Urbino (now `PU`).
`ref_provincia` contains both spellings plus the provinces absent from this
file, so an unexpected code cannot break the weekly load.

`comune = 'AMSTERDAM'` appears under two different provinces (RM and NA) —
foreign-domiciled entities registered through an Italian office.

### 11. Text hygiene

644 company names contain internal double spaces; 62 `comune` values have
leading or trailing whitespace. Both are normalised on import (whitespace runs
collapsed to a single space), because otherwise a name search splits one
company into two.

---

## Growth over time

Registrations to the startup section, by year:

| Year | New |
|---|---:|
| 2013 | 2 |
| 2014 | 9 |
| 2015 | 40 |
| 2016 | 48 |
| 2017 | 114 |
| 2018 | 155 |
| 2019 | 231 |
| 2020 | 618 |
| 2021 | 1,303 |
| 2022 | 1,312 |
| 2023 | 1,531 |
| 2024 | 2,005 |
| 2025 | 2,254 |
| 2026 (to Aug) | 1,920 |

These are **not** founding dates for a cohort study. Innovative-startup status
expires after five years, so early years look small because those companies
have already aged out of the registry — not because few were founded. This is
precisely why the snapshot history is worth accumulating: it is the only way
this project can observe companies leaving.
