#!/usr/bin/env bash
set -euo pipefail

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=================================================="
echo " Starting Requirements Verification (test_run.sh) "
echo "=================================================="

# 1. Activate venv to use venv's Python
if [ -d "venv" ]; then
  echo "[INFO] Activating virtual environment (venv)..."
  source venv/bin/activate
else
  echo "[ERROR] venv directory not found! Please create it or install requirements." >&2
  exit 1
fi

# Print Python version being used
echo "[INFO] Using python: $(which python3) ($(python3 --version))"

# Prepare clean output directories
REPORT_OUT="out/report_test"
TREEMAP_OUT="out/treemap_test"
rm -rf "${REPORT_OUT}" "${TREEMAP_OUT}"

# --------------------------------------------------
# Test 1: report_analysis.py
# --------------------------------------------------
echo "--------------------------------------------------"
echo " Test 1: Running report_analysis.py..."
echo "--------------------------------------------------"

python3 src/report_analysis.py \
  sample_data/und_metrics.csv \
  sample_data/cloc/cloc.csv \
  "sample_data/pmd/*.xml" \
  "${REPORT_OUT}" \
  "/"

# Verification list for Test 1
REQUIRED_REPORT_FILES=(
  "summary_report.csv"
  "und_summary.csv"
  "summary_cloc.csv"
  "pmd_summary.csv"
  "und_pmd_merge.csv"
  "file_metrics_hierarchy.xlsx"
  "func_metrics.xlsx"
  "und/und_metrics.csv"
  "und/und_file.csv"
  "und/und_func.csv"
  "und/und_class.csv"
  "und/CountLineCode(Area)-Essential(FileAverage)_treemap.html"
  "und/CountLineCode(Area)-Cyclomatic(FileAverage)_treemap.html"
  "cloc/cloc_filtered.csv"
  "cloc/cloc_pie_chart.html"
  "pmd/pmd_clone_ratio.csv"
  "pmd/pmd_clone_ratio_summary.csv"
)

echo "[INFO] Verifying generated report files..."
MISSING_REPORT=0
for f in "${REQUIRED_REPORT_FILES[@]}"; do
  file_path="${REPORT_OUT}/${f}"
  if [ -f "${file_path}" ] && [ -s "${file_path}" ]; then
    echo -e "  [${GREEN}OK${NC}] Generated and non-empty: ${f}"
  else
    echo -e "  [${RED}FAILED${NC}] Missing or empty: ${f}" >&2
    MISSING_REPORT=$((MISSING_REPORT + 1))
  fi
done

# --------------------------------------------------
# Test 2: run_git_diff_treemap.sh
# --------------------------------------------------
echo "--------------------------------------------------"
echo " Test 2: Running run_git_diff_treemap.sh..."
echo "--------------------------------------------------"

bash src/run_git_diff_treemap.sh \
  HEAD~1 \
  "${TREEMAP_OUT}" \
  --git-dir analysis_code/Open3D \
  --cloc-csv sample_data/cloc/cloc.csv \
  --und-csv sample_data/und_metrics.csv \
  --algo add \
  --extensions "cpp,c,cs,h,hpp"

# Verification list for Test 2
REQUIRED_TREEMAP_FILES=(
  "index.html"
  "code_total_lines_treemap.html"
  "changed_lines_count_treemap.html"
  "changed_lines_treemap.html"
  "git_diff_file_metrics.csv"
  "git_diff_summary.csv"
  "merged_metrics.csv"
)

echo "[INFO] Verifying generated treemap files..."
MISSING_TREEMAP=0
for f in "${REQUIRED_TREEMAP_FILES[@]}"; do
  file_path="${TREEMAP_OUT}/${f}"
  if [ -f "${file_path}" ] && [ -s "${file_path}" ]; then
    echo -e "  [${GREEN}OK${NC}] Generated and non-empty: ${f}"
  else
    echo -e "  [${RED}FAILED${NC}] Missing or empty: ${f}" >&2
    MISSING_TREEMAP=$((MISSING_TREEMAP + 1))
  fi
done

# --------------------------------------------------
# Summary of results
# --------------------------------------------------
echo "=================================================="
TOTAL_MISSING=$((MISSING_REPORT + MISSING_TREEMAP))
if [ "${TOTAL_MISSING}" -eq 0 ]; then
  echo -e "${GREEN}SUCCESS: All verification tests passed!${NC}"
  echo "=================================================="
  exit 0
else
  echo -e "${RED}FAILURE: ${TOTAL_MISSING} required files were missing or empty!${NC}" >&2
  echo "=================================================="
  exit 1
fi
