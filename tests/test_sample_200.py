"""Regression checks for the committed frozen 200-company sample."""
from __future__ import annotations

import csv
from pathlib import Path


SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_200_2026-09-06.csv"


def test_every_sample_website_url_is_normalized_https():
    with SAMPLE.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 200
    assert all(row["website_url"].startswith("https://") for row in rows)
