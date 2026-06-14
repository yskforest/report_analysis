#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")"; pwd)
PROJECT_DIR=$(cd "${SCRIPT_DIR}/.."; pwd)

PYTHON_BIN=${PYTHON:-}
if [ -z "${PYTHON_BIN}" ]; then
  if [ -x "${PROJECT_DIR}/venv/bin/python" ]; then
    PYTHON_BIN="${PROJECT_DIR}/venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

"${PYTHON_BIN}" "${SCRIPT_DIR}/git_diff_treemap.py" "$@"
