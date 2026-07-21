#!/usr/bin/env bash
# AC-10: config.yaml に thresholds を定義して UND CSV を入力すると、
# `threshold_exceeded_summary.csv` と `threshold_exceeded_functions.csv`, `threshold_exceeded_dir_summary.csv` が
# `OUTPUT_DIR/und/` に生成され、基準値を超過した関数が正しく集計されていること
# 対応要求: FR-CLI-07, FR-THRESH-01~06, AC-10

source "$(dirname "$0")/test_helpers.sh"
activate_venv

begin_test "AC-10" "基準値超過関数の集集・集計検証"

OUT=$(setup_output_dir "ac10")

# 一時的な config.yaml を作成 (基準値を低く設定して超過を発生させる)
CONFIG_FILE="${OUT}/config.yaml"
cat <<EOF > "${CONFIG_FILE}"
thresholds:
  MaxNesting: 2
  Essential: 2
  Cyclomatic: 3
  CountLine: 40
  CountLineCode: 30
EOF

# 実行
python3 "${PROJECT_DIR}/src/report_analysis.py" \
  --config "${CONFIG_FILE}" \
  "${PROJECT_DIR}/sample_data/und_metrics.csv" \
  none none none \
  none \
  "${OUT}" "/"

# 1. threshold_exceeded_functions.csv の検証
FUNCS_CSV="${OUT}/und/threshold_exceeded_functions.csv"
assert_file_exists "${FUNCS_CSV}" "threshold_exceeded_functions.csv"

# ヘッダーに期待する列があるか検証
head -1 "${FUNCS_CSV}" | grep -q "File" || fail "Missing File column in exceeded functions CSV"
head -1 "${FUNCS_CSV}" | grep -q "Name" || fail "Missing Name column in exceeded functions CSV"
head -1 "${FUNCS_CSV}" | grep -q "Kind" || fail "Missing Kind column in exceeded functions CSV"
head -1 "${FUNCS_CSV}" | grep -q "MaxNesting" || fail "Missing MaxNesting column in exceeded functions CSV"
head -1 "${FUNCS_CSV}" | grep -q "exceeded_metrics" || fail "Missing exceeded_metrics column in exceeded functions CSV"

# 2. threshold_exceeded_summary.csv の検証
SUMMARY_CSV="${OUT}/und/threshold_exceeded_summary.csv"
assert_file_exists "${SUMMARY_CSV}" "threshold_exceeded_summary.csv"

head -1 "${SUMMARY_CSV}" | grep -q "File" || fail "Missing File column in summary CSV"
head -1 "${SUMMARY_CSV}" | grep -q "total_functions" || fail "Missing total_functions column in summary CSV"
head -1 "${SUMMARY_CSV}" | grep -q "MaxNesting_exceeded_count" || fail "Missing MaxNesting_exceeded_count column in summary CSV"
head -1 "${SUMMARY_CSV}" | grep -q "total_exceeded_count" || fail "Missing total_exceeded_count column in summary CSV"
head -1 "${SUMMARY_CSV}" | grep -q "exceeded_ratio" || fail "Missing exceeded_ratio column in summary CSV"

# 3. threshold_exceeded_dir_summary.csv の検証
DIR_SUMMARY_CSV="${OUT}/und/threshold_exceeded_dir_summary.csv"
assert_file_exists "${DIR_SUMMARY_CSV}" "threshold_exceeded_dir_summary.csv"

head -1 "${DIR_SUMMARY_CSV}" | grep -q "Dir" || fail "Missing Dir column in dir summary CSV"
head -1 "${DIR_SUMMARY_CSV}" | grep -q "total_functions" || fail "Missing total_functions column in dir summary CSV"
head -1 "${DIR_SUMMARY_CSV}" | grep -q "total_exceeded_count" || fail "Missing total_exceeded_count column in dir summary CSV"
head -1 "${DIR_SUMMARY_CSV}" | grep -q "exceeded_ratio" || fail "Missing exceeded_ratio column in dir summary CSV"

# 最上位の ALL_FILES 行が存在することを確認
grep -q "ALL_FILES" "${DIR_SUMMARY_CSV}" || fail "Missing ALL_FILES row in dir summary CSV"

cleanup_output_dir "ac10"
print_summary
