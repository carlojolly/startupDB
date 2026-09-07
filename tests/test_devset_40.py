"""Contract checks for the held-out prompt-development sample."""
from __future__ import annotations

import csv
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE = REPO_ROOT / "data" / "sample_200_2026-09-06.csv"
DEVSET = REPO_ROOT / "data" / "devset_40_2026-09-07.csv"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def test_devset_is_disjoint_stratified_and_normalized():
    raw = DEVSET.read_bytes()
    sample = read_rows(SAMPLE)
    devset = read_rows(DEVSET)
    sample_ids = {row["codice_fiscale"] for row in sample}
    devset_ids = {row["codice_fiscale"] for row in devset}

    assert len(devset) == len(devset_ids) == 40
    assert sample_ids.isdisjoint(devset_ids)
    assert [row["codice_fiscale"] for row in devset] == sorted(devset_ids)
    assert sum(row["ateco"] == "621000" for row in devset) == 28
    assert sum(row["ateco"] != "621000" for row in devset) == 12
    assert all(row["website_url"].startswith("https://") for row in devset)
    assert raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
