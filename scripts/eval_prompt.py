#!/usr/bin/env python3
"""Evaluate the current tagging prompt on the held-out 40-company dev set.

This script never writes tag_runs or company_tags. It fetches the dev-set
homepages once, runs the current prompt one or more times over the same text,
and compares the categorical predictions with hand-labelled ground truth.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import itertools
import pathlib

import tag_companies
from db import REPO_ROOT


DEVSET_FILE = REPO_ROOT / "data" / "devset_40_2026-09-07.csv"
LABELS_FILE = REPO_ROOT / "data" / "devset_labels_2026-09-07.csv"
FROZEN_SAMPLE_FILE = REPO_ROOT / "data" / "sample_200_2026-09-06.csv"
LABEL_COLUMNS = [
    "codice_fiscale", "parent_sector", "sector", "product_type",
    "customer_model",
]
SCORED_FIELDS = ("parent_sector", "product_type", "customer_model")


def parse_multi_value(value: str, field: str, codice_fiscale: str) -> tuple[str, ...]:
    values = tuple(part.strip() for part in value.split("|"))
    if not values or any(not part for part in values):
        raise ValueError(
            f"Empty {field} value for codice_fiscale {codice_fiscale}"
        )
    if len(values) != len(set(values)):
        raise ValueError(
            f"Duplicate {field} value for codice_fiscale {codice_fiscale}"
        )
    return values


def load_labels(path: pathlib.Path) -> dict[str, dict[str, object]]:
    """Load ordered label values; comparisons treat multi-values as sets."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames != LABEL_COLUMNS:
                raise ValueError(
                    f"Unexpected label columns in {path}: {reader.fieldnames}; "
                    f"expected {LABEL_COLUMNS}"
                )
            rows = list(reader)
    except FileNotFoundError:
        raise SystemExit(
            f"Ground-truth labels not found: {path}\n"
            "Finish the hand-labelled dev-set file before running prompt evals."
        ) from None

    labels: dict[str, dict[str, object]] = {}
    for row in rows:
        cf = row["codice_fiscale"].strip()
        if not cf:
            raise ValueError(f"Blank codice_fiscale in {path}")
        if cf in labels:
            raise ValueError(f"Duplicate codice_fiscale {cf} in {path}")
        sector = row["sector"].strip()
        if not sector:
            raise ValueError(f"Empty sector value for codice_fiscale {cf}")
        labels[cf] = {
            field: parse_multi_value(row[field], field, cf)
            for field in SCORED_FIELDS
        }
        labels[cf]["sector"] = sector
    return labels


def validate_inputs(sample_file: pathlib.Path, sample: list[tuple],
                    labels: dict[str, dict[str, object]]) -> None:
    """Keep prompt iteration strictly off the scored 200-company sample."""
    if sample_file.resolve() == FROZEN_SAMPLE_FILE.resolve() or len(sample) == 200:
        raise SystemExit(
            "Refusing to evaluate on the frozen 200-company benchmark sample. "
            f"Use the held-out dev set: {DEVSET_FILE}"
        )
    if len(sample) != 40:
        raise SystemExit(
            f"Prompt evaluation requires the complete 40-company dev set; "
            f"{sample_file} contains {len(sample)} rows."
        )

    sample_ids = {row[0] for row in sample}
    label_ids = set(labels)
    if sample_ids != label_ids:
        missing = sorted(sample_ids - label_ids)
        extra = sorted(label_ids - sample_ids)
        raise SystemExit(
            "Ground-truth IDs do not exactly match the dev set. "
            f"Missing labels: {missing or 'none'}; extra labels: {extra or 'none'}"
        )


def refuse_frozen_sample(sample_file: pathlib.Path) -> None:
    if sample_file.resolve() == FROZEN_SAMPLE_FILE.resolve():
        raise SystemExit(
            "Refusing to evaluate on the frozen 200-company benchmark sample. "
            f"Use the held-out dev set: {DEVSET_FILE}"
        )


def ordered_results(sample: list[tuple], results: list[tag_companies.Tagged]):
    by_id = {result.cf: result for result in results}
    return [by_id[row[0]] for row in sample]


def predicted_values(result: tag_companies.Tagged,
                     field: str) -> tuple[str, ...] | None:
    if result.tags is None:
        return None
    return tuple(getattr(result.tags, field))


def sets_match(predicted: tuple[str, ...] | None,
               expected: tuple[str, ...]) -> bool:
    return predicted is not None and set(predicted) == set(expected)


def display_values(values: tuple[str, ...] | None) -> str:
    return "<ERROR>" if values is None else "|".join(values)


