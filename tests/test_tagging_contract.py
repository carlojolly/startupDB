"""Executable checks for the v5 tagging and CSV contracts."""
from __future__ import annotations

import asyncio
import csv
import pathlib
import sys
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import export_tags  # noqa: E402
import tag_companies  # noqa: E402


def _valid_tags(**overrides):
    values = {
        "parent_sector": ["business_software"],
        "sector": "accounting automation",
        "product_type": ["software_product"],
        "customer_model": ["b2b"],
        "one_line": "Automates accounting workflows for businesses.",
    }
    values.update(overrides)
    return tag_companies.CompanyTags(**values)


def test_v5_classification_fields_are_ordered_lists_of_one_or_two():
    tags = _valid_tags(
        parent_sector=["hospitality_travel_food_service", "arts_culture_heritage"],
        product_type=["hardware_device", "software_product"],
        customer_model=["b2b", "b2c"],
    )
    assert tags.parent_sector == [
        "hospitality_travel_food_service", "arts_culture_heritage",
    ]
    assert tags.product_type == ["hardware_device", "software_product"]
    assert tags.customer_model == ["b2b", "b2c"]

    for field, value in (
        ("parent_sector", "business_software"),
        ("parent_sector", []),
        ("parent_sector", ["business_software", "other", "food_agriculture"]),
        ("product_type", "software_product"),
        ("product_type", []),
        ("product_type", ["software_product", "hardware_device", "marketplace"]),
        ("customer_model", "b2b"),
        ("customer_model", []),
        ("customer_model", ["b2b", "b2c", "b2g"]),
    ):
        with pytest.raises(ValidationError):
            _valid_tags(**{field: value})


@pytest.mark.parametrize("field,other", [
    ("parent_sector", "business_software"),
    ("product_type", "software_product"),
    ("customer_model", "b2b"),
])
def test_unclear_cannot_appear_with_another_value(field, other):
    with pytest.raises(ValidationError, match="cannot combine 'unclear'"):
        _valid_tags(**{field: ["unclear", other]})


@pytest.mark.parametrize("direct_model", ["b2b", "b2c"])
def test_b2b2c_cannot_appear_with_direct_customer_models(direct_model):
    with pytest.raises(ValidationError, match="cannot combine 'b2b2c'"):
        _valid_tags(customer_model=["b2b2c", direct_model])


