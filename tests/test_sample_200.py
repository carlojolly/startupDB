"""Regression checks for the committed frozen 200-company sample."""
from __future__ import annotations

import csv
import hashlib
import pathlib
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import export_tags  # noqa: E402
import tag_companies  # noqa: E402


SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_200_2026-09-06.csv"


def test_every_sample_website_url_is_normalized_https():
    with SAMPLE.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 200
    assert all(row["website_url"].startswith("https://") for row in rows)


def test_scored_sample_hash_is_frozen():
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest() == (
        "3892e5006f3edf04e30f45b20b8b585bd275308f68411984d612ca6ef1b474db"
    )


def test_loader_returns_all_companies_in_file_order():
    with SAMPLE.open(encoding="utf-8-sig", newline="") as fh:
        file_rows = list(csv.DictReader(fh))

    sample, stats = tag_companies.load_sample(SAMPLE)

    assert len(sample) == 200
    assert [row[0] for row in sample] == [row["codice_fiscale"] for row in file_rows]
    assert stats == {
        "pool_total": 200,
        "pool_621000": 140,
        "picked_621000": 140,
        "picked_other": 60,
    }


def test_loader_limit_keeps_first_rows_in_file_order():
    full_sample, _stats = tag_companies.load_sample(SAMPLE)
    limited_sample, _stats = tag_companies.load_sample(SAMPLE, limit=10)

    assert limited_sample == full_sample[:10]


@pytest.mark.parametrize("row_count", [0, 50, 199, 201])
def test_export_rejects_non_200_company_runs(row_count):
    with pytest.raises(SystemExit, match="requires exactly 200"):
        export_tags._require_contract_row_count([None] * row_count, run_id=12)
