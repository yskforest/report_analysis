#!/usr/bin/env bash
# AC-03: 複数 PMD XML → 統合された clone ratio CSV が生成される
# 対応要求: FR-PMD-01〜03

source "$(dirname "$0")/test_helpers.sh"
activate_venv

begin_test "AC-03" "PMD 複数 XML 統合解析"

OUT=$(setup_output_dir "ac03")
python3 "${PROJECT_DIR}/src/report_analysis.py" \
  none none \
  "${PROJECT_DIR}/sample_data/pmd/*.xml" \
  none none "${OUT}" "/"

# 検証: ファイル存在
assert_file_exists "${OUT}/pmd/pmd_clone_ratio.csv" "pmd_clone_ratio.csv"
assert_file_exists "${OUT}/summary.csv" "summary.csv"
assert_csv_has_column "${OUT}/summary.csv" "pmd_TotalFileTokens"

# 検証: 行数が1以上（複数XMLの統合結果が反映されている）
assert_csv_min_rows "${OUT}/pmd/pmd_clone_ratio.csv" 1 \
  "AC-03: pmd_clone_ratio.csv にデータ行が存在する"

cleanup_output_dir "ac03"
print_summary
