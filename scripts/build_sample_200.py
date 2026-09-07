"""Build the frozen benchmark and held-out development samples.

Both seeds are fixed to their sample freeze dates. Once generated, both tagging
pipelines must use these committed CSVs rather than drawing their own samples.
"""
from __future__ import annotations

import csv
import hashlib
import random
from pathlib import Path

from clean import clean_website


REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "data" / "raw" / "startup_2026-08-30.csv"
SAMPLE_OUTPUT = REPO_ROOT / "data" / "sample_200_2026-09-06.csv"
DEVSET_OUTPUT = REPO_ROOT / "data" / "devset_40_2026-09-07.csv"
SAMPLE_SEED = 20260906
DEVSET_SEED = 20260907

OUTPUT_COLUMNS = [
    "codice_fiscale",
    "denominazione",
    "ateco",
    "attivita_label",
    "website_url",
]

# The original frozen sample from docs/tagging-contract-v4.md section 5.
FROZEN_50 = (
    "02201200678", "02213700665", "02389720505", "02546170446",
    "02573700503", "02608010977", "02748430465", "02758170209",
    "02763610223", "02777080397", "02836200416", "02851180030",
    "03016790994", "03059700843", "03091510358", "03190720304",
    "03482960733", "03841040540", "03981650132", "03991140785",
    "04126421207", "04190980369", "04511290167", "04583160165",
    "04878730169", "04961240613", "05076270239", "05182200757",
    "05735930280", "07396210820", "09650761217", "10102211215",
    "10820971215", "11056941211", "11504620961", "11588050960",
    "12395800969", "12885490966", "13075840960", "13378230968",
    "13408430018", "13418880962", "13849000966", "13964370962",
    "13989710960", "14121000963", "14313550965", "14464950964",
    "16597601000", "18197041009",
)


def read_source() -> list[dict[str, str]]:
    with SOURCE.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def eligible_companies(
    rows: list[dict[str, str]],
) -> dict[str, tuple[dict[str, str], str]]:
    """Return source rows keyed by codice fiscale with normalized URLs."""
    eligible = {}
    for row in rows:
        cf = row["codice fiscale"].strip()
        website_url, _domain = clean_website(row["sito internet"])
        if cf and website_url:
            eligible[cf] = (row, website_url)

    eligible_target = sum(
        row["ateco 2007"].strip() == "621000"
        for row, _website_url in eligible.values()
    )
    if len(eligible) != 9_620 or eligible_target != 4_259:
        raise ValueError(
            f"Expected 9,620 eligible companies split 4,259/5,361; got "
            f"{len(eligible)} split {eligible_target}/{len(eligible) - eligible_target}"
        )
    return eligible


def draw_stratified(
    eligible: dict[str, tuple[dict[str, str], str]],
    *,
    target_count: int,
    other_count: int,
    seed: int,
    include: set[str] | frozenset[str] = frozenset(),
    exclude: set[str] | frozenset[str] = frozenset(),
) -> list[dict[str, str]]:
    """Draw a deterministic 621000/other sample and return it sorted by CF."""
    included = set(include)
    excluded = set(exclude)
    if included & excluded:
        raise ValueError("Included companies cannot also be excluded")

    missing = sorted(included - eligible.keys())
    if missing:
        raise ValueError(f"Included companies missing or ineligible: {missing}")

    included_target = sum(
        eligible[cf][0]["ateco 2007"].strip() == "621000" for cf in included
    )
    included_other = len(included) - included_target
    draw_target = target_count - included_target
    draw_other = other_count - included_other
    if draw_target < 0 or draw_other < 0:
        raise ValueError("Included companies exceed the requested stratum counts")

    target_pool = sorted(
        cf for cf, (row, _website_url) in eligible.items()
        if cf not in included | excluded
        and row["ateco 2007"].strip() == "621000"
    )
    other_pool = sorted(
        cf for cf, (row, _website_url) in eligible.items()
        if cf not in included | excluded
        and row["ateco 2007"].strip() != "621000"
    )
    if len(target_pool) < draw_target or len(other_pool) < draw_other:
        raise ValueError("Not enough eligible companies for the requested draw")

    rng = random.Random(seed)
    selected = included | set(rng.sample(target_pool, draw_target))
    selected |= set(rng.sample(other_pool, draw_other))

    sample = []
    for cf in sorted(selected):
        row, website_url = eligible[cf]
        sample.append({
            "codice_fiscale": row["codice fiscale"],
            "denominazione": row["denominazione"],
            "ateco": row["ateco 2007"],
            "attivita_label": row["attività"],
            "website_url": website_url,
        })

    actual_target = sum(row["ateco"].strip() == "621000" for row in sample)
    expected_total = target_count + other_count
    if len(sample) != expected_total or actual_target != target_count:
        raise ValueError(
            f"Expected {expected_total} companies split "
            f"{target_count}/{other_count}; got "
            f"{len(sample)} split {actual_target}/{len(sample) - actual_target}"
        )
    return sample


def build_sample(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Build the scored 200-company sample; retained as the public entry point."""
    return draw_stratified(
        eligible_companies(rows),
        target_count=140,
        other_count=60,
        seed=SAMPLE_SEED,
        include=set(FROZEN_50),
    )


def write_sample(rows: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=OUTPUT_COLUMNS,
            lineterminator="\n",
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source_rows = read_source()
    eligible = eligible_companies(source_rows)
    sample = draw_stratified(
        eligible,
        target_count=140,
        other_count=60,
        seed=SAMPLE_SEED,
        include=set(FROZEN_50),
    )
    sample_ids = {row["codice_fiscale"] for row in sample}
    devset = draw_stratified(
        eligible,
        target_count=28,
        other_count=12,
        seed=DEVSET_SEED,
        exclude=sample_ids,
    )
    write_sample(sample, SAMPLE_OUTPUT)
    write_sample(devset, DEVSET_OUTPUT)

    print(f"Source: {len(source_rows)} companies")
    print("Eligible: 9,620 companies (4,259 ATECO 621000, 5,361 other)")
    print(f"Sample: seed={SAMPLE_SEED}, 140 ATECO 621000, 60 other, "
          f"sha256={sha256(SAMPLE_OUTPUT)}")
    print(f"Dev set: seed={DEVSET_SEED}, 28 ATECO 621000, 12 other, "
          f"sha256={sha256(DEVSET_OUTPUT)}")
    print(f"Frozen 50 included: {set(FROZEN_50).issubset(row['codice_fiscale'] for row in sample)}")
    print(f"Intersection: {len(sample_ids & {row['codice_fiscale'] for row in devset})}")


if __name__ == "__main__":
    main()
