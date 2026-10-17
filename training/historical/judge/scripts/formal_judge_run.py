"""CPU-safe planning/connectivity/health; training only on explicit run command."""
import argparse
import ast
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from judge_reliability import JudgeFailure, record_event, request_judge, validate_response

BASELINE = "8cc4accd0c687a040543a791e472e3f5b236e2e2"
BACKEND = "Qwen2.5-32B-Instruct-AWQ"
FILES = ["train.py", "judge_reliability.py", "scripts/formal_judge_run.py",
         "run_correctness_judge.sh", "configs/correctness_judge_3seeds.sh",
         "configs/correctness_judge_smoke.sh"]
STAGES = ["eval_base", "eval_base_holdout", "train", "eval_lora", "eval_lora_holdout"]
PRIVATE_KEYS = {"AI_JUDGE_BASE_URL", "AI_JUDGE_API_KEY", "AI_JUDGE_MODEL"}


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def literals(path):
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = shlex.split(line, comments=True)
        if not parts:
            continue
        if len(parts) != 1 or "=" not in parts[0]:
            raise ValueError("Expected literal KEY=value configuration")
        key, value = parts[0].split("=", 1)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or key in result:
            raise ValueError("Invalid or duplicate configuration key")
        result[key] = value
    return result


def config(smoke=False, seed=3407):
    values = literals(ROOT / "configs/correctness_judge_3seeds.sh")
    if smoke:
        values.update(literals(ROOT / "configs/correctness_judge_smoke.sh"))
    values["SEED"] = str(seed)
    return values


def historical_namespace(values=None, source=None):
    """Extract only judge constants/functions; never import the GPU trainer."""
    values = values or config()
    namespace = {"hashlib": hashlib, "re": re, "json": json, "urllib": urllib,
                 "AI_JUDGE_MODEL": "qwen-32b",
                 "JudgeFailure": JudgeFailure, "record_event": record_event,
                 "request_judge": request_judge, "validate_response": validate_response}
    for key, value in values.items():
        if key.startswith("AI_JUDGE_"):
            if key in {"AI_JUDGE_ENABLED", "AI_JUDGE_MOCK", "AI_JUDGE_REQUIRE_TEST_PASS"}:
                namespace[key] = value == "1"
            elif key in {"AI_JUDGE_MODEL", "AI_JUDGE_BASE_URL", "AI_JUDGE_API_KEY"}:
                namespace[key] = value
            else:
                namespace[key] = float(value) if "." in value else int(value)
    constants = {"AI_JUDGE_PROMPT_VERSION", "AI_JUDGE_SYSTEM_PROMPT",
                 "AI_JUDGE_USER_TEMPLATE", "AI_JUDGE_PROMPT_HASH",
                 "AI_JUDGE_ALLOWED_SUBCATEGORIES", "AI_JUDGE_SEVERITY_WEIGHTS"}
    functions = {"numbered_python_code", "build_ai_judge_user_prompt",
                 "ai_judge_chat_completions_url", "parse_json_object", "call_ollama_ai_judge",
                 "code_lines_for_span", "sanitize_ai_judge_findings", "score_ai_judge_findings",
                 "apply_ai_judge_reward", "add_mock_finding", "mock_ai_judge_response"}
    tree = ast.parse(source if source is not None else (ROOT / "train.py").read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if
             (isinstance(node, ast.FunctionDef) and node.name in functions) or
             (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants
                                                  for t in node.targets))]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "historical_judge", "exec"), namespace)
    return namespace


def prompt_metadata():
    namespace = historical_namespace()
    text = "\n".join(namespace[key] for key in
                     ("AI_JUDGE_PROMPT_VERSION", "AI_JUDGE_SYSTEM_PROMPT", "AI_JUDGE_USER_TEMPLATE"))
    return {"version": namespace["AI_JUDGE_PROMPT_VERSION"],
            "historical_hash": namespace["AI_JUDGE_PROMPT_HASH"],
            "sha256": hashlib.sha256(text.encode()).hexdigest(), "text": text}


def source_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}


def git(*args):
    # Command-scoped LFS bypass supports source-only Windows worktrees too.
    return subprocess.check_output(["git", "-c", "filter.lfs.process=",
                                    "-c", "filter.lfs.smudge=", "-c", "filter.lfs.required=false",
                                    *args], cwd=ROOT, text=True)


