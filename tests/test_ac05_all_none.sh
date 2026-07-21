#!/usr/bin/env bash
# AC-05: 全入力が未存在 → 終了コード 1 を返す
# 対応要求: FR-PART-03, FR-CLI-05

source "$(dirname "$0")/test_helpers.sh"
activate_venv

begin_test "AC-05" "全入力なしでの異常終了"

OUT=$(setup_output_dir "ac05")

# 全引数に none を指定
assert_exit_code 1 "AC-05: 全 none で exit 1" \
  python3 "${PROJECT_DIR}/src/report_analysis.py" \
  none none none none none "${OUT}" "/"

# stderr にエラーメッセージが出力されること
set +e
stderr_output=$(python3 "${PROJECT_DIR}/src/report_analysis.py" \
  none none none none none "${OUT}" "/" 2>&1 1>/dev/null)
set -e

if echo "${stderr_output}" | grep -qi "error\|no valid"; then
  pass "AC-05: stderr にエラーメッセージが出力されている"
else
  fail "AC-05: stderr にエラーメッセージが見つからない"
fi

cleanup_output_dir "ac05"
print_summary
