from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import eval_batch_quality  # noqa: E402
import score_vc_relevance  # noqa: E402
import tag_companies  # noqa: E402


ROW = (
    "01234567890", "EXAMPLE S.R.L.", "software", "621000",
    "https://example.it", "Milano",
)
FETCHED = tag_companies.Fetched(
    codice_fiscale=ROW[0], url=ROW[4],
    text="We sell repeatable workflow software to businesses. " * 20,
    fetch_pass="http", fetch_bucket="OK", note="ok",
)


def test_sync_and_batch_share_one_canonical_request_body():
    body = eval_batch_quality.request_body("taxonomy", ROW, FETCHED)

    assert body["model"] == "gpt-5.6-terra"
    assert body["temperature"] == 0
    assert body["reasoning"] == {"effort": "none"}
    assert body["max_output_tokens"] == 1024
    assert body["input"][0]["content"] == tag_companies.SYSTEM_PROMPT
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["strict"] is True


def test_vc_batch_body_uses_luna_and_frozen_vc_prompt():
    body = eval_batch_quality.request_body("vc", ROW, FETCHED)

    assert body["model"] == "gpt-5.6-luna"
    assert body["temperature"] == 0
    assert body["max_output_tokens"] == 512
    assert body["input"][0]["content"] == score_vc_relevance.SYSTEM_PROMPT


def test_batch_parser_applies_companytags_validator():
    invalid = """{
      "parent_sector": ["business_software", "education_workforce", "other"],
      "sector": "workflow software",
      "product_type": ["software_product"],
      "customer_model": ["b2b"],
      "one_line": "Workflow software."
    }"""

    with pytest.raises(ValueError, match="at most 2 items"):
        eval_batch_quality._parse_output("taxonomy", invalid)


def test_quality_gate_fails_if_batch_accuracy_regresses():
    sample = [ROW] * 40
    # Give the repeated fixture unique IDs so the gate's expected-size logic
    # remains representative without requiring real dev-set rows.
    sample = [((str(index).zfill(11)), *ROW[1:]) for index in range(40)]
    labels = {
        row[0]: {
            "parent_sector": ("business_software",),
            "product_type": ("software_product",),
            "customer_model": ("b2b",),
        }
        for row in sample
    }
    correct = {
        "parent_sector": ["business_software"],
        "sector": "workflow software",
        "product_type": ["software_product"],
        "customer_model": ["b2b"],
        "one_line": "Workflow software.",
    }
    sync = {
        "taxonomy": {row[0]: dict(correct) for row in sample},
        "vc": {row[0]: {"vc_relevance": "medium"} for row in sample},
    }
    batch = {
        "taxonomy": {row[0]: dict(correct) for row in sample},
        "vc": {row[0]: {"vc_relevance": "medium"} for row in sample},
    }
    batch["taxonomy"][sample[0][0]] = {
        **correct, "product_type": ["professional_services"],
    }

    passed, report = eval_batch_quality.quality_report(
        sample, labels, [sync, sync], batch,
    )

    assert passed is False
    assert any(
        "product_type: sync 40/40, 40/40; batch 39/40" in line
        for line in report
    )


def test_quality_gate_requires_exact_vc_label_agreement():
    sample = [ROW]
    labels = {
        ROW[0]: {
            "parent_sector": ("business_software",),
            "product_type": ("software_product",),
            "customer_model": ("b2b",),
        }
    }
    taxonomy = {
        "parent_sector": ["business_software"],
        "sector": "workflow software",
        "product_type": ["software_product"],
        "customer_model": ["b2b"],
        "one_line": "Workflow software.",
    }
    sync = {"taxonomy": {ROW[0]: taxonomy},
            "vc": {ROW[0]: {"vc_relevance": "high"}}}
    batch = {"taxonomy": {ROW[0]: taxonomy},
             "vc": {ROW[0]: {"vc_relevance": "medium"}}}

    passed, report = eval_batch_quality.quality_report(
        sample, labels, [sync, sync], batch,
    )

    assert passed is False
    assert any("vc_relevance sync 1 vs batch: 1/1" in line for line in report)


def test_quality_gate_accepts_batch_within_normal_run_variance():
    sample = [ROW]
    labels = {
        ROW[0]: {
            "parent_sector": ("business_software",),
            "product_type": ("software_product",),
            "customer_model": ("b2b",),
        }
    }
    taxonomy = {
        "parent_sector": ["business_software"],
        "sector": "workflow software",
        "product_type": ["software_product"],
        "customer_model": ["b2b"],
        "one_line": "Workflow software.",
    }
    sync_one = {"taxonomy": {ROW[0]: taxonomy},
                "vc": {ROW[0]: {"vc_relevance": "low"}}}
    sync_two = {"taxonomy": {ROW[0]: taxonomy},
                "vc": {ROW[0]: {"vc_relevance": "medium"}}}
    batch = {"taxonomy": {ROW[0]: taxonomy},
             "vc": {ROW[0]: {"vc_relevance": "medium"}}}

    passed, _report = eval_batch_quality.quality_report(
        sample, labels, [sync_one, sync_two], batch,
    )

    assert passed is True
