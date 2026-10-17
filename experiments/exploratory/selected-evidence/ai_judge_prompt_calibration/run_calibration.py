"""Run frozen prompt profiles against the paired calibration dataset."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from calibration_core import build_user_prompt, parse_json_object, sanitize_findings, score_findings
from prompt_profiles import PROMPT_PROFILES


ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = ROOT / "dataset" / "cases.jsonl"
EXPECTED_BASELINE_HASH = "50d083c5e7100d2e"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_cases(path: Path) -> tuple[list[dict[str, Any]], str]:
    text = path.read_text(encoding="utf-8")
    cases = [json.loads(line) for line in text.splitlines() if line.strip()]
    case_ids = [case["case_id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Dataset has duplicate case_id values")
    return cases, sha256_text(text)


def display_dataset_path(path: Path) -> str:
    resolved = path.resolve()
    repo_root = ROOT.parents[1]
    try:
        return resolved.relative_to(repo_root).as_posix()
    except ValueError:
        return f"<EXTERNAL_DATASET>/{resolved.name}"


def repository_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def chat_completions_url(base_url: str) -> str:
    value = base_url.rstrip("/")
    if value.endswith("/chat/completions"):
        return value
    if value.endswith("/v1"):
        return f"{value}/chat/completions"
    return f"{value}/v1/chat/completions"


def request_once(
    url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> tuple[dict[str, Any], str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8")
    response_json = json.loads(body)
    content = response_json["choices"][0]["message"]["content"]
    return response_json, str(content)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as target:
        target.write(canonical_json(value) + "\n")
        target.flush()


def write_manifest(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["baseline_v3", "calibrated_v4"],
        choices=sorted(PROMPT_PROFILES),
    )
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--case-limit", type=int)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-delay-seconds", type=float, default=2.0)
    parser.add_argument("--request-delay-seconds", type=float, default=0.0)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=900)
    parser.add_argument("--seed", type=int, default=3407)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.repetitions <= 0 or args.retries <= 0:
        raise SystemExit("repetitions and retries must be positive")
    cases, dataset_hash = read_cases(args.dataset.resolve())
    if args.case_limit is not None:
        if args.case_limit <= 0:
            raise SystemExit("case-limit must be positive")
        cases = cases[: args.case_limit]
    if PROMPT_PROFILES["baseline_v3"].prompt_hash != EXPECTED_BASELINE_HASH:
        raise SystemExit("baseline_v3 no longer matches the Run 13 prompt hash")
    prompt_hashes = {
        name: PROMPT_PROFILES[name].prompt_hash for name in args.profiles
    }
    planned_calls = len(cases) * len(args.profiles) * args.repetitions
    validation = {
        "dataset": display_dataset_path(args.dataset),
        "dataset_sha256": dataset_hash,
        "case_count": len(cases),
        "profiles": args.profiles,
        "prompt_hashes": prompt_hashes,
        "repetitions": args.repetitions,
        "planned_calls": planned_calls,
        "candidate_code_executed": False,
    }
    if args.validate_only:
        print(json.dumps(validation, indent=2))
        return 0
    if args.output_dir is None:
        raise SystemExit("--output-dir is required unless --validate-only is used")

    base_url = os.getenv("AI_JUDGE_BASE_URL", "").strip()
    model = os.getenv("AI_JUDGE_MODEL", "qwen3-coder:30b").strip()
    api_key = os.getenv("AI_JUDGE_API_KEY", "ollama")
    if not base_url:
        raise SystemExit("AI_JUDGE_BASE_URL must be configured in the shell")
    endpoint = chat_completions_url(base_url)

    output_dir = args.output_dir.resolve()
    manifest_path = output_dir / "run_manifest.json"
    calls_path = output_dir / "calls.jsonl"
    if output_dir.exists() and not args.resume:
        raise SystemExit(f"Refusing to overwrite existing output directory: {output_dir}")
    if args.resume and not manifest_path.exists():
        raise SystemExit("--resume requires an existing run_manifest.json")
    output_dir.mkdir(parents=True, exist_ok=args.resume)

    configuration = {
        **validation,
        "repository_commit": repository_commit(),
        "model": model,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "seed": args.seed,
        "timeout_seconds": args.timeout_seconds,
        "retries": args.retries,
        "retry_delay_seconds": args.retry_delay_seconds,
        "request_delay_seconds": args.request_delay_seconds,
        "endpoint": "<configured>",
    }

    completed: set[tuple[str, str, int]] = set()
    if args.resume:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        previous_configuration = manifest["configuration"]
        if previous_configuration != configuration:
            raise SystemExit("Resume configuration differs from the existing manifest")
        if calls_path.exists():
            for line in calls_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    record = json.loads(line)
                    completed.add(
                        (record["profile"], record["case_id"], record["repetition"])
                    )
    else:
        manifest = {
            "run_type": "ai_judge_prompt_calibration",
            "state": "running",
            "started_at_utc": utc_now(),
            "configuration": configuration,
            "completed_calls": 0,
            "error_calls": 0,
        }
        write_manifest(manifest_path, manifest)

    for profile_name in args.profiles:
        profile = PROMPT_PROFILES[profile_name]
        for case in cases:
            for repetition in range(1, args.repetitions + 1):
                key = (profile_name, case["case_id"], repetition)
                if key in completed:
                    continue
                user_prompt = build_user_prompt(profile, case)
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": profile.system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": args.temperature,
                    "top_p": args.top_p,
                    "max_tokens": args.max_tokens,
                    "stream": False,
                    "seed": args.seed,
                    "response_format": {"type": "json_object"},
                }
                record: dict[str, Any] = {
                    "profile": profile_name,
                    "prompt_version": profile.version,
                    "prompt_hash": profile.prompt_hash,
                    "case_id": case["case_id"],
                    "pair_id": case["pair_id"],
                    "condition": case["condition"],
                    "expected_subcategories": case["expected_subcategories"],
                    "target_subcategory": case["target_subcategory"],
                    "repetition": repetition,
                    "request_sha256": sha256_text(canonical_json(payload)),
                    "started_at_utc": utc_now(),
                    "candidate_code_executed": False,
                }
                started = time.perf_counter()
                last_error: Exception | None = None
                for attempt in range(1, args.retries + 1):
                    try:
                        response_json, raw_content = request_once(
                            endpoint, api_key, payload, args.timeout_seconds
                        )
                        parsed = parse_json_object(raw_content)
                        if str(parsed.get("status", "")).strip() != "ok":
                            raise ValueError("Judge status is not 'ok'")
                        findings = sanitize_findings(parsed, case["candidate_code"])
                        record.update(
                            {
                                "status": "ok",
                                "attempts": attempt,
                                "raw_content": raw_content,
                                "raw_response_metadata": {
                                    key: response_json.get(key)
                                    for key in ("id", "created", "model", "usage")
                                    if key in response_json
                                },
                                "parsed_response": parsed,
                                "raw_finding_count": len(parsed.get("findings", [])),
                                "sanitized_findings": findings,
                                "sanitized_finding_count": len(findings),
                                "predicted_subcategories": sorted(
                                    {item["subcategory"] for item in findings}
                                ),
                                "score": score_findings(findings),
                            }
                        )
                        last_error = None
                        break
                    except Exception as exc:  # preserve a final error as evidence
                        last_error = exc
                        if attempt < args.retries:
                            time.sleep(args.retry_delay_seconds * attempt)
                record["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
                record["finished_at_utc"] = utc_now()
                if last_error is not None:
                    message = str(last_error).replace(base_url, "<configured>")
                    record.update(
                        {
                            "status": "error",
                            "attempts": args.retries,
                            "error_type": type(last_error).__name__,
                            "error_message": message[:500],
                        }
                    )
                append_jsonl(calls_path, record)
                completed.add(key)
                manifest["completed_calls"] = len(completed)
                manifest["error_calls"] = sum(
                    json.loads(line).get("status") == "error"
                    for line in calls_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
                write_manifest(manifest_path, manifest)
                print(
                    f"{len(completed)}/{planned_calls} {profile_name} "
                    f"{case['case_id']} repetition={repetition} status={record['status']}",
                    flush=True,
                )
                if args.request_delay_seconds:
                    time.sleep(args.request_delay_seconds)

    manifest["state"] = "complete"
    manifest["finished_at_utc"] = utc_now()
    manifest["completed_calls"] = len(completed)
    write_manifest(manifest_path, manifest)
    print(json.dumps({"output_dir": str(output_dir), **manifest}, indent=2))
    return 0 if manifest["error_calls"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
