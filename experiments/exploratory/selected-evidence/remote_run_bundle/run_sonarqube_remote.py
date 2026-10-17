"""Reproduce SonarQube in an isolated local-only Docker container."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from common import (
    REPO_ROOT,
    load_json,
    redact_text,
    resolve_run_dir,
    run_command,
    sha256_file,
    update_stage,
    utc_now,
    venv_executable,
    venv_python,
    write_json,
)


SONAR_IMAGE = "sonarqube@sha256:d4899d380ad9d7b63ebaa751e047f5a4f064f8902cdf7c1a3c3c96f7d71600ed"


def api_request(
    base_url: str,
    path: str,
    *,
    username: str = "admin",
    password: str = '',
    data: dict[str, str] | None = None,
) -> dict[str, Any] | str:
    body = urllib.parse.urlencode(data).encode("utf-8") if data else None
    request = urllib.request.Request(base_url + path, data=body, method="POST" if data else "GET")
    credentials = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    request.add_header("Authorization", f"Basic {credentials}")
    if body is not None:
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(request, timeout=15) as response:
        text = response.read().decode("utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def wait_until_up(base_url: str, timeout_seconds: float = 180.0) -> tuple[str, float]:
    started = time.perf_counter()
    last_status = "unreachable"
    while time.perf_counter() - started < timeout_seconds:
        try:
            response = api_request(base_url, "/api/system/status")
            if isinstance(response, dict):
                last_status = str(response.get("status", "unknown"))
                if last_status == "UP":
                    return str(response.get("version", "unknown")), time.perf_counter() - started
        except Exception:
            pass
        time.sleep(3)
    raise TimeoutError(f"SonarQube did not become ready; last status={last_status}")


def parse_sensor_ms(log_path: Path) -> int | None:
    text = log_path.read_text(encoding="utf-8")
    matches = re.findall(r"Sensor Python Sensor \[python\] \(done\) \| time=(\d+)ms", text)
    return int(matches[-1]) if matches else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--port", type=int, default=19000)
    parser.add_argument("--keep-work", action="store_true")
    args = parser.parse_args()
    run_dir = resolve_run_dir(args.run_directory)
    if not (run_dir / "run_manifest.json").exists():
        raise SystemExit("Initialize the run directory first")
    stage_dir = run_dir / "sonarqube"
    if stage_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing stage: {stage_dir}")
    stage_dir.mkdir()
    logs = stage_dir / "logs"
    work = run_dir / "work" / "sonarqube_workspace"
    fake_repo = work / "UnSloth-RL"
    experiment = fake_repo / "experiments" / "sonarqube_pilot"
    venv = work / "sonarqube_venv"
    base_url = f"http://127.0.0.1:{args.port}"
    container = "softeng700-sonar-" + re.sub(r"[^a-z0-9]", "-", run_dir.name.lower())[:40]
    token_name = f"{container}-token"
    token: str | None = None
    container_started = False
    stage: dict[str, Any] = {
        "state": "running",
        "started_at_utc": utc_now(),
        "docker_image": SONAR_IMAGE,
        "bind": "127.0.0.1:<configured-port>",
        "candidate_code_executed": False,
    }
    update_stage(run_dir, "sonarqube", stage)
    try:
        experiment.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(REPO_ROOT / "experiments" / "sonarqube_pilot", experiment)
        shutil.copytree(
            REPO_ROOT / "experiments" / "codequal_analyzer_pilot",
            fake_repo / "experiments" / "codequal_analyzer_pilot",
        )
        shutil.rmtree(experiment / "results")
        (experiment / "results").mkdir()
        samples_target = fake_repo / "results" / "13" / "samples.csv"
        samples_target.parent.mkdir(parents=True)
        shutil.copy2(REPO_ROOT / "results" / "13" / "samples.csv", samples_target)
        shutil.copy2(REPO_ROOT / "train.py", fake_repo / "train.py")

        pull_started = time.perf_counter()
        run_command(
            ["docker", "pull", SONAR_IMAGE],
            cwd=work,
            log_path=logs / "01_docker_pull.log",
        )
        pull_seconds = time.perf_counter() - pull_started
        run_command(
            [
                "docker", "run", "--rm", "-d", "--name", container,
                "-e", "SONAR_ES_BOOTSTRAP_CHECKS_DISABLE=true",
                "-p", f"127.0.0.1:{args.port}:9000", SONAR_IMAGE,
            ],
            cwd=work,
            log_path=logs / "02_docker_run.log",
        )
        container_started = True
        server_version, startup_seconds = wait_until_up(base_url)
        token_response = api_request(
            base_url,
            "/api/user_tokens/generate",
            data={"name": token_name},
        )
        if not isinstance(token_response, dict) or not token_response.get("token"):
            raise RuntimeError("Could not create temporary SonarQube token")
        token = str(token_response["token"])

        run_command(
            [sys.executable, "-m", "venv", str(venv)],
            cwd=work,
            log_path=logs / "03_venv.log",
        )
        python = venv_python(venv)
        run_command(
            [str(python), "-m", "pip", "install", "--requirement", str(experiment / "requirements-pilot.txt")],
            cwd=work,
            log_path=logs / "04_install.log",
        )
        run_command(
            [str(python), "prepare_dataset.py"],
            cwd=experiment,
            log_path=logs / "05_prepare_dataset.log",
        )
        run_command(
            [str(python), "prepare_extension.py"],
            cwd=experiment,
            log_path=logs / "06_prepare_extension.log",
        )

        scanner = venv_executable(venv, "pysonar")
        scanner_env = os.environ.copy()
        scanner_env["SONAR_TOKEN"] = token
        scanner_env["SONAR_HOST_URL"] = base_url
        scan_records: dict[str, dict[str, Any]] = {}

        def scan(name: str, build_string: str, extension: bool = False) -> None:
            command = [
                str(scanner),
                "--sonar-qualitygate-wait",
                "--sonar-qualitygate-timeout", "300",
                "--sonar-build-string", build_string,
            ]
            if extension:
                command.extend(["--sonar-sources", "dataset,extension"])
            started = time.perf_counter()
            result = run_command(
                command,
                cwd=experiment,
                log_path=logs / f"scan_{name}.log",
                env=scanner_env,
                allowed_exit_codes={0, 1},
            )
            log_text = (logs / f"scan_{name}.log").read_text(encoding="utf-8")
            if (
                "SonarScanner Engine completed successfully" not in log_text
                and "QUALITY GATE STATUS: FAILED" not in log_text
            ):
                raise RuntimeError(f"Sonar scanner did not complete successfully for {name}")
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            scan_records[name] = {
                "exit_code": result["exit_code"],
                "end_to_end_ms": elapsed_ms,
                "python_sensor_ms": parse_sensor_ms(logs / f"scan_{name}.log"),
            }

        scan("frozen_1", "remote-frozen-1")
        write_json(
            experiment / "results" / "raw_issues_scan1.json",
            api_request(base_url, "/api/issues/search?componentKeys=softeng700-sonarqube-pilot&ps=500&p=1&additionalFields=_all"),
        )
        scan("frozen_2", "remote-frozen-2")
        write_json(
            experiment / "results" / "raw_issues_scan2.json",
            api_request(base_url, "/api/issues/search?componentKeys=softeng700-sonarqube-pilot&ps=500&p=1&additionalFields=_all"),
        )

        profiles = api_request(base_url, "/api/qualityprofiles/search?language=py")
        if not isinstance(profiles, dict):
            raise RuntimeError("Invalid quality profile response")
        write_json(experiment / "results" / "python_profiles.json", profiles)
        default_profile = next(item for item in profiles["profiles"] if item.get("isDefault"))
        profile_query = urllib.parse.quote(str(default_profile["key"]), safe="")
        active_rules = api_request(
            base_url,
            f"/api/rules/search?activation=true&qprofile={profile_query}&ps=500",
        )
        write_json(experiment / "results" / "active_python_rules.json", active_rules)

        scan("extension", "remote-extension", extension=True)
        write_json(
            experiment / "results" / "raw_issues_extension.json",
            api_request(base_url, "/api/issues/search?componentKeys=softeng700-sonarqube-pilot&ps=500&p=1&additionalFields=_all"),
        )
        write_json(
            experiment / "results" / "quality_gate_extension.json",
            api_request(base_url, "/api/qualitygates/project_status?projectKey=softeng700-sonarqube-pilot"),
        )
        write_json(
            experiment / "results" / "project_measures_extension.json",
            api_request(base_url, "/api/measures/component?component=softeng700-sonarqube-pilot&metricKeys=ncloc,files,complexity,cognitive_complexity,violations,code_smells,bugs,vulnerabilities,security_hotspots"),
        )
        timings = {
            "one_time_setup": {
                "docker_image_pull_seconds": round(pull_seconds, 3),
                "server_startup_seconds": round(startup_seconds, 3),
                "included_in_scan_latency": False,
            },
            "frozen_scan_1": {"files": 73, **scan_records["frozen_1"]},
            "frozen_scan_2": {"files": 73, **scan_records["frozen_2"]},
            "exploratory_extension": {"files": 90, **scan_records["extension"]},
        }
        write_json(experiment / "results" / "timings.json", timings)
        run_command(
            [str(python), "summarize_results.py"],
            cwd=experiment,
            log_path=logs / "10_summarize.log",
        )
        (experiment / "results" / "active_python_rules.json").unlink(missing_ok=True)
        freeze = run_command(
            [str(python), "-m", "pip", "freeze"],
            cwd=work,
            log_path=logs / "11_pip_freeze.log",
        )
        (stage_dir / "environment_freeze.txt").write_text(freeze["stdout"], encoding="utf-8")
        shutil.copytree(experiment / "results", stage_dir / "results")
        stage.update(
            {
                "state": "complete",
                "finished_at_utc": utc_now(),
                "sonarqube_version": server_version,
                "temporary_token_revoked": False,
                "scan_records": scan_records,
                "source_hashes": {
                    "sonar_project_properties": sha256_file(experiment / "sonar-project.properties"),
                    "rule_mapping": sha256_file(experiment / "rule_mapping.json"),
                    "protocol": sha256_file(experiment / "PROTOCOL.md"),
                    "samples_csv": sha256_file(samples_target),
                    "train_py": sha256_file(fake_repo / "train.py"),
                },
                "result_summary": load_json(stage_dir / "results" / "summary.json"),
            }
        )
        return_code = 0
    except Exception as exc:
        stage.update(
            {
                "state": "failed",
                "finished_at_utc": utc_now(),
                "error_type": type(exc).__name__,
                "error_message": redact_text(exc)[:500],
                "work_preserved": True,
            }
        )
        return_code = 1
    finally:
        if token is not None:
            try:
                api_request(base_url, "/api/user_tokens/revoke", data={"name": token_name})
                stage["temporary_token_revoked"] = True
            except Exception as cleanup_error:
                stage["token_cleanup_error"] = str(cleanup_error)[:300]
        if container_started:
            completed = subprocess.run(
                ["docker", "stop", container], capture_output=True, text=True, check=False
            )
            stage["container_stopped"] = completed.returncode == 0
        write_json(stage_dir / "stage_manifest.json", stage)
        update_stage(run_dir, "sonarqube", stage)
        if stage.get("state") == "complete" and not args.keep_work:
            shutil.rmtree(work)

    print(json.dumps(stage, indent=2))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
