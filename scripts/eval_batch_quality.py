#!/usr/bin/env python3
"""Prove Batch API quality equivalence before using it on the registry.

The harness fetches the held-out 40-company dev set once, sends byte-equivalent
request bodies through the synchronous Responses API and the Batch API, and
compares both result sets. It never writes to Postgres and refuses the frozen
200-company scored sample.

    python scripts/eval_batch_quality.py run
    python scripts/eval_batch_quality.py check --state data/batch_quality/state.json
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import datetime
import hashlib
import json
import os
import pathlib
import time
from typing import Any, Literal

from dotenv import load_dotenv
from openai import OpenAI
from openai.lib._parsing._responses import type_to_text_format_param
from pydantic import BaseModel, ValidationError

import eval_prompt
import score_vc_relevance
import tag_companies
from db import REPO_ROOT


ARTIFACT_DIR = REPO_ROOT / "data" / "batch_quality"
DEFAULT_STATE = ARTIFACT_DIR / "state.json"
TERMINAL_BATCH_STATES = {"completed", "failed", "expired", "cancelled"}
TaskKind = Literal["taxonomy", "vc"]


def _json_dump(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _json_load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _model_for(kind: TaskKind) -> str:
    return tag_companies.MODEL if kind == "taxonomy" else "gpt-5.6-luna"


def _output_model(kind: TaskKind) -> type[BaseModel]:
    return (tag_companies.CompanyTags if kind == "taxonomy"
            else score_vc_relevance.VCRelevance)


def request_body(kind: TaskKind, row: tuple,
                 fetched: tag_companies.Fetched) -> dict[str, Any]:
    """Build the one canonical body used by both sync and Batch requests."""
    _cf, name, attivita, _ateco, url, _comune = row
    if kind == "taxonomy":
        system_prompt = tag_companies.SYSTEM_PROMPT
        user_message = tag_companies.build_user_message(
            name, attivita, url, fetched.text,
            f"{fetched.fetch_bucket}/{fetched.note}",
        )
        max_output_tokens = 1024
    else:
        system_prompt = score_vc_relevance.SYSTEM_PROMPT
        user_message = score_vc_relevance.build_user_message(
            name, attivita, url, fetched.text,
            f"{fetched.fetch_bucket}/{fetched.note}",
        )
        max_output_tokens = 512

    return {
        "model": _model_for(kind),
        "temperature": 0,
        "max_output_tokens": max_output_tokens,
        "reasoning": {"effort": "none"},
        "store": False,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "text": {"format": type_to_text_format_param(_output_model(kind))},
    }


def _unreadable(kind: TaskKind) -> BaseModel:
    return (tag_companies.unreadable_tags() if kind == "taxonomy"
            else score_vc_relevance.unreadable_relevance())


def _response_text(body: dict[str, Any]) -> str:
    for item in body.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return content.get("text", "")
    raise ValueError("Response has no output_text content")


def _parse_output(kind: TaskKind, text: str) -> BaseModel:
    return _output_model(kind).model_validate_json(text)


def snapshot_rows(sample: list[tuple],
                  fetched: dict[str, tag_companies.Fetched]) -> list[dict[str, Any]]:
    rows = []
    for cf, name, attivita, ateco, url, comune in sample:
        page = fetched[cf]
        rows.append({
            "codice_fiscale": cf,
            "denominazione": name,
            "attivita_label": attivita,
            "ateco": ateco,
            "website_url": url,
            "comune": comune,
            "fetch_pass": page.fetch_pass,
            "fetch_bucket": page.fetch_bucket,
            "fetch_note": page.note,
            "homepage_text": page.text,
        })
    return rows


def restore_snapshot(rows: list[dict[str, Any]]) -> tuple[list[tuple], dict[str, tag_companies.Fetched]]:
    sample = []
    fetched = {}
    for item in rows:
        cf = item["codice_fiscale"]
        sample.append((
            cf, item["denominazione"], item["attivita_label"], item["ateco"],
            item["website_url"], item.get("comune"),
        ))
        fetched[cf] = tag_companies.Fetched(
            codice_fiscale=cf,
            url=item["website_url"],
            text=item["homepage_text"],
            fetch_pass=item["fetch_pass"],
            fetch_bucket=item["fetch_bucket"],
            note=item["fetch_note"],
        )
    return sample, fetched


async def synchronous_baseline(sample: list[tuple],
                               fetched: dict[str, tag_companies.Fetched],
                               concurrency: int) -> dict[str, dict[str, Any]]:
    """Run canonical bodies synchronously; DEAD pages use the same local rule."""
    client = tag_companies.make_client()
    semaphore = asyncio.Semaphore(concurrency)
    output: dict[str, dict[str, Any]] = {"taxonomy": {}, "vc": {}}

    async def one(kind: TaskKind, row: tuple) -> tuple[TaskKind, str, BaseModel]:
        cf = row[0]
        page = fetched[cf]
        if page.fetch_bucket == "DEAD" or not page.text:
            return kind, cf, _unreadable(kind)
        async with semaphore:
            response = await client.responses.create(**request_body(kind, row, page))
        return kind, cf, _parse_output(kind, response.output_text)

    tasks = [
        asyncio.create_task(one(kind, row))
        for row in sample for kind in ("taxonomy", "vc")
    ]
    try:
        for index, task in enumerate(asyncio.as_completed(tasks), 1):
            kind, cf, result = await task
            output[kind][cf] = result.model_dump()
            if index % 20 == 0 or index == len(tasks):
                print(f"  synchronous {index}/{len(tasks)}", flush=True)
    finally:
        await client.close()
    return output


def write_batch_inputs(directory: pathlib.Path, sample: list[tuple],
                       fetched: dict[str, tag_companies.Fetched]) -> dict[str, pathlib.Path]:
    paths = {}
    for kind in ("taxonomy", "vc"):
        path = directory / f"{kind}_requests.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            for row in sample:
                cf = row[0]
                page = fetched[cf]
                if page.fetch_bucket == "DEAD" or not page.text:
                    continue
                request = {
                    "custom_id": f"{kind}:{cf}",
                    "method": "POST",
                    "url": "/v1/responses",
                    "body": request_body(kind, row, page),
                }
                fh.write(json.dumps(request, ensure_ascii=False, separators=(",", ":")))
                fh.write("\n")
        paths[kind] = path
    return paths


def submit(args) -> pathlib.Path:
    eval_prompt.refuse_frozen_sample(args.sample_file)
    labels = eval_prompt.load_labels(args.labels_file)
    sample, _stats = tag_companies.load_sample(args.sample_file)
    eval_prompt.validate_inputs(args.sample_file, sample, labels)

    run_dir = ARTIFACT_DIR / datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    print("Fetching the dev set once for both execution modes ...")
    fetched = asyncio.run(tag_companies.fetch_all(
        sample, args.fetch_concurrency, args.timeout,
        render_concurrency=args.render_concurrency,
        use_browser=not args.no_render,
    ))
    snapshot_path = run_dir / "fetch_snapshot.json"
    _json_dump(snapshot_path, snapshot_rows(sample, fetched))

    print("Running two synchronous controls with the saved inputs ...")
    baseline_paths = []
    for run_number in (1, 2):
        print(f"Synchronous control {run_number}/2")
        baseline = asyncio.run(synchronous_baseline(
            sample, fetched, args.api_concurrency,
        ))
        baseline_path = run_dir / f"synchronous_results_{run_number}.json"
        _json_dump(baseline_path, baseline)
        baseline_paths.append(str(baseline_path))

    inputs = write_batch_inputs(run_dir, sample, fetched)
    client = OpenAI()
    batches = {}
    input_meta = {}
    for kind, path in inputs.items():
        with path.open("rb") as fh:
            uploaded = client.files.create(file=fh, purpose="batch")
        batch = client.batches.create(
            input_file_id=uploaded.id,
            endpoint="/v1/responses",
            completion_window="24h",
            metadata={
                "purpose": "startup-map-quality-gate",
                "task": kind,
            },
        )
        batches[kind] = batch.id
        input_meta[kind] = {
            "path": str(path),
            "sha256": _sha256(path),
            "file_id": uploaded.id,
        }
        print(f"Submitted {kind}: {batch.id}")

    state = {
        "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "sample_file": str(args.sample_file.resolve()),
        "labels_file": str(args.labels_file.resolve()),
        "snapshot": str(snapshot_path),
        "synchronous_results": baseline_paths,
        "prompt_version": tag_companies.PROMPT_VERSION,
        "vc_prompt_version": score_vc_relevance.VC_PROMPT_VERSION,
        "models": {"taxonomy": _model_for("taxonomy"), "vc": _model_for("vc")},
        "inputs": input_meta,
        "batches": batches,
    }
    _json_dump(args.state, state)
    print(f"State: {args.state}")
    return args.state


def batch_status(client: OpenAI, state: dict[str, Any]) -> dict[str, Any]:
    return {kind: client.batches.retrieve(batch_id)
            for kind, batch_id in state["batches"].items()}


def _batch_results(client: OpenAI, batch, kind: TaskKind) -> dict[str, dict[str, Any]]:
    if not batch.output_file_id:
        raise ValueError(f"{kind} batch has no output file")
    content = client.files.content(batch.output_file_id).text
    results = {}
    failures = []
    for line in content.splitlines():
        item = json.loads(line)
        custom_id = item["custom_id"]
        response = item.get("response")
        if not response or response.get("status_code") != 200:
            failures.append((custom_id, item.get("error") or response))
            continue
        try:
            parsed = _parse_output(kind, _response_text(response["body"]))
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            failures.append((custom_id, f"{type(exc).__name__}: {exc}"))
            continue
        cf = custom_id.split(":", 1)[1]
        results[cf] = parsed.model_dump()
    if failures:
        details = "\n".join(f"  {key}: {error}" for key, error in failures)
        raise ValueError(f"{kind} batch has {len(failures)} invalid results:\n{details}")
    return results


def _sets(value: list[str]) -> set[str]:
    return set(value)


def _disagreement(first: dict[str, Any], second: dict[str, Any], kind: TaskKind,
                  field: str, expected_ids: set[str]) -> int:
    if kind == "taxonomy":
        return sum(
            _sets(first[kind][cf][field]) != _sets(second[kind][cf][field])
            for cf in expected_ids
        )
    return sum(
        first[kind][cf][field] != second[kind][cf][field]
        for cf in expected_ids
    )


def quality_report(sample: list[tuple], labels: dict[str, dict[str, Any]],
                   sync_runs: list[dict[str, dict[str, Any]]],
                   batch: dict[str, dict[str, Any]]) -> tuple[bool, list[str]]:
    lines = []
    passed = True
    total = len(sample)
    expected_ids = {row[0] for row in sample}
    if len(sync_runs) != 2:
        raise ValueError("The quality gate requires exactly two synchronous controls.")
    for kind in ("taxonomy", "vc"):
        modes = [(f"sync{index}", run[kind])
                 for index, run in enumerate(sync_runs, 1)]
        modes.append(("batch", batch[kind]))
        for mode, results in modes:
            missing = expected_ids - set(results)
            extra = set(results) - expected_ids
            if missing or extra:
                passed = False
                lines.append(f"{kind} {mode}: missing={sorted(missing)} extra={sorted(extra)}")

    lines.append("TAXONOMY ACCURACY (exact set-match)")
    for field in eval_prompt.SCORED_FIELDS:
        sync_correct = [sum(
            _sets(run["taxonomy"][cf][field]) == set(labels[cf][field])
            for cf in expected_ids if cf in run["taxonomy"]
        ) for run in sync_runs]
        batch_correct = sum(
            _sets(batch["taxonomy"][cf][field]) == set(labels[cf][field])
            for cf in expected_ids if cf in batch["taxonomy"]
        )
        if batch_correct < min(sync_correct):
            passed = False
        lines.append(
            f"  {field}: sync {sync_correct[0]}/{total}, {sync_correct[1]}/{total}; "
            f"batch {batch_correct}/{total}"
        )

    lines.append("EXECUTION VARIANCE (exact output disagreement)")
    for field in eval_prompt.SCORED_FIELDS:
        sync_variance = _disagreement(
            sync_runs[0], sync_runs[1], "taxonomy", field, expected_ids,
        )
        batch_distances = [
            _disagreement(run, batch, "taxonomy", field, expected_ids)
            for run in sync_runs
        ]
        if min(batch_distances) > sync_variance:
            passed = False
        lines.append(
            f"  {field}: sync-sync {sync_variance}/{total}; "
            f"batch-sync {batch_distances[0]}/{total}, {batch_distances[1]}/{total}"
        )

    lines.append("SYNC 1 vs BATCH DISAGREEMENTS (with ground truth)")
    for field in eval_prompt.SCORED_FIELDS:
        disagreements = [
            cf for cf in expected_ids
            if cf in sync_runs[0]["taxonomy"] and cf in batch["taxonomy"]
            and _sets(sync_runs[0]["taxonomy"][cf][field])
            != _sets(batch["taxonomy"][cf][field])
        ]
        lines.append(f"  {field}: {len(disagreements)}/{total}")
        for cf in sorted(disagreements):
            expected = set(labels[cf][field])
            sync_matches = _sets(sync_runs[0]["taxonomy"][cf][field]) == expected
            batch_matches = _sets(batch["taxonomy"][cf][field]) == expected
            if sync_matches and not batch_matches:
                outcome = "BATCH REGRESSION"
            elif batch_matches and not sync_matches:
                outcome = "BATCH FIX"
            elif sync_matches and batch_matches:
                outcome = "both correct"
            else:
                outcome = "both wrong"
            lines.append(
                f"    {cf}: sync={'|'.join(sync_runs[0]['taxonomy'][cf][field])} "
                f"batch={'|'.join(batch['taxonomy'][cf][field])} "
                f"truth={'|'.join(labels[cf][field])} [{outcome}]"
            )

    vc_sync_variance = _disagreement(
        sync_runs[0], sync_runs[1], "vc", "vc_relevance", expected_ids,
    )
    vc_batch_distances = [
        _disagreement(run, batch, "vc", "vc_relevance", expected_ids)
        for run in sync_runs
    ]
    if min(vc_batch_distances) > vc_sync_variance:
        passed = False
    lines.append(
        f"  vc_relevance variance: sync-sync {vc_sync_variance}/{total}; "
        f"batch-sync {vc_batch_distances[0]}/{total}, "
        f"{vc_batch_distances[1]}/{total}"
    )
    vc_disagreements = [cf for cf in expected_ids
                        if sync_runs[0]["vc"][cf]["vc_relevance"]
                        != batch["vc"][cf]["vc_relevance"]]
    lines.append(f"  vc_relevance sync 1 vs batch: {len(vc_disagreements)}/{total}")
    for cf in sorted(vc_disagreements):
        lines.append(
            f"    {cf}: sync={sync_runs[0]['vc'][cf]['vc_relevance']} "
            f"batch={batch['vc'][cf]['vc_relevance']}"
        )
    return passed, lines


def collect(state_path: pathlib.Path) -> bool | None:
    state = _json_load(state_path)
    if state["prompt_version"] != tag_companies.PROMPT_VERSION:
        raise SystemExit("The taxonomy prompt changed after submission; quality gate invalid.")
    if state["vc_prompt_version"] != score_vc_relevance.VC_PROMPT_VERSION:
        raise SystemExit("The VC prompt changed after submission; quality gate invalid.")
    current_models = {"taxonomy": _model_for("taxonomy"), "vc": _model_for("vc")}
    if state["models"] != current_models:
        raise SystemExit("A model changed after submission; quality gate invalid.")
    for kind, meta in state["inputs"].items():
        if _sha256(pathlib.Path(meta["path"])) != meta["sha256"]:
            raise SystemExit(f"{kind} Batch input changed after submission.")

    client = OpenAI()
    statuses = batch_status(client, state)
    for kind, batch in statuses.items():
        counts = getattr(batch, "request_counts", None)
        print(f"{kind}: {batch.status}"
              + (f" ({counts.completed}/{counts.total} completed, "
                 f"{counts.failed} failed)" if counts else ""))
    if any(batch.status not in TERMINAL_BATCH_STATES for batch in statuses.values()):
        return None
    bad = {kind: batch.status for kind, batch in statuses.items()
           if batch.status != "completed"}
    if bad:
        raise SystemExit(f"Batch quality gate cannot run: {bad}")

    sample, fetched = restore_snapshot(_json_load(pathlib.Path(state["snapshot"])))
    labels = eval_prompt.load_labels(pathlib.Path(state["labels_file"]))
    sync_paths = state["synchronous_results"]
    if isinstance(sync_paths, str):
        raise SystemExit(
            "This state has only one synchronous control; rerun the quality gate."
        )
    sync_runs = [_json_load(pathlib.Path(path)) for path in sync_paths]
    batch_results: dict[str, dict[str, Any]] = {}
    for kind in ("taxonomy", "vc"):
        batch_results[kind] = _batch_results(client, statuses[kind], kind)
        for row in sample:
            cf = row[0]
            page = fetched[cf]
            if page.fetch_bucket == "DEAD" or not page.text:
                batch_results[kind][cf] = _unreadable(kind).model_dump()
    _json_dump(state_path.parent / "batch_results.json", batch_results)

    passed, lines = quality_report(sample, labels, sync_runs, batch_results)
    report_path = state_path.parent / "quality_report.txt"
    report = "\n".join([*(lines), "", f"QUALITY GATE: {'PASS' if passed else 'FAIL'}", ""])
    report_path.write_text(report, encoding="utf-8")
    print("\n" + report)
    if passed:
        gate = {
            "passed_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "state": str(state_path.resolve()),
            "prompt_version": state["prompt_version"],
            "vc_prompt_version": state["vc_prompt_version"],
            "models": state["models"],
            "input_sha256": {kind: meta["sha256"]
                              for kind, meta in state["inputs"].items()},
        }
        _json_dump(state_path.parent / "quality_gate.json", gate)
    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def common(subparser) -> None:
        subparser.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)

    submit_parser = subparsers.add_parser("submit")
    common(submit_parser)
    submit_parser.add_argument("--sample-file", type=pathlib.Path,
                               default=eval_prompt.DEVSET_FILE)
    submit_parser.add_argument("--labels-file", type=pathlib.Path,
                               default=eval_prompt.LABELS_FILE)
    submit_parser.add_argument("--fetch-concurrency", type=int, default=16)
    submit_parser.add_argument("--render-concurrency", type=int, default=8)
    submit_parser.add_argument("--api-concurrency", type=int, default=8)
    submit_parser.add_argument("--timeout", type=float, default=8.0)
    submit_parser.add_argument("--no-render", action="store_true")

    check_parser = subparsers.add_parser("check")
    common(check_parser)

    run_parser = subparsers.add_parser("run", parents=[], add_help=True)
    common(run_parser)
    run_parser.add_argument("--sample-file", type=pathlib.Path,
                            default=eval_prompt.DEVSET_FILE)
    run_parser.add_argument("--labels-file", type=pathlib.Path,
                            default=eval_prompt.LABELS_FILE)
    run_parser.add_argument("--fetch-concurrency", type=int, default=16)
    run_parser.add_argument("--render-concurrency", type=int, default=8)
    run_parser.add_argument("--api-concurrency", type=int, default=8)
    run_parser.add_argument("--timeout", type=float, default=8.0)
    run_parser.add_argument("--no-render", action="store_true")
    run_parser.add_argument("--poll-seconds", type=int, default=30)
    run_parser.add_argument("--max-wait-minutes", type=int, default=60)

    args = parser.parse_args()
    load_dotenv(REPO_ROOT / ".env")
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set; add it to .env.")

    if args.command == "submit":
        submit(args)
        return
    if args.command == "check":
        result = collect(args.state)
        if result is None:
            raise SystemExit(2)
        if not result:
            raise SystemExit(1)
        return

    state_path = submit(args)
    deadline = time.monotonic() + args.max_wait_minutes * 60
    while time.monotonic() < deadline:
        result = collect(state_path)
        if result is not None:
            if not result:
                raise SystemExit(1)
            return
        time.sleep(args.poll_seconds)
    raise SystemExit(
        f"Batches are still running. Resume with: {__file__} check --state {state_path}"
    )


if __name__ == "__main__":
    main()
