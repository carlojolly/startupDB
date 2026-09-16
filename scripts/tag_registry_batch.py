#!/usr/bin/env python3
"""Run the website-eligible registry through the validated Batch pipeline.

    python scripts/tag_registry_batch.py prepare
    python scripts/tag_registry_batch.py submit
    python scripts/tag_registry_batch.py check --write

Homepage fetches are checkpointed. Nothing reaches Postgres until all outputs
from both models pass local Pydantic validation.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import datetime
import hashlib
import json
import os
import pathlib
import time
import uuid
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

import build_sample_200
import eval_batch_quality as batch_common
import score_vc_relevance
import tag_companies
from db import REPO_ROOT, connect


ARTIFACT_DIR = REPO_ROOT / "data" / "registry_batch"
DEFAULT_STATE = ARTIFACT_DIR / "state.json"
QUALITY_GATE = REPO_ROOT / "data" / "batch_quality" / "quality_gate.json"
TERMINAL_STATES = {"completed", "failed", "expired", "cancelled"}
KINDS = ("taxonomy", "vc")


def json_dump(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def json_load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def models() -> dict[str, str]:
    return {"taxonomy": tag_companies.MODEL, "vc": "gpt-5.6-luna"}


def registry_rows() -> list[tuple]:
    """Read the same cleaned 9,620-company pool used by the benchmark."""
    eligible = build_sample_200.eligible_companies(
        build_sample_200.read_source()
    )
    return [(
        cf, row["denominazione"], row["attività"], row["ateco 2007"],
        url, row["comune"],
    ) for cf, (row, url) in sorted(eligible.items())]


def serialize_row(row: tuple) -> dict[str, Any]:
    cf, name, activity, ateco, url, comune = row
    return {"codice_fiscale": cf, "denominazione": name,
            "attivita_label": activity, "ateco": ateco,
            "website_url": url, "comune": comune}


def restore_row(item: dict[str, Any]) -> tuple:
    return (item["codice_fiscale"], item["denominazione"],
            item["attivita_label"], item["ateco"], item["website_url"],
            item.get("comune"))


def validate_quality_gate(path: pathlib.Path = QUALITY_GATE) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit("Batch quality gate is missing; run eval_batch_quality.py.")
    gate = json_load(path)
    expected = {"prompt_version": tag_companies.PROMPT_VERSION,
                "vc_prompt_version": score_vc_relevance.VC_PROMPT_VERSION,
                "models": models()}
    stale = [key for key, value in expected.items() if gate.get(key) != value]
    if stale:
        raise SystemExit("Batch quality gate is stale for: " + ", ".join(stale))
    return gate


def validate_state(state: dict[str, Any]) -> None:
    checks = {
        "source_sha256": sha256(build_sample_200.SOURCE),
        "prompt_version": tag_companies.PROMPT_VERSION,
        "vc_prompt_version": score_vc_relevance.VC_PROMPT_VERSION,
        "models": models(),
    }
    changed = [key for key, value in checks.items() if state.get(key) != value]
    if changed:
        raise SystemExit("Registry Batch state is stale for: " + ", ".join(changed))


def create_state(path: pathlib.Path, chunk_size: int,
                 batch_chunk_size: int) -> dict[str, Any]:
    if path.exists():
        state = json_load(path)
        validate_state(state)
        if state["chunk_size"] != chunk_size:
            raise SystemExit("Cannot change fetch chunk size after the job starts.")
        if state["batch_chunk_size"] != batch_chunk_size:
            raise SystemExit("Cannot change Batch chunk size after the job starts.")
        return state
    sample = registry_rows()
    run_dir = ARTIFACT_DIR / datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    companies = run_dir / "companies.json"
    json_dump(companies, [serialize_row(row) for row in sample])
    state = {
        "job_id": str(uuid.uuid4()),
        "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "source_sha256": sha256(build_sample_200.SOURCE),
        "company_count": len(sample), "companies": str(companies),
        "run_dir": str(run_dir), "chunk_size": chunk_size,
        "batch_chunk_size": batch_chunk_size,
        "prompt_version": tag_companies.PROMPT_VERSION,
        "vc_prompt_version": score_vc_relevance.VC_PROMPT_VERSION,
        "models": models(), "parts": [],
    }
    json_dump(path, state)
    return state


def load_companies(state: dict[str, Any]) -> list[tuple]:
    rows = [restore_row(item) for item in json_load(pathlib.Path(state["companies"]))]
    if len(rows) != state["company_count"] or len({row[0] for row in rows}) != len(rows):
        raise SystemExit("Saved company list is incomplete or contains duplicates.")
    return rows


def chunk_path(state: dict[str, Any], index: int) -> pathlib.Path:
    return pathlib.Path(state["run_dir"]) / "fetch_chunks" / f"{index:05d}.json"


def load_fetches(state: dict[str, Any], sample: list[tuple], require_all=True):
    fetched = {}
    size = state["chunk_size"]
    for index, start in enumerate(range(0, len(sample), size)):
        path = chunk_path(state, index)
        if not path.exists():
            if require_all:
                raise SystemExit(f"Homepage fetch incomplete at chunk {index}; run prepare.")
            continue
        chunk_sample, pages = batch_common.restore_snapshot(json_load(path))
        expected = {row[0] for row in sample[start:start + size]}
        if {row[0] for row in chunk_sample} != expected:
            raise SystemExit(f"Fetch checkpoint {path} has the wrong companies.")
        if set(fetched) & set(pages):
            raise SystemExit(f"Fetch checkpoint {path} contains duplicate IDs.")
        fetched.update(pages)
    if require_all and set(fetched) != {row[0] for row in sample}:
        raise SystemExit("Fetch checkpoints do not cover the registry.")
    return fetched


def prepare(args) -> dict[str, Any]:
    state = create_state(args.state, args.fetch_chunk_size,
                         args.batch_chunk_size)
    sample = load_companies(state)
    size = state["chunk_size"]
    total = (len(sample) + size - 1) // size
    print(f"Registry: {len(sample):,} URL-eligible companies in {total} chunks")
    for index, start in enumerate(range(0, len(sample), size)):
        path = chunk_path(state, index)
        chunk = sample[start:start + size]
        if path.exists():
            print(f"Fetch chunk {index + 1}/{total}: checkpoint exists")
            continue
        print(f"Fetch chunk {index + 1}/{total}: {len(chunk)} companies")
        pages = asyncio.run(tag_companies.fetch_all(
            chunk, args.fetch_concurrency, args.timeout,
            render_concurrency=args.render_concurrency,
            use_browser=not args.no_render,
        ))
        json_dump(path, batch_common.snapshot_rows(chunk, pages))
        buckets = collections.Counter(page.fetch_bucket for page in pages.values())
        print(f"  checkpointed {path.name}: {dict(buckets)}", flush=True)
    pages = load_fetches(state, sample)
    state["coverage"] = {
        "fetch_bucket": dict(collections.Counter(p.fetch_bucket for p in pages.values())),
        "fetch_pass": dict(collections.Counter(p.fetch_pass for p in pages.values())),
    }
    state["fetch_completed_at"] = datetime.datetime.now(datetime.UTC).isoformat()
    json_dump(args.state, state)
    print(f"Fetch complete: {state['coverage']}")
    return state


def upload(client: OpenAI, kind: str, path: pathlib.Path, purpose: str):
    with path.open("rb") as fh:
        file = client.files.create(file=fh, purpose="batch")
    batch = client.batches.create(
        input_file_id=file.id, endpoint="/v1/responses",
        completion_window="24h", metadata={"purpose": purpose, "task": kind},
    )
    return batch.id, file.id


def submit_next_part(state_path: pathlib.Path, state: dict[str, Any],
                     sample: list[tuple], pages, client: OpenAI) -> bool:
    incomplete = (state["parts"][-1] if state["parts"]
                  and not state["parts"][-1].get("completed_at")
                  and set(state["parts"][-1]["batches"]) != set(KINDS)
                  else None)
    if incomplete:
        part = incomplete
        part_index = part["index"]
        wanted = set(part["company_ids"])
        part_sample = [row for row in sample if row[0] in wanted]
    else:
        part_index = len(state["parts"])
        start = part_index * state["batch_chunk_size"]
        part_sample = sample[start:start + state["batch_chunk_size"]]
        if not part_sample:
            return False
        part = {"index": part_index,
                "company_ids": [row[0] for row in part_sample],
                "batches": {}, "inputs": {}, "retry_batches": {}}
        state["parts"].append(part)
        json_dump(state_path, state)
    part_dir = pathlib.Path(state["run_dir"]) / "parts" / f"{part_index:04d}"
    part_dir.mkdir(parents=True, exist_ok=True)
    inputs = batch_common.write_batch_inputs(part_dir, part_sample, pages)
    print(f"Submitting Batch part {part_index + 1}/"
          f"{(len(sample) + state['batch_chunk_size'] - 1) // state['batch_chunk_size']} "
          f"({len(part_sample)} companies)")
    for kind in KINDS:
        if kind in part["batches"]:
            continue
        batch_id, file_id = upload(client, kind, inputs[kind],
                                   "startup-map-full-registry")
        part["batches"][kind] = batch_id
        part["inputs"][kind] = {"path": str(inputs[kind]),
                                "sha256": sha256(inputs[kind]),
                                "file_id": file_id}
        print(f"Submitted {kind}: {batch_id}")
        json_dump(state_path, state)
    return True


def submit(args) -> dict[str, Any]:
    state = json_load(args.state)
    validate_state(state)
    if state["parts"] and set(state["parts"][-1]["batches"]) == set(KINDS):
        print(f"Batch processing already started with {len(state['parts'])} part(s).")
        return state
    gate = validate_quality_gate(args.quality_gate)
    sample = load_companies(state)
    pages = load_fetches(state, sample)
    client = OpenAI()
    state["quality_gate"] = {"path": str(args.quality_gate.resolve()),
                             "passed_at": gate["passed_at"]}
    state["submitted_at"] = datetime.datetime.now(datetime.UTC).isoformat()
    submit_next_part(args.state, state, sample, pages, client)
    json_dump(args.state, state)
    return state


def read_output(client, batch, kind: str, path: pathlib.Path):
    if not batch.output_file_id:
        raise SystemExit(f"Completed {kind} batch has no output file.")
    content = client.files.content(batch.output_file_id).text
    path.write_text(content, encoding="utf-8")
    results, failures, usages = {}, {}, []
    for line in content.splitlines():
        item = json.loads(line)
        cf = item["custom_id"].split(":", 1)[1]
        response = item.get("response")
        if not response or response.get("status_code") != 200:
            failures[cf] = str(item.get("error") or response)
            continue
        body = response["body"]
        if body.get("usage"):
            usages.append(body["usage"])
        try:
            parsed = batch_common._parse_output(
                kind, batch_common._response_text(body)
            )
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            failures[cf] = f"{type(exc).__name__}: {exc}"
            continue
        results[cf] = parsed.model_dump()
    return results, failures, usages


def corrective_body(kind: str, row: tuple, page, error: str):
    body = batch_common.request_body(kind, row, page)
    body["input"][1]["content"] += (
        "\n\nYour previous classification was rejected because it failed the "
        f"output contract: {error}. Return a corrected classification. For "
        "taxonomy, keep each list to one or two ordered values and obey all "
        "combination rules."
    )
    return body


def submit_retries(client, state_path, state, part, sample, pages,
                   failures) -> None:
    by_id = {row[0]: row for row in sample}
    run_dir = pathlib.Path(state["run_dir"])
    for kind in KINDS:
        if not failures[kind]:
            continue
        path = run_dir / f"{kind}_retry_requests.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            for cf in sorted(failures[kind]):
                request = {"custom_id": f"{kind}:{cf}", "method": "POST",
                           "url": "/v1/responses",
                           "body": corrective_body(kind, by_id[cf], pages[cf],
                                                   failures[kind][cf])}
                fh.write(json.dumps(request, ensure_ascii=False,
                                    separators=(",", ":")) + "\n")
        batch_id, file_id = upload(client, kind, path,
                                   "startup-map-full-registry-retry")
        part["retry_batches"][kind] = batch_id
        part.setdefault("retry_inputs", {})[kind] = {
            "path": str(path), "sha256": sha256(path), "file_id": file_id,
            "company_ids": sorted(failures[kind]),
        }
        print(f"Submitted {kind} retry for {len(failures[kind])}: {batch_id}")
    json_dump(state_path, state)


def batch_cost(kind: str, usages: list[dict[str, Any]]) -> dict[str, Any]:
    input_tokens = sum(u.get("input_tokens", 0) for u in usages)
    output_tokens = sum(u.get("output_tokens", 0) for u in usages)
    cached = sum(u.get("input_tokens_details", {}).get("cached_tokens", 0)
                 for u in usages)
    writes = sum(u.get("input_tokens_details", {}).get("cache_write_tokens", 0)
                 for u in usages)
    p_in, p_cached, p_write, p_out = tag_companies.MODEL_PRICING[models()[kind]]
    cost = .5 * ((input_tokens - cached - writes) / 1e6 * p_in
                 + cached / 1e6 * p_cached + writes / 1e6 * p_write
                 + output_tokens / 1e6 * p_out)
    return {"requests": len(usages), "input_tokens": input_tokens,
            "cached_tokens": cached, "cache_write_tokens": writes,
            "output_tokens": output_tokens, "estimated_usd": round(cost, 6)}


def status_line(kind: str, batch) -> str:
    counts = getattr(batch, "request_counts", None)
    detail = (f" ({counts.completed}/{counts.total} completed, "
              f"{counts.failed} failed)") if counts else ""
    return f"{kind}: {batch.status}{detail}"


def queue_limit_failure(batch) -> bool:
    """Return true when OpenAI rejected a whole batch before processing it."""
    errors = getattr(getattr(batch, "errors", None), "data", None) or []
    counts = getattr(batch, "request_counts", None)
    return (
        batch.status == "failed"
        and any(getattr(error, "code", None) == "token_limit_exceeded"
                for error in errors)
        and (counts is None or counts.completed == counts.failed == 0)
    )


def resubmit_queue_limited_batches(client, state_path, state, part,
                                   batches) -> bool:
    """Replace only batches rejected by the organization queue-token cap."""
    limited = {kind: batch for kind, batch in batches.items()
               if queue_limit_failure(batch)}
    other_bad = {kind: batch.status for kind, batch in batches.items()
                 if batch.status != "completed" and kind not in limited}
    if not limited or other_bad:
        return False
    history = part.setdefault("queue_limit_retries", {})
    for kind in limited:
        attempts = history.setdefault(kind, [])
        if len(attempts) >= 6:
            raise SystemExit(
                f"{kind} hit the Batch queue-token limit six times; "
                "nothing was written."
            )
        old_id = part["batches"][kind]
        replacement = client.batches.create(
            input_file_id=part["inputs"][kind]["file_id"],
            endpoint="/v1/responses", completion_window="24h",
            metadata={"purpose": "startup-map-full-registry",
                      "task": kind},
        )
        attempts.append(old_id)
        part["batches"][kind] = replacement.id
        print(f"Resubmitted queue-limited {kind}: {replacement.id}")
    json_dump(state_path, state)
    return True


def collect(args) -> bool | None:
    state = json_load(args.state)
    validate_state(state)
    sample = load_companies(state)
    pages = load_fetches(state, sample)
    if not state["parts"]:
        raise SystemExit("No Batch parts submitted; run submit first.")
    part = state["parts"][-1]
    for kind, meta in part["inputs"].items():
        if sha256(pathlib.Path(meta["path"])) != meta["sha256"]:
            raise SystemExit(f"{kind} request file changed after submission.")
    client = OpenAI()
    batches = {kind: client.batches.retrieve(part["batches"][kind])
               for kind in KINDS}
    for kind, batch in batches.items():
        print(status_line(kind, batch))
    if any(b.status not in TERMINAL_STATES for b in batches.values()):
        return None
    if resubmit_queue_limited_batches(client, args.state, state, part, batches):
        return None
    bad = {kind: b.status for kind, b in batches.items() if b.status != "completed"}
    if bad:
        raise SystemExit(f"Registry batches did not complete: {bad}")

    run_dir = (pathlib.Path(state["run_dir"]) / "parts" /
               f"{part['index']:04d}")
    results, failures, usages = {}, {}, {}
    part_ids = set(part["company_ids"])
    part_sample = [row for row in sample if row[0] in part_ids]
    expected_api = {row[0] for row in part_sample
                    if pages[row[0]].fetch_bucket != "DEAD" and pages[row[0]].text}
    for kind in KINDS:
        results[kind], failures[kind], usages[kind] = read_output(
            client, batches[kind], kind, run_dir / f"{kind}_output.jsonl"
        )
        missing = expected_api - set(results[kind]) - set(failures[kind])
        failures[kind].update({cf: "missing from Batch output" for cf in missing})
    if any(failures.values()) and not part["retry_batches"]:
        submit_retries(client, args.state, state, part, part_sample, pages,
                       failures)
        return None
    if part["retry_batches"]:
        retries = {kind: client.batches.retrieve(batch_id)
                   for kind, batch_id in part["retry_batches"].items()}
        for kind, batch in retries.items():
            print(status_line(f"{kind} retry", batch))
        if any(b.status not in TERMINAL_STATES for b in retries.values()):
            return None
        bad = {kind: b.status for kind, b in retries.items()
               if b.status != "completed"}
        if bad:
            raise SystemExit(f"Corrective batches did not complete: {bad}")
        for kind, retry in retries.items():
            fixed, still_bad, retry_usage = read_output(
                client, retry, kind, run_dir / f"{kind}_retry_output.jsonl"
            )
            if still_bad:
                raise SystemExit(f"{kind} has {len(still_bad)} invalid results "
                                 "after retry; nothing was written.")
            results[kind].update(fixed)
            usages[kind].extend(retry_usage)
            failures[kind] = {}
    for row in part_sample:
        cf = row[0]
        if pages[cf].fetch_bucket == "DEAD" or not pages[cf].text:
            results["taxonomy"][cf] = tag_companies.unreadable_tags().model_dump()
            results["vc"][cf] = score_vc_relevance.unreadable_relevance().model_dump()
    expected = part_ids
    for kind in KINDS:
        if set(results[kind]) != expected:
            raise SystemExit(f"{kind} result IDs do not exactly cover the registry.")
    result_path = run_dir / "validated_results.json"
    json_dump(result_path, results)
    part["validated_results"] = str(result_path)
    part["usage"] = {kind: batch_cost(kind, usages[kind]) for kind in KINDS}
    part["completed_at"] = datetime.datetime.now(datetime.UTC).isoformat()
    json_dump(run_dir / "usage.json", part["usage"])
    json_dump(args.state, state)
    print(f"Validated part {part['index'] + 1}: {len(part_sample)} companies; "
          f"usage={part['usage']}")
    if submit_next_part(args.state, state, sample, pages, client):
        return None

    combined = {kind: {} for kind in KINDS}
    totals = {kind: collections.Counter() for kind in KINDS}
    for saved_part in state["parts"]:
        if not saved_part.get("validated_results"):
            raise SystemExit("A prior Batch part lacks validated results.")
        saved = json_load(pathlib.Path(saved_part["validated_results"]))
        for kind in KINDS:
            combined[kind].update(saved[kind])
            totals[kind].update(saved_part["usage"][kind])
    full_expected = {row[0] for row in sample}
    if any(set(combined[kind]) != full_expected for kind in KINDS):
        raise SystemExit("Combined Batch parts do not cover the registry.")
    full_path = pathlib.Path(state["run_dir"]) / "validated_results.json"
    json_dump(full_path, combined)
    state["validated_results"] = str(full_path)
    state["usage"] = {kind: dict(totals[kind]) for kind in KINDS}
    state["validated_at"] = datetime.datetime.now(datetime.UTC).isoformat()
    json_dump(pathlib.Path(state["run_dir"]) / "usage.json", state["usage"])
    json_dump(args.state, state)
    print(f"Validated all {len(sample):,} companies; usage={state['usage']}")
    if args.write:
        write_database(args.state)
    else:
        print("Nothing written to Postgres; rerun check with --write.")
    return True


def database_rows(sample, pages, results, run_id: int) -> list[tuple]:
    rows = []
    for cf, _name, _activity, _ateco, url, _comune in sample:
        page = pages[cf]
        source = "rule" if page.fetch_bucket == "DEAD" or not page.text else "llm"
        evidence = (f"{url} | {page.chars} chars of homepage text "
                    f"| fetch={page.fetch_bucket} | pass={page.fetch_pass}")
        taxonomy = tag_companies.CompanyTags.model_validate(results["taxonomy"][cf])
        vc = score_vc_relevance.VCRelevance.model_validate(results["vc"][cf])
        for field in tag_companies.TAG_FIELDS:
            value = getattr(taxonomy, field)
            for tag_value in value if isinstance(value, list) else [value]:
                rows.append((cf, run_id, field, tag_value, None, evidence, source,
                             page.fetch_pass, page.fetch_bucket, page.chars))
        for field in ("vc_relevance", "vc_relevance_reason"):
            rows.append((cf, run_id, field, getattr(vc, field), None, evidence,
                         source, page.fetch_pass, page.fetch_bucket, page.chars))
    return rows


def write_database(state_path: pathlib.Path) -> int:
    state = json_load(state_path)
    validate_state(state)
    if state.get("db_run_id"):
        print(f"Already written as tag_run {state['db_run_id']}.")
        return state["db_run_id"]
    if not state.get("validated_results"):
        raise SystemExit("Results have not been validated; run check first.")
    sample = load_companies(state)
    pages = load_fetches(state, sample)
    results = json_load(pathlib.Path(state["validated_results"]))
    expected = {row[0] for row in sample}
    if any(set(results[kind]) != expected for kind in KINDS):
        raise SystemExit("Validated result IDs no longer match this job.")
    marker = f"registry_batch_job={state['job_id']}"
    cost = sum(item["estimated_usd"] for item in state["usage"].values())
    notes = (f"{marker}; {len(sample)} website-eligible registry companies; "
             f"taxonomy={state['models']['taxonomy']} ({state['prompt_version']}); "
             f"vc={state['models']['vc']} ({state['vc_prompt_version']}); "
             f"OpenAI Batch API; batch_parts={len(state['parts'])}; "
             f"coverage={state['coverage']}; estimated_api_cost_usd={cost:.4f}; "
             "HTTP pass verifies TLS; browser pass deliberately accepts invalid "
             "TLS certificates for text-only retrieval")
    model = f"{state['models']['taxonomy']} taxonomy + {state['models']['vc']} VC (Batch)"
    prompt = f"{state['prompt_version']} + {state['vc_prompt_version']}"
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM tag_runs WHERE notes LIKE %s LIMIT 1",
                    (f"%{marker}%",))
        existing = cur.fetchone()
        if existing:
            run_id = existing[0]
        else:
            ids = sorted(expected)
            cur.execute("SELECT count(*) FROM companies WHERE codice_fiscale = ANY(%s)",
                        (ids,))
            present = cur.fetchone()[0]
            if present != len(ids):
                raise SystemExit(f"Database has {present}/{len(ids)} companies; "
                                 "import the registry first. Nothing was written.")
            cur.execute("INSERT INTO tag_runs (model, prompt_version, notes) "
                        "VALUES (%s,%s,%s) RETURNING id", (model, prompt, notes))
            run_id = cur.fetchone()[0]
            rows = database_rows(sample, pages, results, run_id)
            cur.executemany(
                "INSERT INTO company_tags (codice_fiscale,run_id,tag_type,tag_value,"
                "confidence,evidence,source,fetch_pass,fetch_bucket,homepage_chars) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", rows)
            cur.execute("UPDATE tag_runs SET finished_at=now(), companies_tagged=%s "
                        "WHERE id=%s", (len(sample), run_id))
        conn.commit()
    state["db_run_id"] = run_id
    state["written_at"] = datetime.datetime.now(datetime.UTC).isoformat()
    json_dump(state_path, state)
    print(f"Wrote full-registry results as tag_run {run_id}.")
    return run_id


def prepare_args(parser) -> None:
    parser.add_argument("--fetch-chunk-size", type=int, default=500)
    parser.add_argument("--batch-chunk-size", type=int, default=400)
    parser.add_argument("--fetch-concurrency", type=int, default=24)
    parser.add_argument("--render-concurrency", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--no-render", action="store_true")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p_prepare = commands.add_parser("prepare")
    p_prepare.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    prepare_args(p_prepare)
    p_submit = commands.add_parser("submit")
    p_submit.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    p_submit.add_argument("--quality-gate", type=pathlib.Path, default=QUALITY_GATE)
    p_check = commands.add_parser("check")
    p_check.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    p_check.add_argument("--write", action="store_true")
    p_run = commands.add_parser("run")
    p_run.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    p_run.add_argument("--quality-gate", type=pathlib.Path, default=QUALITY_GATE)
    p_run.add_argument("--poll-seconds", type=int, default=60)
    p_run.add_argument("--write", action="store_true")
    prepare_args(p_run)
    args = parser.parse_args()
    load_dotenv(REPO_ROOT / ".env")
    if args.command in {"submit", "check", "run"} and not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set; add it to .env.")
    if args.command == "prepare":
        prepare(args)
    elif args.command == "submit":
        submit(args)
    elif args.command == "check":
        if collect(args) is None:
            raise SystemExit(2)
    else:
        prepare(args)
        submit(args)
        while collect(args) is None:
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
