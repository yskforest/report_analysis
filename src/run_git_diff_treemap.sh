#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")"; pwd)
PROJECT_DIR=$(cd "${SCRIPT_DIR}/.."; pwd)

PYTHON_BIN="python3"

# Extract positional arguments
BASE_REF="${1:-}"
OUTPUT_DIR="${2:-}"

if [ -z "${BASE_REF}" ] || [ -z "${OUTPUT_DIR}" ]; then
  echo "Usage: $0 <base_ref> <output_dir> [options]" >&2
  exit 1
fi

# Initialize lists of arguments
EXTRACTOR_ARGS=()
TREEMAP_DEPTH="8"
NO_PROGRESS=""

CLOC_CSV=""
UND_CSV=""
GIT_DIR="."
STRIP_PREFIXES=()

# Parse options
shift 2
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cloc-csv)
      CLOC_CSV="$2"
      shift 2
      ;;
    --cloc-csv=*)
      CLOC_CSV="${1#*=}"
      shift 1
      ;;
    --und-csv)
      UND_CSV="$2"
      shift 2
      ;;
    --und-csv=*)
      UND_CSV="${1#*=}"
      shift 1
      ;;
    --git-dir)
      GIT_DIR="$2"
      EXTRACTOR_ARGS+=("$1" "$2")
      shift 2
      ;;
    --git-dir=*)
      GIT_DIR="${1#*=}"
      EXTRACTOR_ARGS+=("$1")
      shift 1
      ;;
    --treemap-max-depth)
      TREEMAP_DEPTH="$2"
      shift 2
      ;;
    --treemap-max-depth=*)
      TREEMAP_DEPTH="${1#*=}"
      shift 1
      ;;
    --no-progress)
      NO_PROGRESS="--no-progress"
      EXTRACTOR_ARGS+=("$1")
      shift 1
      ;;
    *)
      EXTRACTOR_ARGS+=("$1")
      shift 1
      ;;
  esac
done

# Resolve absolute path prefixes to strip automatically for safety
STRIP_PREFIXES+=("/home/korver/code/hc_new_arch")
STRIP_PREFIXES+=("${PROJECT_DIR}")

if [ -d "${GIT_DIR}" ]; then
  REPO_FULL_PATH=$(cd "${GIT_DIR}"; pwd)
  REPO_NAME=$(basename "${REPO_FULL_PATH}")
  STRIP_PREFIXES+=("${REPO_FULL_PATH}")
  STRIP_PREFIXES+=("${REPO_NAME}")
fi

# Step 1: Run Git Diff Extractor
echo "[INFO] Running Git diff metrics extraction..."
"${PYTHON_BIN}" "${SCRIPT_DIR}/git_diff_extractor.py" "${BASE_REF}" "${OUTPUT_DIR}" "${EXTRACTOR_ARGS[@]}"

# Step 2: Merge Metrics CSVs
echo "[INFO] Merging CSV reports..."
MERGE_INPUTS=("${OUTPUT_DIR}/git_diff_file_metrics.csv")
MERGE_PREFIXES=("git")

if [ -n "${CLOC_CSV}" ]; then
  MERGE_INPUTS+=("${CLOC_CSV}")
  MERGE_PREFIXES+=("cloc")
fi

if [ -n "${UND_CSV}" ]; then
  MERGE_INPUTS+=("${UND_CSV}")
  MERGE_PREFIXES+=("und")
fi

# Build strip prefix arguments
STRIP_OPTS=()
for prefix in "${STRIP_PREFIXES[@]}"; do
  STRIP_OPTS+=("--strip-prefix" "${prefix}")
done

# Run merge_metrics.py (Note: we leave the base CSV un-prefixed by leaving prefixes[0] empty in Python if we want,
# but passing "git cloc und" to prefixes: we will implement the Python merge_metrics.py to keep the original column names
# for the 1st input by default, or if we pass 'git' it will prepend 'git_'. Let's not pass the first prefix 'git' if we want
# to keep columns unprefixed. In merge_metrics.py, we can pass --prefixes cloc und and omit git, or pass "" as first prefix.
# Let's pass "" for the baseline prefix to keep original column names!)
"${PYTHON_BIN}" "${SCRIPT_DIR}/merge_metrics.py" "${OUTPUT_DIR}/merged_metrics.csv" \
  --inputs "${MERGE_INPUTS[@]}" \
  --prefixes "" "cloc" "und" \
  "${STRIP_OPTS[@]}"

# Step 3: Generate Plotly HTML Treemaps from merged metrics CSV
echo "[INFO] Generating treemaps from merged CSV..."
GEN_ARGS=("${OUTPUT_DIR}/merged_metrics.csv" "${OUTPUT_DIR}" "--treemap-max-depth" "${TREEMAP_DEPTH}")
if [ -n "${NO_PROGRESS}" ]; then
  GEN_ARGS+=("--no-progress")
fi

"${PYTHON_BIN}" "${SCRIPT_DIR}/generate_treemaps.py" "${GEN_ARGS[@]}"
