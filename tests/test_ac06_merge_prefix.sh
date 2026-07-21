#!/usr/bin/env bash
# AC-06: metrics_merge.csv が File 列で結合され、プレフィックスが付与されている
# 対応要求: FR-MERGE-01

source "$(dirname "$0")/test_helpers.sh"
activate_venv

begin_test "AC-06" "metrics_merge.csv のプレフィックス検証"

OUT=$(setup_output_dir "ac06")

# 全入力を指定
python3 "${PROJECT_DIR}/src/report_analysis.py" \
  "${PROJECT_DIR}/sample_data/und_metrics.csv" \
  "${PROJECT_DIR}/sample_data/cloc/cloc.csv" \
  "${PROJECT_DIR}/sample_data/pmd/*.xml" \
  "${PROJECT_DIR}/sample_data/git_numstat.tsv" \
  none \
  "${OUT}" "/"

MERGE_CSV="${OUT}/metrics_merge.csv"

# ファイル存在確認
assert_file_exists "${MERGE_CSV}" "metrics_merge.csv"

# File 列が存在する
assert_csv_has_column "${MERGE_CSV}" "File" "File 列が存在する"

# 各ツールのプレフィックス付き列が存在する
assert_csv_has_column "${MERGE_CSV}" "und_" "und_ プレフィックス付き列が存在する"
assert_csv_has_column "${MERGE_CSV}" "cloc_" "cloc_ プレフィックス付き列が存在する"
assert_csv_has_column "${MERGE_CSV}" "pmd_" "pmd_ プレフィックス付き列が存在する"
assert_csv_has_column "${MERGE_CSV}" "git_" "git_ プレフィックス付き列が存在する"

cleanup_output_dir "ac06"
print_summary