def credentials():
    # Only this private literal file and these three environment settings are read.
    values = {}
    private = ROOT / ".env"
    if private.exists():
        if subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=ROOT).returncode:
            raise ValueError("Private .env must be gitignored")
        values = literals(private)
        if set(values) - PRIVATE_KEYS:
            raise ValueError("Use only the three judge settings in private .env")
    values.update({key: os.environ[key] for key in PRIVATE_KEYS if key in os.environ})
    if any(not values.get(key) for key in PRIVATE_KEYS):
        raise ValueError("Missing private judge settings; values are never logged")
    if values["AI_JUDGE_MODEL"] != "qwen-32b":
        raise ValueError("Formal experiment requires API alias qwen-32b")
    if not values["AI_JUDGE_BASE_URL"].startswith(("http://", "https://")):
        raise ValueError("Invalid private endpoint configuration")
    return values


def stage_config(values, root, mode):
    return {**values, "TEST_MODE": mode, "RUN_ROOT": str(root), "RUN_ID": mode,
            "RUN_NAME": root.name, "REPEAT_INDEX": "1", "REPEAT_TOTAL": "1",
            "LOG_DIR": str(root / "logs" / mode), "OUTPUT_DIR": str(root / "output" / mode),
            "LORA_OUTPUT_DIR": str(root / "adapters" / mode),
            "LORA_PATH": str(root / "adapters" / "train"),
            "AI_JUDGE_STATUS_PATH": str(root / "judge-status.jsonl")}


def child_env(settings, private):
    environment = os.environ.copy()
    # Ambient trainer knobs cannot silently override the matched settings.
    for node in ast.walk(ast.parse((ROOT / "train.py").read_text(encoding="utf-8"))):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "getenv" and node.args
                and isinstance(node.args[0], ast.Constant)):
            environment.pop(node.args[0].value, None)
    environment.update(settings)
    environment.update(private)
    environment["PYTHONUNBUFFERED"] = "1"
    environment["CUDA_VISIBLE_DEVICES"] = os.getenv("GPU_DEVICE", "1")
    return environment