def print_evaluation(run_number: int, sample: list[tuple],
                     results: list[tag_companies.Tagged],
                     labels: dict[str, dict[str, object]]) -> None:
    results = ordered_results(sample, results)
    print(f"\nEVALUATION — RUN {run_number}")
    print("=" * 72)
    for field in SCORED_FIELDS:
        correct = sum(
            sets_match(predicted_values(result, field), labels[result.cf][field])
            for result in results
        )
        print(f"{field:16} {correct:2}/{len(results)}  "
              f"{100 * correct / len(results):5.1f}% exact set-match")

    unclear = sum(
        result.tags is not None and result.tags.sector.strip().lower() == "unclear"
        for result in results
    )
    failures = sum(result.tags is None for result in results)
    print(f"{'sector unclear':16} {unclear:2}/{len(results)}  "
          f"{100 * unclear / len(results):5.1f}%")
    if failures:
        print(f"{'failed calls':16} {failures:2}/{len(results)}")

    disagreements = []
    for result in results:
        wrong = [
            field for field in SCORED_FIELDS
            if not sets_match(predicted_values(result, field),
                              labels[result.cf][field])
        ]
        if wrong:
            disagreements.append((result, wrong))

    print(f"\nDISAGREEMENTS — RUN {run_number}: {len(disagreements)} companies")
    if not disagreements:
        print("  none")
        return
    for result, wrong in disagreements:
        print(f"\n{result.cf}  {result.name}")
        if result.error:
            print(f"  error: {result.error}")
        for field in wrong:
            predicted = predicted_values(result, field)
            expected = labels[result.cf][field]
            print(f"  {field}: predicted={display_values(predicted)}  "
                  f"true={display_values(expected)}")
        predicted_sector = result.tags.sector if result.tags else "<ERROR>"
        print(f"  sector (not scored): predicted={predicted_sector!r}  "
              f"true={labels[result.cf]['sector']!r}")


def print_variance(sample: list[tuple],
                   runs: list[list[tag_companies.Tagged]]) -> None:
    """Report exact categorical disagreement between every pair of runs."""
    if len(runs) < 2:
        return
    ordered = [ordered_results(sample, results) for results in runs]
    for left_index, right_index in itertools.combinations(range(len(runs)), 2):
        left, right = ordered[left_index], ordered[right_index]
        print(f"\nVARIANCE — RUN {left_index + 1} vs RUN {right_index + 1}")
        print("=" * 72)
        any_disagreement = 0
        per_field = {field: 0 for field in SCORED_FIELDS}
        for left_result, right_result in zip(left, right, strict=True):
            row_differs = False
            for field in SCORED_FIELDS:
                left_values = predicted_values(left_result, field)
                right_values = predicted_values(right_result, field)
                if (left_values is None or right_values is None
                        or set(left_values) != set(right_values)):
                    per_field[field] += 1
                    row_differs = True
            any_disagreement += row_differs

        for field in SCORED_FIELDS:
            count = per_field[field]
            print(f"{field:16} {count:2}/{len(left)}  "
                  f"{100 * count / len(left):5.1f}% disagree")
        print(f"{'any categorical':16} {any_disagreement:2}/{len(left)}  "
              f"{100 * any_disagreement / len(left):5.1f}% disagree")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-file", type=pathlib.Path, default=DEVSET_FILE)
    parser.add_argument("--labels-file", type=pathlib.Path, default=LABELS_FILE)
    parser.add_argument("--runs", type=int, default=1,
                        help="Number of identical prompt runs (default: 1)")
    parser.add_argument("--fetch-concurrency", type=int, default=16)
    parser.add_argument("--render-concurrency", type=int, default=4)
    parser.add_argument("--api-concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")

    refuse_frozen_sample(args.sample_file)
    labels = load_labels(args.labels_file)
    sample, _stats = tag_companies.load_sample(args.sample_file)
    validate_inputs(args.sample_file, sample, labels)

    print(f"Loaded {len(sample)} held-out companies and {len(labels)} labels")
    print("Fetching homepages once; every prompt run uses the same fetched text ...")
    fetched = asyncio.run(tag_companies.fetch_all(
        sample, args.fetch_concurrency, args.timeout,
        render_concurrency=args.render_concurrency,
        use_browser=not args.no_render,
    ))

    runs = []
    for run_number in range(1, args.runs + 1):
        print(f"\nTagging run {run_number}/{args.runs} with "
              f"{tag_companies.MODEL} / {tag_companies.PROMPT_VERSION} ...")
        results = asyncio.run(tag_companies.tag_all(
            sample, fetched, args.api_concurrency, dry_run=False,
        ))
        runs.append(results)
        print_evaluation(run_number, sample, results, labels)
    print_variance(sample, runs)


if __name__ == "__main__":
    main()
