"""Build the frozen 200-company benchmark sample from the registry CSV.

The seed is intentionally fixed at 20260906, matching the sample freeze date.
Once generated, both tagging pipelines must use the same committed CSV rather
than drawing their own samples.
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

from clean import clean_website


REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "data" / "raw" / "startup_2026-08-30.csv"
OUTPUT = REPO_ROOT / "data" / "sample_200_2026-09-06.csv"
SEED = 20260906

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


def build_sample(rows: list[dict[str, str]]) -> list[dict[str, str]]:
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

    frozen = set(FROZEN_50)

    missing = sorted(frozen - eligible.keys())
    if missing:
        raise ValueError(f"Frozen companies missing or ineligible: {missing}")

    frozen_target = sum(eligible[cf][0]["ateco 2007"].strip() == "621000"
                        for cf in frozen)
    if frozen_target != 35:
        raise ValueError(
            f"Expected frozen 50 to split 35/15 by ATECO; got "
            f"{frozen_target}/{50 - frozen_target}"
        )

    target_pool = sorted(
        cf for cf, (row, _website_url) in eligible.items()
        if cf not in frozen and row["ateco 2007"].strip() == "621000"
    )
    other_pool = sorted(
        cf for cf, (row, _website_url) in eligible.items()
        if cf not in frozen and row["ateco 2007"].strip() != "621000"
    )

    rng = random.Random(SEED)
    selected = frozen | set(rng.sample(target_pool, 105))
    selected |= set(rng.sample(other_pool, 45))

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

    target_count = sum(row["ateco"].strip() == "621000" for row in sample)
    if len(sample) != 200 or target_count != 140:
        raise ValueError(
            f"Expected 200 companies split 140/60; got "
            f"{len(sample)} split {target_count}/{len(sample) - target_count}"
        )
    return sample


def write_sample(rows: list[dict[str, str]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=OUTPUT_COLUMNS,
            lineterminator="\n",
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    source_rows = read_source()
    sample = build_sample(source_rows)
    write_sample(sample)

    target_count = sum(row["ateco"].strip() == "621000" for row in sample)
    print(f"Seed: {SEED}")
    print(f"Source: {len(source_rows)} companies")
    print("Eligible: 9,620 companies (4,259 ATECO 621000, 5,361 other)")
    print(f"Sample: {len(sample)} companies ({target_count} ATECO 621000, "
          f"{len(sample) - target_count} other)")
    print(f"Frozen 50 included: {set(FROZEN_50).issubset(row['codice_fiscale'] for row in sample)}")
    print(f"Wrote: {OUTPUT}")


if __name__ == "__main__":
    main()