def health(root, *, save=True):
    root = Path(root).resolve()
    meta = json.loads((root / "metadata.json").read_text())
    events = [json.loads(line) for line in (root / "judge-status.jsonl").read_text().splitlines()]
    counts = Counter(event["status"] for event in events)
    with (root / "logs/train/samples.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    groups = defaultdict(list)
    for row in rows:
        groups[row["step"]].append(row)
    useful = sum(len({float(row["reward_ai_judge"]) for row in group
                      if row["ai_judge_status"] == "ok"}) > 1 for group in groups.values())
    total_varied = sum(len({float(row["reward_total"]) for row in group}) > 1
                       for group in groups.values())
    state = json.loads((root / "output/train/trainer_state.json").read_text())
    expected = int(meta["configuration"]["MAX_STEPS"])
    checks = {
        "run_completed": meta["status"] == "completed" and bool(meta.get("end")),
        "stage_outcomes_complete": len(meta.get("stage_results", [])) == len(STAGES)
            and [result["stage"] for result in meta["stage_results"]] == STAGES
            and all(result.get("start") and result.get("end") and result.get("exit_code") == 0
                    for result in meta["stage_results"]),
        "judge_requests_succeeded": counts["ok"] > 0 and counts["attempt"] > 0,
        "no_fatal_or_schema_parse_errors": counts["fatal"] == 0 and not any(
            event.get("kind") in {"schema", "parse", "unexpected"} for event in events),
        "no_failure_quality_rewards": all(
            row["ai_judge_status"] == "ok" if row["test_status"] == "passed"
            else float(row["reward_ai_judge"]) == 0 for row in rows)
            and all(not row["ai_judge_error"] for row in rows),
        "valid_logged_findings": all(isinstance(json.loads(row["ai_judge_findings_json"]), list)
                                      for row in rows),
        "historical_instrument_logged": all(
            row["ai_judge_model"] == "qwen-32b"
            and row["ai_judge_prompt_hash"] == meta["prompt"]["historical_hash"]
            and row["ai_judge_prompt_version"] == meta["prompt"]["version"] for row in rows),
        "useful_within_group_judge_variation": useful > 0,
        "total_reward_variation": total_varied > 0,
        "complete_steps_and_groups": state["global_step"] == expected
            and len(groups) == expected and all(len(group) == 4 for group in groups.values())
            and len(rows) == expected * 4,
        "fresh_adapter_saved": (root / "adapters/train/adapter_config.json").is_file()
            and any((root / "adapters/train" / name).is_file()
                    for name in ("adapter_model.safetensors", "adapter_model.bin")),
        "provenance_complete": all((root / name).is_file() for name in
            ("packages.txt", "gpu.txt", "source.diff", "baseline.diff", "git-status.txt", "judge-prompt.txt",
             "judge-summary.json")) and all(
            (root / "source" / name).is_file()
            and hashlib.sha256((root / "source" / name).read_bytes()).hexdigest()
                == meta["source_hashes"][name] for name in FILES),
        "metadata_complete": all(key in meta for key in
            ("start", "git_commit", "git_branch", "dirty", "dataset", "requested_alias",
             "recorded_backend", "prompt")) and meta["requested_alias"] == "qwen-32b"
             and meta["recorded_backend"] == BACKEND,
        "paths_and_resume": all(
            Path(settings["OUTPUT_DIR"]).resolve() == root / "output" / stage
            and Path(settings["LOG_DIR"]).resolve() == root / "logs" / stage
            and Path(settings["LORA_OUTPUT_DIR"]).resolve() == root / "adapters" / stage
            and Path(settings["LORA_PATH"]).resolve() == root / "adapters/train"
            and settings["AUTO_RESUME"] == "0" and settings["RESUME_FROM_CHECKPOINT"] == "none"
            for stage, settings in meta["stages"].items()),
        "mode_directory": root.parent.name == "correctness-judge-" + meta["mode"],
    }
    report = {"pass": all(checks.values()), "checks": checks, "judge_status_counts": dict(counts),
              "judge_varied_groups": useful, "total_varied_groups": total_varied,
              "groups": len(groups), "note": "Smoke is operational evidence, not final model quality."}
    if save:
        write_json(root / "health.json", report)
    return report


def approval_gate(path, mode, seed):
    root = Path(path).resolve()
    meta = json.loads((root / "metadata.json").read_text())
    required_mode = "smoke" if seed == 3407 else "formal"
    required_seed = 3407 if seed == 3407 else seed - 1
    if (meta["mode"] != required_mode or meta["seed"] != required_seed
            or meta["source_hashes"] != source_hashes() or not health(root, save=False)["pass"]):
        raise ValueError("Preceding matched smoke/seed must pass with identical source")
    previous = meta["configuration"].copy()
    current = config(mode == "smoke", seed)
    for key in ("MAX_STEPS", "SEED"):
        previous.pop(key)
        current.pop(key)
    if previous != current:
        raise ValueError("Preceding run configuration differs")


def run(args):
    values = config(args.smoke, args.seed)
    mode = "smoke" if args.smoke else "formal"
    if args.smoke and args.seed != 3407:
        raise ValueError("Initial smoke uses seed 3407")
    root = ROOT / "results" / ("correctness-judge-" + mode) / (
        f"seed-{args.seed}-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ"))
    stages = {stage: stage_config(values, root, stage) for stage in STAGES}
    if args.dry_run:
        print(json.dumps({"mode": mode, "seed": args.seed, "configuration": values,
                          "stages": stages, "prompt": {k: v for k, v in prompt_metadata().items()
                                                       if k != "text"},
                          "requested_alias": "qwen-32b", "recorded_backend": BACKEND}, indent=2))
        return 0
    if not args.smoke:
        if not args.after:
            raise ValueError("Formal run requires --after passing smoke/preceding seed directory")
        approval_gate(args.after, mode, args.seed)
    private = credentials()
    if git("ls-files", ".env").strip():
        raise ValueError("Private .env must never be tracked")
    # flock is Linux-only and released by the OS on exit, including crashes.
    import fcntl
    with (ROOT / ".correctness-judge.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        root.mkdir(parents=True, exist_ok=False)
        print(f"RUN_DIRECTORY={root}", flush=True)
        prompt = prompt_metadata()
        meta = {"mode": mode, "seed": args.seed, "status": "preparing", "start": now(),
                "end": None, "baseline": BASELINE, "git_commit": git("rev-parse", "HEAD").strip(),
                "git_branch": git("branch", "--show-current").strip(), "configuration": values,
                "stages": stages, "source_hashes": source_hashes(),
                "requested_alias": private["AI_JUDGE_MODEL"], "recorded_backend": BACKEND,
                "backend_evidence": "Externally confirmed by user; not resolved by API alias here",
                "prompt": {k: v for k, v in prompt.items() if k != "text"},
                "dataset": {"name": values["DATASET_NAME"], "split": "test",
                            "train": [0, 50], "holdout": [50, 100], "end_exclusive": True},
                "gpu_device": os.getenv("GPU_DEVICE", "1"), "stage_results": []}
        status = git("status", "--porcelain")
        meta["dirty"] = bool(status.strip())
        (root / "git-status.txt").write_text(status, encoding="utf-8")
        (root / "source.diff").write_text(git("diff", "HEAD", "--", *FILES, ".gitignore"), encoding="utf-8")
        (root / "baseline.diff").write_text(git("diff", BASELINE, "--", *FILES, ".gitignore"), encoding="utf-8")
        (root / "judge-prompt.txt").write_text(prompt["text"], encoding="utf-8")
        for name in FILES:
            target = root / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
        write_json(root / "metadata.json", meta)
        (root / "judge-status.jsonl").touch()
        try:
            subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
            (root / "packages.txt").write_text(subprocess.check_output(
                [sys.executable, "-m", "pip", "freeze"], text=True), encoding="utf-8")
            (root / "gpu.txt").write_text(subprocess.check_output(["nvidia-smi"], text=True), encoding="utf-8")
            meta["status"] = "running"
            for stage, settings in stages.items():
                result = {"stage": stage, "start": now()}
                meta["stage_results"].append(result)
                write_json(root / "metadata.json", meta)
                with (root / (stage + ".log")).open("w", encoding="utf-8") as log:
                    completed = subprocess.run([sys.executable, "train.py"], cwd=ROOT,
                                               env=child_env(settings, private), stdout=log,
                                               stderr=subprocess.STDOUT)
                result.update(end=now(), exit_code=completed.returncode)
                if completed.returncode:
                    raise ValueError("Trainer stage failed; inspect private run logs")
            meta["status"] = "completed"
        finally:
            if meta["status"] != "completed":
                meta["status"] = "failed"
            meta["end"] = now()
            write_json(root / "metadata.json", meta)
            events = [json.loads(line) for line in (root / "judge-status.jsonl").read_text().splitlines()]
            write_json(root / "judge-summary.json", {
                "statuses": dict(Counter(event["status"] for event in events)),
                "errors_by_kind": dict(Counter(event.get("kind") for event in events
                                                if event["status"] == "error")),
                "infrastructure_failure_rewards": "Forbidden: failure raises before reward return"})
        report = health(root)
        print(json.dumps(report, indent=2))
        return 0 if report["pass"] else 1


def connectivity(count):
    values = {**config(), **credentials()}
    namespace = historical_namespace(values)
    root = ROOT / "results/judge-connectivity" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    root.mkdir(parents=True, exist_ok=False)
    write_json(root / "metadata.json", {"start": now(), "requested_alias": "qwen-32b",
               "recorded_backend": BACKEND, "prompt": {k: v for k, v in prompt_metadata().items()
                                                        if k != "text"}, "requests": count})
    os.environ["AI_JUDGE_STATUS_PATH"] = str(root / "judge-status.jsonl")
    cases = [("Write add_one(x) returning x + 1.", "def add_one(x):\n    return x + 1"),
             ("Return whether x is positive.", "def positive(x):\n    if x > 0:\n        return True\n    else:\n        return False")]
    results = []
    # Bounded diagnostics: one HTTP attempt per probe (2-5 total), no retry batch.
    def single_attempt(request, timeout, parse):
        with urllib.request.urlopen(request, timeout=timeout) as response:
            envelope = json.loads(response.read().decode("utf-8"))
        return validate_response(parse(envelope["choices"][0]["message"]["content"]))
    namespace["request_judge"] = single_attempt
    for index in range(count):
        task, code = cases[index % 2]
        try:
            response = namespace["call_ollama_ai_judge"](task, code, code)
            findings = namespace["sanitize_ai_judge_findings"](response, code)
            results.append({"probe": index + 1, "status": "ok", "schema": "valid",
                            "score": namespace["score_ai_judge_findings"](findings)})
        except Exception as exc:
            results.append({"probe": index + 1, "status": "failed", "error_type": type(exc).__name__})
            write_json(root / "connectivity.json", results)
            raise ValueError("Connectivity probe failed; no training permitted") from None
    write_json(root / "connectivity.json", results)
    print(json.dumps({"directory": str(root), "requests": count, "results": results}, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--dry-run", action="store_true", help="No secrets, network, GPU, or writes")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--seed", type=int, choices=(3407, 3408, 3409), default=3407)
    parser.add_argument("--after", help="Passing smoke/preceding formal run directory")
    action.add_argument("--connectivity", type=int, choices=range(2, 6), metavar="2..5")
    action.add_argument("--health", help="Inspect an existing run without starting training")
    args = parser.parse_args()
    try:
        if args.health:
            report = health(args.health)
            print(json.dumps(report, indent=2))
            return 0 if report["pass"] else 1
        if args.connectivity:
            if args.dry_run:
                parser.error("Connectivity cannot be combined with --dry-run")
            return connectivity(args.connectivity)
        return run(args)
    except Exception as exc:
        # No raw third-party exception text can disclose private endpoint/key.
        print(f"FAILED ({type(exc).__name__}); check configuration or private run artifacts", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
