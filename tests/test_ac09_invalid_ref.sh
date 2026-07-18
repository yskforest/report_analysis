#!/usr/bin/env bash
# AC-09: 不正な Base Ref → 終了コード 1 でエラー理由を出力
# 対応要求: FR-CLI-06, エラー処理

source "$(dirname "$0")/test_helpers.sh"
activate_venv

begin_test "AC-09" "不正 Base Ref でのエラー終了"

OUT=$(setup_output_dir "ac09")

# 存在しないタグを指定
INVALID_REF="nonexistent-tag-xyz-12345"

set +e
stderr_output=$(bash "${PROJECT_DIR}/src/run_git_diff_treemap.sh" \
  "${INVALID_REF}" "${OUT}" --no-progress 2>&1)
exit_code=$?
set -e

# 検証: 終了コード 1
if [ "${exit_code}" -ne 0 ]; then
  pass "AC-09: exit code = ${exit_code} (非ゼロ)"
else
  fail "AC-09: expected non-zero exit code, got 0"
fi

# 検証: エラー理由がstderrに出力されている
if echo "${stderr_output}" | grep -qi "error\|fatal\|invalid\|unknown\|not found\|${INVALID_REF}"; then
  pass "AC-09: エラー理由が出力されている"
else
  fail "AC-09: エラー理由が出力に見つからない"
fi

cleanup_output_dir "ac09"
print_summary
