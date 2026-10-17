#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
exec "${PYTHON_BIN:-python}" scripts/formal_judge_run.py "$@"
