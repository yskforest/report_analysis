#!/usr/bin/env bash
# AC-01: Windows 形式パス（\）の UND CSV → 出力パスが / 区切りに統一される
# 対応要求: FR-UND-02

source "$(dirname "$0")/test_helpers.sh"
activate_venv

begin_test "AC-01" "UND CSV パス正規化（Windows形式 → Linux形式）"

# フィクスチャ生成
fixture_csv=$(generate_und_win_fixture)
if [ $? -ne 0 ] || [ ! -f "${fixture_csv}" ]; then
  skip "UND CSV fixture generation failed"
  print_summary
  exit $?
fi

# 実行
OUT=$(setup_output_dir "ac01")
python3 "${PROJECT_DIR}/src/report_analysis.py" \
  "${fixture_csv}" none none none "${OUT}" "/"

# 検証: und_metrics.csv が存在する
assert_file_exists "${OUT}/und/und_metrics.csv"

# 検証: File 列にバックスラッシュが含まれない
assert_csv_no_backslash "${OUT}/und/und_metrics.csv" "File" \
  "AC-01: und_metrics.csv の File 列にバックスラッシュがない"

# und_file.csv も検証
if [ -f "${OUT}/und/und_file.csv" ]; then
  assert_csv_no_backslash "${OUT}/und/und_file.csv" "File" \
    "AC-01: und_file.csv の File 列にバックスラッシュがない"
fi

cleanup_output_dir "ac01"
print_summary
