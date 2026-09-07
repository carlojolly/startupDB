"""Regression checks for the committed frozen 200-company sample."""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path


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
