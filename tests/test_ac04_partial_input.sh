#!/usr/bin/env bash
# AC-04: 一部入力が未存在でも存在する入力のみで終了コード 0 で完了する
# 対応要求: FR-PART-01, FR-PART-02

source "$(dirname "$0")/test_helpers.sh"
activate_venv

begin_test "AC-04" "部分入力（UND のみ）での正常終了"

OUT=$(setup_output_dir "ac04")

# UND のみ指定（CLOC/PMD/Git は none）
assert_exit_code 0 "AC-04: UND のみで exit 0" \
  python3 "${PROJECT_DIR}/src/report_analysis.py" \
  "${PROJECT_DIR}/sample_data/und_metrics.csv" \
  none none none "${OUT}" "/"

# UND 成果物が存在する
assert_file_exists "${OUT}/und/und_metrics.csv" "und_metrics.csv"

# CLOC / PMD / Git のディレクトリは空または未作成
assert_dir_empty_or_missing "${OUT}/cloc" "cloc/"
assert_dir_empty_or_missing "${OUT}/pmd" "pmd/"
assert_dir_empty_or_missing "${OUT}/git" "git/"

cleanup_output_dir "ac04"
print_summary
