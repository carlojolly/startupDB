#!/usr/bin/env python3
"""Recover high-confidence fetch/classification misses from a completed tag run.

The base run stays immutable. Only candidates matching narrow recovery rules
are re-fetched and reclassified; a new complete run is created transactionally
by copying the base and replacing those companies.

    python scripts/recover_tag_run.py --base-run-id 14
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
from typing import Any

import eval_batch_quality as batch_common
import score_vc_relevance
import tag_companies
import tag_registry_batch
from db import REPO_ROOT, connect


DEFAULT_FETCH_DIR = REPO_ROOT / "data/registry_batch/20260914T192223/fetch_chunks"


def dump(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_ids(base_run_id: int, fetch_dir: pathlib.Path) -> set[str]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT codice_fiscale
            FROM company_tags
            WHERE run_id = %s
            GROUP BY codice_fiscale
            HAVING max(fetch_bucket) = 'OK'
               AND count(*) FILTER (WHERE tag_type = 'parent_sector'
                                     AND tag_value <> 'unclear') = 0
               AND count(*) FILTER (WHERE tag_type = 'sector'
                                     AND tag_value <> 'unclear') = 0
               AND count(*) FILTER (WHERE tag_type = 'product_type'
                                     AND tag_value <> 'unclear') = 0
               AND count(*) FILTER (WHERE tag_type = 'customer_model'
                                     AND tag_value <> 'unclear') = 0
        """, (base_run_id,))
        ids = {str(row[0]) for row in cur.fetchall()}

    for path in sorted(fetch_dir.glob("*.json")):
        for row in load(path):
            if str(row.get("fetch_note", "")).startswith("offsite_redirect"):
                ids.add(str(row["codice_fiscale"]))
    return ids


