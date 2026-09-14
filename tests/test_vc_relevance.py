from __future__ import annotations

import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import score_vc_relevance  # noqa: E402


def test_unreadable_homepage_is_always_unclear():
    result = score_vc_relevance.unreadable_relevance()
    assert result.vc_relevance == "unclear"
    assert "Homepage unavailable" in result.vc_relevance_reason


def test_review_csv_preserves_input_order_and_has_review_evidence(tmp_path):
    first = score_vc_relevance.Scored(
        "2", "Second", "621000", "software", "https://second.example",
        score_vc_relevance.VCRelevance(
            vc_relevance="medium",
            vc_relevance_reason="Repeatable product, but market evidence is limited.",
        ),
        "http", "OK", 900,
    )
    second = score_vc_relevance.Scored(
        "1", "First", "000000", "other", "https://first.example",
        score_vc_relevance.VCRelevance(
            vc_relevance="low",
            vc_relevance_reason="The offering is bespoke and headcount-bound.",
        ),
        "browser", "THIN", 120,
    )
    output = tmp_path / "review.csv"

    score_vc_relevance.write_review(output, [first, second])

    with output.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [row["codice_fiscale"] for row in rows] == ["2", "1"]
    assert rows[0]["vc_relevance"] == "medium"
    assert rows[0]["vc_relevance_reason"].startswith("Repeatable product")
    assert rows[0]["fetch_bucket"] == "OK"

    restored = score_vc_relevance.read_review(output)
    assert [result.cf for result in restored] == ["2", "1"]
    assert restored[0].relevance.vc_relevance == "medium"
    assert restored[0].homepage_chars == 900


def test_database_rows_store_label_reason_and_prompt_provenance():
    result = score_vc_relevance.Scored(
        "1", "Company", "621000", "software", "https://company.example",
        score_vc_relevance.VCRelevance(
            vc_relevance="high",
            vc_relevance_reason="Scalable product with validated demand.",
        ),
        "browser", "OK", 1200,
    )

    rows = score_vc_relevance.db_tag_rows([result], run_id=12)

    assert [row[2] for row in rows] == [
        "vc_relevance", "vc_relevance_reason",
    ]
    assert [row[3] for row in rows] == [
        "high", "Scalable product with validated demand.",
    ]
    assert all("vc_prompt=vc-relevance-v1-2026-09-13" in row[5] for row in rows)
    assert all(row[6] == "llm" for row in rows)