def test_validation_failure_is_reasked_once():
    class Responses:
        def __init__(self):
            self.calls = []

        async def parse(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return SimpleNamespace(
                    output_parsed=_valid_tags(
                        parent_sector=[
                            "business_software",
                            "financial_services_insurance",
                            "health_life_sciences",
                        ]
                    ),
                    usage=None,
                )
            return SimpleNamespace(output_parsed=_valid_tags(), usage=None)

    responses = Responses()
    client = SimpleNamespace(responses=responses)
    result = asyncio.run(tag_companies.tag_one(
        client, asyncio.Semaphore(1), "01234567890", "Example", "Software",
        "https://example.it", "Homepage text", "OK", "OK", "http",
    ))

    assert result.tags == _valid_tags()
    assert len(responses.calls) == 2
    assert "previous classification was rejected" in (
        responses.calls[1]["input"][1]["content"]
    )
    assert responses.calls[1]["text_format"] is tag_companies.CompanyTags
    assert all(call["temperature"] == 0 for call in responses.calls)


def test_all_unclear_on_ok_page_is_reassessed_once():
    unclear = _valid_tags(
        parent_sector=["unclear"], sector="unclear",
        product_type=["unclear"], customer_model=["unclear"],
        one_line="Homepage describes connected safety products.",
    )

    class Responses:
        def __init__(self):
            self.calls = []

        async def parse(self, **kwargs):
            self.calls.append(kwargs)
            parsed = unclear if len(self.calls) == 1 else _valid_tags()
            return SimpleNamespace(output_parsed=parsed, usage=None)

    responses = Responses()
    result = asyncio.run(tag_companies.tag_one(
        SimpleNamespace(responses=responses), asyncio.Semaphore(1),
        "01234567890", "Example", "Software", "https://example.it",
        "Concrete product homepage text " * 30, "OK/ok", "OK", "http",
    ))

    assert result.tags == _valid_tags()
    assert len(responses.calls) == 2
    assert "Reassess the page once" in responses.calls[1]["input"][1]["content"]


def test_dead_homepage_is_unclear_without_calling_model(monkeypatch):
    def unexpected_client():
        raise AssertionError("an unreadable homepage must not reach the model")

    monkeypatch.setattr(tag_companies, "make_client", unexpected_client)
    sample = [(
        "02781910209", "FLAB S.R.L.", "Software production",
        "621000", "https://www.cantieresicuro.com", None,
    )]
    fetched = {
        "02781910209": tag_companies.Fetched(
            codice_fiscale="02781910209",
            url="https://www.cantieresicuro.com",
            text="",
            fetch_pass="none",
            fetch_bucket="DEAD",
            note="dns_failure",
        ),
    }

    [result] = asyncio.run(
        tag_companies.tag_all(sample, fetched, concurrency=1, dry_run=False)
    )

    assert result.tags.parent_sector == ["unclear"]
    assert result.tags.sector == "unclear"
    assert result.tags.product_type == ["unclear"]
    assert result.tags.customer_model == ["unclear"]
    assert result.page_chars == 0
    assert result.fetch_bucket == "DEAD"
    assert result.usage is None


def test_dry_run_results_are_never_written(monkeypatch):
    def unexpected_connect(*_args, **_kwargs):
        raise AssertionError("a dry run must not open a database connection")

    monkeypatch.setattr(tag_companies, "connect", unexpected_connect)
    stub = tag_companies.Tagged(
        "02781910209", "FLAB S.R.L.", "Software production",
        "https://www.cantieresicuro.com",
        tag_companies.stub_tags("FLAB S.R.L.", "OK"), None,
        page_chars=7045, fetch_bucket="OK", fetch_pass="http",
    )

    with pytest.raises(ValueError, match="must not be called for a dry run"):
        tag_companies.write_results([stub], dry_run=True)


def test_run_notes_state_tls_verification_policy():
    result = tag_companies.Tagged(
        "02781910209", "FLAB S.R.L.", "Software production",
        "https://www.cantieresicuro.com", _valid_tags(), None,
        page_chars=7045, fetch_bucket="OK", fetch_pass="browser",
    )

    notes = tag_companies.build_run_notes([result])

    assert "HTTP pass verifies TLS" in notes
    assert "browser pass deliberately accepts invalid TLS certificates" in notes


def test_openai_usage_accounting_includes_prompt_cache_rates():
    usages = [
        SimpleNamespace(
            input_tokens=2_000,
            output_tokens=100,
            input_tokens_details=SimpleNamespace(
                cached_tokens=1_200,
                cache_write_tokens=500,
            ),
        ),
        SimpleNamespace(
            input_tokens=1_500,
            output_tokens=80,
            input_tokens_details=SimpleNamespace(
                cached_tokens=0,
                cache_write_tokens=0,
            ),
        ),
    ]

    input_tokens, cached_tokens, cache_write_tokens, output_tokens, cost = (
        tag_companies.usage_totals(usages)
    )

    assert (input_tokens, cached_tokens, cache_write_tokens, output_tokens) == (
        3_500, 1_200, 500, 180,
    )
    assert cost == pytest.approx(
        1_800 / 1e6 * tag_companies.PRICE_IN_PER_MTOK
        + 1_200 / 1e6 * tag_companies.PRICE_CACHED_IN_PER_MTOK
        + 500 / 1e6 * tag_companies.PRICE_CACHE_WRITE_PER_MTOK
        + 180 / 1e6 * tag_companies.PRICE_OUT_PER_MTOK
    )


def test_luna_model_selection_updates_usage_prices():
    original = tag_companies.MODEL
    try:
        tag_companies.configure_model("gpt-5.6-luna")
        assert tag_companies.MODEL == "gpt-5.6-luna"
        assert (
            tag_companies.PRICE_IN_PER_MTOK,
            tag_companies.PRICE_CACHED_IN_PER_MTOK,
            tag_companies.PRICE_CACHE_WRITE_PER_MTOK,
            tag_companies.PRICE_OUT_PER_MTOK,
        ) == (0.20, 0.02, 0.25, 1.20)
    finally:
        tag_companies.configure_model(original)


def test_prompt_matches_multi_value_contract_and_keeps_precedence():
    prompt = tag_companies.SYSTEM_PROMPT
    assert "are LISTS of one or two" in prompt
    assert "marketplace beats software_product" in prompt
    assert "hedging is not free" in prompt
    assert '`["b2b", "b2c"]`' in prompt
    assert "Restaurants, catering, hotels, tourism, and travel" in prompt
    assert "podcasts" in prompt and "performing-arts institutions" in prompt
    assert "diagnostics applied to artworks" in prompt
    assert tag_companies.PROMPT_VERSION == "v5.1-product-boundaries-2026-09-13"


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


def test_export_pipe_joins_two_values_in_model_order():
    db_row = (
        "02201200678", "Example S.R.L.", "621000", "Software",
        "https://example.it",
        ["climate_energy_circular", "food_agriculture"],
        ["farm energy management"],
        ["software_product", "hardware_device"],
        ["b2b"], None,
        ["Manages renewable energy for farms."],
        "http", "OK", 1234,
        "https://example.it | 1234 chars of homepage text | fetch=OK | pass=http",
    )

    row = export_tags._export_row(db_row, run_id=7)

    assert row[5] == "climate_energy_circular|food_agriculture"
    assert row[7] == "software_product|hardware_device"


def test_enriched_export_appends_vc_relevance_and_reason():
    db_row = (
        "02201200678", "Example S.R.L.", "621000", "Software",
        "https://example.it", ["business_software"], ["workflow software"],
        ["software_product"], ["b2b"], None, ["Automates workflows."],
        "http", "OK", 1234, "evidence", ["high"],
        ["Repeatable software with validated demand."],
    )
    row = export_tags._export_row(db_row, run_id=13, include_vc=True)
    assert export_tags.VC_COLUMNS[-2:] == [
        "vc_relevance", "vc_relevance_reason",
    ]
    assert row[-2:] == ["high", "Repeatable software with validated demand."]


def test_export_uses_url_and_provenance_recorded_with_run():
    evidence = "https://fetched.example/path | 876 chars of homepage text | fetch=OK | pass=browser"
    assert export_tags._provenance(
        "https://current.example", None, None, None, evidence
    ) == ("https://fetched.example/path", "browser", "OK", 876)
