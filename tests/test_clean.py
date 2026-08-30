"""Tests for the CSV cleaning functions.

Run them with:   pytest

None of these need a database. The last test only runs if you have a real
export sitting in data/raw/ — it is skipped otherwise, so CI stays green
without shipping company data into the repo.
"""
from __future__ import annotations

import csv
import datetime
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import clean  # noqa: E402


# ---------------------------------------------------------------------------
# Header handling — the export has literal newlines inside three header names
# ---------------------------------------------------------------------------

def test_normalise_header_flattens_newlines():
    assert clean.normalise_header("1° req.\n(6)") == "1° req. (6)"
    assert clean.normalise_header("  DATA   Dichiarazione\n(7) ") == "data dichiarazione (7)"


def test_resolve_columns_reports_what_is_missing():
    with pytest.raises(ValueError, match="missing expected columns"):
        clean.resolve_columns(["denominazione", "pv"])


# ---------------------------------------------------------------------------
# Scalars
# ---------------------------------------------------------------------------

def test_text_collapses_internal_whitespace():
    # 644 company names in the real file contain double spaces.
    assert clean.text("ACME   S.R.L.  ") == "ACME S.R.L."
    assert clean.text("   ") is None
    assert clean.text(None) is None


def test_parse_date_handles_italian_format_and_junk():
    assert clean.parse_date("09/07/2020") == datetime.date(2020, 7, 9)
    assert clean.parse_date("") is None
    assert clean.parse_date("not a date") is None
    # day/month order must not be swapped: 07/09 is 7 September, not 9 July
    assert clean.parse_date("07/09/2020") == datetime.date(2020, 9, 7)


def test_si_flag_treats_blank_as_false():
    # The req. columns are 'SI' or blank and never 'NO', so blank means False.
    assert clean.parse_si_flag("SI") is True
    assert clean.parse_si_flag("") is False
    assert clean.parse_si_flag(None) is False


def test_si_no_keeps_blank_as_unknown():
    assert clean.parse_si_no("SI") is True
    assert clean.parse_si_no("NO") is False
    assert clean.parse_si_no("") is None


# ---------------------------------------------------------------------------
# ATECO
# ---------------------------------------------------------------------------

def test_ateco_division_never_zero_pads():
    # '471' is ATECO group 47.1, NOT a truncated '471000'. Verified against the
    # real file: no short code zero-pads to a 6-digit code that exists there.
    assert clean.ateco_division("471") == "47"
    assert clean.ateco_division("621000") == "62"
    assert clean.ateco_division("0113") == "01"
    assert clean.ateco_division("NC") is None
    assert clean.ateco_division("") is None


def test_parse_attivita_splits_section_and_division():
    assert clean.parse_attivita("J 62 PRODUZIONE DI SOFTWARE, CONSULENZA") == (
        "J", "62", "PRODUZIONE DI SOFTWARE, CONSULENZA")
    # 'N.S.' is what the 58 unclassified rows carry.
    assert clean.parse_attivita("N.S.") == (None, None, "N.S.")


def test_in_liquidazione_detected_from_name():
    assert clean.is_in_liquidazione("LABELSCOIN S.R.L. IN LIQUIDAZIONE") is True
    assert clean.is_in_liquidazione("ACME S.R.L. IN SCIOGLIMENTO") is True
    assert clean.is_in_liquidazione("ACME S.R.L.") is False


# ---------------------------------------------------------------------------
# Websites — every input below is a real value from the registry export
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,url,domain", [
    ("www.labelscoin.technology", "https://www.labelscoin.technology", "labelscoin.technology"),
    ("www. siepegrande.it",       "https://www.siepegrande.it",        "siepegrande.it"),
    (": www.kriton.cloud",        "https://www.kriton.cloud",          "kriton.cloud"),
    ("eidoslab.io - eidoslab.eu - eidoslab.it", "https://eidoslab.io", "eidoslab.io"),
    ("www.langaponica.it e www.langaponica.com", "https://www.langaponica.it", "langaponica.it"),
    ("htps://www.fmsafetynet.com/", "https://www.fmsafetynet.com",     "fmsafetynet.com"),
    ("http//keynesia.energy",      "https://keynesia.energy",          "keynesia.energy"),
    ("//sostenia.net/",            "https://sostenia.net",             "sostenia.net"),
    ("http:www.real-ei.it",        "https://www.real-ei.it",           "real-ei.it"),
])
def test_clean_website_repairs_real_values(raw, url, domain):
    assert clean.clean_website(raw) == (url, domain)


