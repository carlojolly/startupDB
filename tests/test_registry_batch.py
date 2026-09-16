from __future__ import annotations

import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import tag_registry_batch  # noqa: E402


class Attrs:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_registry_pool_is_clean_complete_and_stably_ordered():
    rows = tag_registry_batch.registry_rows()
    assert len(rows) == 9_620
    assert [row[0] for row in rows] == sorted(row[0] for row in rows)
    assert len({row[0] for row in rows}) == 9_620
    assert all(row[4].startswith("https://") for row in rows)


def test_queue_limit_failure_requires_zero_processed_requests():
    error = Attrs(code="token_limit_exceeded")
    rejected = Attrs(status="failed", errors=Attrs(data=[error]),
                     request_counts=Attrs(completed=0, failed=0))
    partial = Attrs(status="failed", errors=Attrs(data=[error]),
                    request_counts=Attrs(completed=1, failed=0))

    assert tag_registry_batch.queue_limit_failure(rejected)
    assert not tag_registry_batch.queue_limit_failure(partial)


def test_quality_gate_must_match_prompts_and_models(tmp_path):
    gate = tmp_path / "gate.json"
    gate.write_text(json.dumps({
        "passed_at": "2026-09-14T00:00:00Z",
        "prompt_version": "stale",
        "vc_prompt_version": "vc-relevance-v1-2026-09-13",
        "models": {"taxonomy": "gpt-5.6-terra", "vc": "gpt-5.6-luna"},
    }))
    with pytest.raises(SystemExit, match="quality gate is stale"):
        tag_registry_batch.validate_quality_gate(gate)


def test_corrective_body_preserves_request_and_adds_validator_error():
    row = ("01234567890", "EXAMPLE S.R.L.", "software", "621000",
           "https://example.it", "Milano")
    page = tag_registry_batch.tag_companies.Fetched(
        codice_fiscale=row[0], url=row[4], text="Product homepage text",
        fetch_pass="http", fetch_bucket="OK", note="ok",
    )
    body = tag_registry_batch.corrective_body(
        "taxonomy", row, page, "parent_sector has 3 values"
    )
    assert body["model"] == "gpt-5.6-terra"
    assert body["temperature"] == 0
    assert "parent_sector has 3 values" in body["input"][1]["content"]
    assert "one or two ordered values" in body["input"][1]["content"]


def test_batch_cost_applies_half_price_and_cache_rates():
    summary = tag_registry_batch.batch_cost("taxonomy", [{
        "input_tokens": 2_000, "output_tokens": 100,
        "input_tokens_details": {
            "cached_tokens": 1_000, "cache_write_tokens": 500,
        },
    }])
    # Half of: 500*2/M + 1000*.2/M + 500*2.5/M + 100*12/M.
    assert summary["estimated_usd"] == pytest.approx(0.001825)


def test_database_rows_include_ordered_taxonomy_and_vc():
    sample = [("01234567890", "EXAMPLE S.R.L.", "software", "621000",
               "https://example.it", "Milano")]
    pages = {sample[0][0]: tag_registry_batch.tag_companies.Fetched(
        codice_fiscale=sample[0][0], url=sample[0][4], text="Homepage",
        fetch_pass="http", fetch_bucket="OK", note="ok",
    )}
    results = {
        "taxonomy": {sample[0][0]: {
            "parent_sector": ["business_software", "education_workforce"],
            "sector": "training software",
            "product_type": ["software_product", "tech_enabled_service"],
            "customer_model": ["b2b", "b2g"],
            "one_line": "Training software for employers and public agencies.",
        }},
        "vc": {sample[0][0]: {
            "vc_relevance": "medium",
            "vc_relevance_reason": "Repeatable software; traction is unclear.",
        }},
    }
    rows = tag_registry_batch.database_rows(sample, pages, results, run_id=99)
    assert [row[3] for row in rows if row[2] == "parent_sector"] == [
        "business_software", "education_workforce",
    ]
    assert [row[2] for row in rows][-2:] == [
        "vc_relevance", "vc_relevance_reason",
    ]


def test_submit_part_creates_its_artifact_directory(tmp_path, monkeypatch):
    row = ("01234567890", "EXAMPLE S.R.L.", "software", "621000",
           "https://example.it", "Milano")
    page = tag_registry_batch.tag_companies.Fetched(
        codice_fiscale=row[0], url=row[4], text="Homepage",
        fetch_pass="http", fetch_bucket="OK", note="ok",
    )
    state_path = tmp_path / "state.json"
    state = {"run_dir": str(tmp_path / "run"), "batch_chunk_size": 400,
             "parts": []}
    uploaded = []

    def fake_upload(_client, kind, path, _purpose):
        assert path.exists()
        uploaded.append(kind)
        return f"batch-{kind}", f"file-{kind}"

    monkeypatch.setattr(tag_registry_batch, "upload", fake_upload)
    submitted = tag_registry_batch.submit_next_part(
        state_path, state, [row], {row[0]: page}, object()
    )

    assert submitted is True
    assert uploaded == ["taxonomy", "vc"]
    assert (tmp_path / "run" / "parts" / "0000" /
            "taxonomy_requests.jsonl").exists()
