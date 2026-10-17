"""Read-only remote-machine preflight for the prepared experiments."""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import urllib.request

from common import REPO_ROOT, git_commit


def command_check(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        command, cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "summary": (completed.stdout or completed.stderr).strip().splitlines()[:2],
    }


def judge_check() -> dict[str, object]:
    base_url = os.getenv("AI_JUDGE_BASE_URL", "").strip().rstrip("/")
    api_key = os.getenv("AI_JUDGE_API_KEY", "ollama")
    model = os.getenv("AI_JUDGE_MODEL", "qwen3-coder:30b")
    if not base_url:
        return {"ok": False, "error": "AI_JUDGE_BASE_URL is not configured"}
    models_url = base_url + ("/models" if base_url.endswith("/v1") else "/v1/models")
    request = urllib.request.Request(models_url)
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        identifiers = {
            str(item.get("id", item.get("name", ""))) for item in payload.get("data", [])
        }
        return {
            "ok": response.status == 200,
            "endpoint": "<configured>",
            "requested_model": model,
            "model_list_returned": bool(identifiers),
            "exact_model_list_match": model in identifiers if identifiers else None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "endpoint": "<configured>",
            "error_type": type(exc).__name__,
            "error": str(exc).replace(base_url, "<configured>")[:300],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tools",
        nargs="+",
        choices=["ai-judge", "codequal", "sonarqube"],
        default=["ai-judge", "codequal", "sonarqube"],
    )
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    result: dict[str, object] = {
        "repository_commit": git_commit(),
        "working_tree_clean": not status,
        "dirty_path_count": len(status),
        "python": sys.version,
        "tools": {},
        "secrets_printed": False,
    }
    tool_results: dict[str, object] = result["tools"]  # type: ignore[assignment]
    tool_results["git"] = {"ok": shutil.which("git") is not None}
    if "codequal" in args.tools:
        tool_results["codequal"] = {
            "python_venv_available": command_check([sys.executable, "-m", "venv", "--help"])["ok"],
            "git_available": shutil.which("git") is not None,
        }
    if "sonarqube" in args.tools:
        tool_results["sonarqube"] = {
            "docker_available": shutil.which("docker") is not None,
            "docker_engine": command_check(["docker", "info", "--format", "{{.ServerVersion}}"])
            if shutil.which("docker")
            else {"ok": False},
        }
    if "ai-judge" in args.tools:
        tool_results["ai_judge"] = judge_check()

    checks = []
    if not args.allow_dirty:
        checks.append(not status)
    if "codequal" in args.tools:
        codequal = tool_results["codequal"]  # type: ignore[assignment]
        checks.extend([codequal["python_venv_available"], codequal["git_available"]])
    if "sonarqube" in args.tools:
        sonar = tool_results["sonarqube"]  # type: ignore[assignment]
        checks.extend([sonar["docker_available"], sonar["docker_engine"]["ok"]])
    if "ai-judge" in args.tools:
        checks.append(tool_results["ai_judge"]["ok"])  # type: ignore[index]
    result["ready"] = all(checks)
    print(json.dumps(result, indent=2))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