def company_rows(ids: set[str]) -> list[tuple]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT codice_fiscale, denominazione, attivita_label, ateco_raw,
                   sito_internet_url, comune
            FROM companies_current
            WHERE codice_fiscale = ANY(%s)
            ORDER BY codice_fiscale
        """, (sorted(ids),))
        rows = [tuple(row) for row in cur.fetchall()]
    found = {str(row[0]) for row in rows}
    if found != ids:
        raise SystemExit(f"Candidate company lookup returned {len(found)}/{len(ids)} rows.")
    return rows


def restore_results(path: pathlib.Path) -> dict[str, dict[str, Any]]:
    saved = load(path)
    for value in saved["taxonomy"].values():
        tag_companies.CompanyTags.model_validate(value)
    for value in saved["vc"].values():
        score_vc_relevance.VCRelevance.model_validate(value)
    return saved


def write_recovered_run(base_run_id: int, sample: list[tuple], pages,
                        results: dict[str, dict[str, Any]]) -> int:
    marker = f"targeted_recovery_v3_base_run={base_run_id}"
    candidate_ids = {str(row[0]) for row in sample}
    if any(set(results[kind]) != candidate_ids for kind in ("taxonomy", "vc")):
        raise SystemExit("Recovery results do not exactly cover the candidate set.")
    improved_ids = {
        cf for cf in candidate_ids
        if pages[cf].fetch_bucket != "DEAD"
        and not (
            results["taxonomy"][cf]["parent_sector"] == ["unclear"]
            and results["taxonomy"][cf]["sector"] == "unclear"
            and results["taxonomy"][cf]["product_type"] == ["unclear"]
            and results["taxonomy"][cf]["customer_model"] == ["unclear"]
        )
    }
    improved_sample = [row for row in sample if str(row[0]) in improved_ids]
    improved_results = {
        kind: {cf: value for cf, value in results[kind].items()
               if cf in improved_ids}
        for kind in ("taxonomy", "vc")
    }

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT companies_tagged FROM tag_runs WHERE id = %s",
                    (base_run_id,))
        base = cur.fetchone()
        if not base or not base[0]:
            raise SystemExit(f"Base tag_run {base_run_id} is missing or incomplete.")
        expected = int(base[0])
        cur.execute("SELECT id FROM tag_runs WHERE notes LIKE %s LIMIT 1",
                    (f"%{marker}%",))
        existing = cur.fetchone()
        if existing:
            print(f"Recovery already written as tag_run {existing[0]}.")
            return existing[0]

        model = "gpt-5.6-terra taxonomy + gpt-5.6-luna VC (targeted recovery)"
        prompt = (f"{tag_companies.PROMPT_VERSION} + "
                  f"{score_vc_relevance.VC_PROMPT_VERSION}")
        notes = (f"{marker}; {len(candidate_ids)} candidates evaluated; "
                 f"{len(improved_ids)} demonstrated improvements applied; "
                 "base run copied unchanged for all other companies; exact-name "
                 "redirect verification; selected first-party page crawl; "
                 "all-unclear usable-page reassessment")
        cur.execute("INSERT INTO tag_runs (model,prompt_version,notes) "
                    "VALUES (%s,%s,%s) RETURNING id", (model, prompt, notes))
        run_id = cur.fetchone()[0]
        cur.execute("""
            INSERT INTO company_tags (
                codice_fiscale, run_id, tag_type, tag_value, confidence,
                evidence, source, fetch_pass, fetch_bucket, homepage_chars
            )
            SELECT codice_fiscale, %s, tag_type, tag_value, confidence,
                   evidence, source, fetch_pass, fetch_bucket, homepage_chars
            FROM company_tags WHERE run_id = %s
            ORDER BY id
        """, (run_id, base_run_id))
        cur.execute("DELETE FROM company_tags WHERE run_id = %s "
                    "AND codice_fiscale = ANY(%s)",
                    (run_id, sorted(improved_ids)))
        replacement = tag_registry_batch.database_rows(
            improved_sample, pages, improved_results, run_id
        )
        cur.executemany(
            "INSERT INTO company_tags (codice_fiscale,run_id,tag_type,tag_value,"
            "confidence,evidence,source,fetch_pass,fetch_bucket,homepage_chars) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", replacement
        )
        cur.execute("SELECT count(DISTINCT codice_fiscale) FROM company_tags "
                    "WHERE run_id = %s", (run_id,))
        actual = cur.fetchone()[0]
        if actual != expected:
            raise SystemExit(
                f"Reconstructed run covers {actual}/{expected} companies; rolled back."
            )
        cur.execute("UPDATE tag_runs SET finished_at=now(), companies_tagged=%s "
                    "WHERE id=%s", (expected, run_id))
        conn.commit()
    print(f"Wrote complete recovered tag_run {run_id}: {expected} companies, "
          f"{len(improved_ids)}/{len(candidate_ids)} candidates improved from "
          f"run {base_run_id}.")
    return run_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-run-id", type=int, required=True)
    parser.add_argument("--fetch-dir", type=pathlib.Path, default=DEFAULT_FETCH_DIR)
    parser.add_argument("--work-dir", type=pathlib.Path, default=None)
    parser.add_argument("--fetch-concurrency", type=int, default=16)
    parser.add_argument("--render-concurrency", type=int, default=4)
    parser.add_argument("--model-concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    work_dir = args.work_dir or (
        REPO_ROOT / "data" / f"recovery_run_{args.base_run_id}"
    )
    snapshot_path = work_dir / "fetch_snapshot.json"
    results_path = work_dir / "validated_results.json"

    ids = candidate_ids(args.base_run_id, args.fetch_dir)
    sample = company_rows(ids)
    print(f"Recovery candidates: {len(sample)}")

    if snapshot_path.exists():
        saved_sample, pages = batch_common.restore_snapshot(load(snapshot_path))
        if [row[0] for row in saved_sample] != [row[0] for row in sample]:
            raise SystemExit("Saved recovery snapshot does not match current candidates.")
        print(f"Using saved fetch checkpoint: {snapshot_path}")
    else:
        pages = asyncio.run(tag_companies.fetch_all(
            sample, args.fetch_concurrency, args.timeout,
            render_concurrency=args.render_concurrency,
        ))
        dump(snapshot_path, batch_common.snapshot_rows(sample, pages))
        print(f"Saved fetch checkpoint: {snapshot_path}")

    if results_path.exists():
        results = restore_results(results_path)
        print(f"Using validated result checkpoint: {results_path}")
    else:
        taxonomy = asyncio.run(tag_companies.tag_all(
            sample, pages, args.model_concurrency, dry_run=False
        ))
        errors = [item for item in taxonomy if item.error or not item.tags]
        if errors:
            raise SystemExit(f"Taxonomy failed for {len(errors)} companies; nothing written.")
        taxonomy_results = {item.cf: item.tags.model_dump() for item in taxonomy}
        taxonomy_usage = [item.usage for item in taxonomy if item.usage]
        taxonomy_cost = tag_companies.usage_totals(taxonomy_usage)[-1]

        tag_companies.configure_model("gpt-5.6-luna")
        try:
            vc = asyncio.run(score_vc_relevance.score_all(
                sample, pages, args.model_concurrency
            ))
            vc_errors = [item for item in vc if item.error]
            if vc_errors:
                raise SystemExit(f"VC scoring failed for {len(vc_errors)} companies; "
                                 "nothing written.")
            vc_results = {item.cf: item.relevance.model_dump() for item in vc}
            vc_usage = [item.usage for item in vc if item.usage]
            vc_cost = tag_companies.usage_totals(vc_usage)[-1]
        finally:
            tag_companies.configure_model("gpt-5.6-terra")

        results = {"taxonomy": taxonomy_results, "vc": vc_results}
        dump(results_path, results)
        print(f"Validated recovery results: taxonomy=${taxonomy_cost:.4f}, "
              f"vc=${vc_cost:.4f}")

    if args.no_write:
        print("Nothing written to Postgres (--no-write).")
    else:
        write_recovered_run(args.base_run_id, sample, pages, results)


if __name__ == "__main__":
    main()
