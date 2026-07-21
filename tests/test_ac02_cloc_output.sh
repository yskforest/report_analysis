#!/usr/bin/env bash
# AC-02: CLOC CSV → OUTPUT_DIR/cloc/ に pie chart HTML と CSV が生成される
# 対応要求: FR-CLOC-01〜04

source "$(dirname "$0")/test_helpers.sh"
activate_venv

begin_test "AC-02" "CLOC 出力ファイル生成"

OUT=$(setup_output_dir "ac02")
python3 "${PROJECT_DIR}/src/report_analysis.py" \
  none \
  "${PROJECT_DIR}/sample_data/cloc/cloc.csv" \
  none none none "${OUT}" "/"

# 検証
assert_file_exists "${OUT}/cloc/cloc_filtered.csv" "cloc_filtered.csv"
assert_file_exists "${OUT}/summary.csv" "summary.csv"
assert_csv_has_column "${OUT}/summary.csv" "cloc_CountLineCode"

cleanup_output_dir "ac02"
print_summary
