#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 5 ]; then
  echo "usage: $0 {UND_CSV|none} {CLOC_CSV|none} {PMD_XML_GLOB_OR_LIST|none} {OUTPUT_DIR} {REMOVE_PATH_PREFIX}" >&2
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "$0")"; pwd)
python3 "${SCRIPT_DIR}/report_analysis.py" "$1" "$2" "$3" "$4" "$5"