@pytest.mark.parametrize("raw", [
    "non presente", "non presente attualmente", "assente", "in costruzione",
    "hotelsalina@hotelsalina.com", ".", "-", "roma", "www.", "www.012factory",
])
def test_clean_website_rejects_non_urls(raw):
    assert clean.clean_website(raw) == (None, None)


def test_clean_website_does_not_mangle_a_normal_domain():
    # Guard against the scheme-stripping regexes eating part of a real domain.
    assert clean.clean_website("www.foo.it//extra")[1] == "foo.it"
    assert clean.clean_website("https://a.b.co/path") == ("https://a.b.co/path", "a.b.co")


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------

def _row(**overrides):
    row = {f: None for f in clean.HASHED_FIELDS}
    row.update({"denominazione": "ACME S.R.L.", "pv": "MI", "in_liquidazione": False,
                "req_ricerca_sviluppo": True, "req_personale_qualificato": False,
                "req_brevetto": False})
    row.update(overrides)
    return row


def test_content_hash_is_stable_across_calls():
    assert clean.content_hash(_row()) == clean.content_hash(_row())


def test_content_hash_changes_when_a_field_changes():
    assert clean.content_hash(_row()) != clean.content_hash(_row(pv="RM"))
    assert clean.content_hash(_row()) != clean.content_hash(_row(req_brevetto=True))


def test_content_hash_ignores_when_we_looked():
    # observed_on / import_id are deliberately not part of the hash, otherwise
    # every weekly import would write a new snapshot for every company.
    a = _row(); b = _row()
    a["observed_on"] = datetime.date(2026, 1, 1)
    b["observed_on"] = datetime.date(2026, 8, 30)
    assert clean.content_hash(a) == clean.content_hash(b)


def test_content_hash_distinguishes_none_from_empty_string():
    assert clean.content_hash(_row(comune=None)) != clean.content_hash(_row(comune="X"))


def test_codice_fiscale_validation():
    assert clean.is_valid_codice_fiscale("00976660944") is True
    assert clean.is_valid_codice_fiscale("0097666094") is False    # 10 digits
    assert clean.is_valid_codice_fiscale("RSSMRA80A01H501U") is False  # personal CF
    assert clean.is_valid_codice_fiscale("") is False


# ---------------------------------------------------------------------------
# Whole-file smoke test (skipped when no export is present)
# ---------------------------------------------------------------------------

REAL_FILES = sorted((pathlib.Path(__file__).resolve().parent.parent / "data" / "raw").glob("*.csv"))


@pytest.mark.skipif(not REAL_FILES, reason="no CSV in data/raw/ to test against")
def test_real_export_cleans_without_errors():
    path = REAL_FILES[-1]
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        columns = clean.resolve_columns(reader.fieldnames)
        rows = [r for r in reader
                if clean.is_valid_codice_fiscale((r.get(columns["codice_fiscale"]) or "").strip())]

    assert rows, "no valid companies found"
    cleaned = [clean.clean_row(r, columns) for r in rows]

    # Primary key really is unique.
    cfs = [(r.get(columns["codice_fiscale"]) or "").strip() for r in rows]
    assert len(set(cfs)) == len(cfs)

    # Hashing is total and deterministic over real data.
    hashes = [clean.content_hash(c) for c in cleaned]
    assert all(len(h) == 64 for h in hashes)
    assert hashes == [clean.content_hash(c) for c in cleaned]

    # Sanity: the vast majority of rows classify and most websites survive.
    with_division = sum(1 for c in cleaned if c["ateco_division"])
    assert with_division / len(cleaned) > 0.99
    raw_sites = [c for c in cleaned if c["sito_internet_raw"]]
    good_sites = [c for c in raw_sites if c["sito_internet_url"]]
    assert len(good_sites) / len(raw_sites) > 0.99
