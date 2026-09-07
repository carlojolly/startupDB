"""Executable checks for the v4 tagging and CSV contracts."""
from __future__ import annotations

import csv
import pathlib
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import export_tags  # noqa: E402
import tag_companies  # noqa: E402


def _valid_tags(**overrides):
    values = {
        "parent_sector": "business_software",
        "sector": "accounting automation",
        "product_type": "software_product",
        "customer_model": "b2b",
        "one_line": "Automates accounting workflows for businesses.",
    }
    values.update(overrides)
    return tag_companies.CompanyTags(**values)


def test_v4_classification_fields_are_single_values():
    tags = _valid_tags()
    assert tags.parent_sector == "business_software"
    assert tags.product_type == "software_product"
    assert tags.customer_model == "b2b"

    for field, value in (
        ("parent_sector", ["business_software"]),
        ("product_type", ["software_product"]),
        ("customer_model", ["b2b"]),
    ):
        with pytest.raises(ValidationError):
            _valid_tags(**{field: value})


def test_prompt_matches_single_value_contract_and_keeps_precedence():
    assert "are LISTS" not in tag_companies.SYSTEM_PROMPT
    assert "marketplace beats software_product" in tag_companies.SYSTEM_PROMPT
    assert "Choose one value" in tag_companies.SYSTEM_PROMPT
    assert tag_companies.PROMPT_VERSION == "v4-single-value-2026-09-06"


def test_export_columns_match_contract_exactly():
    assert export_tags.COLUMNS == [
        "codice_fiscale", "denominazione", "ateco", "attivita_label",
        "website_url", "parent_sector", "sector", "product_type",
        "customer_model", "one_line", "fetch_pass", "fetch_bucket",
        "homepage_chars",
    ]


def test_export_is_bom_utf8_with_lf_line_endings(tmp_path):
    path = tmp_path / "tags_codex_r7_2026-09-06.csv"
    row = ["02201200678", "Example, S.R.L.", "621000", "Software", "https://example.it",
           "business_software", "accounting automation", "software_product", "b2b",
           "Automates accounting workflows.", "http", "OK", 1234]

    export_tags._write_csv(path, [row])

    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    with path.open(encoding="utf-8-sig", newline="") as fh:
        parsed = list(csv.reader(fh))
    assert parsed == [export_tags.COLUMNS, [str(value) for value in row]]


def test_export_uses_url_and_provenance_recorded_with_run():
    evidence = "https://fetched.example/path | 876 chars of homepage text | fetch=OK | pass=browser"
    assert export_tags._provenance(
        "https://current.example", None, None, None, evidence
    ) == ("https://fetched.example/path", "browser", "OK", 876)
