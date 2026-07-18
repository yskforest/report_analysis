#!/usr/bin/env bash
# AC-08: --worktree 指定時に作業ツリーを比較先として差分を集計する
# 対応要求: FR-CLI-08

source "$(dirname "$0")/test_helpers.sh"
activate_venv

begin_test "AC-08" "--worktree 指定時の作業ツリー差分検出"

OUT=$(setup_output_dir "ac08")

# Base Ref: 直近のコミット
BASE_REF=$(cd "${PROJECT_DIR}" && git rev-parse HEAD 2>/dev/null || echo "")
if [ -z "${BASE_REF}" ]; then
  skip "AC-08: 本リポジトリにコミット履歴がない"
  print_summary
  exit $?
fi

# 追跡済みの .py ファイルに一時コメントを追加（.md はデフォルト拡張子フィルタで除外されるため .py を使う）
TARGET_FILE="${PROJECT_DIR}/src/io_models.py"
MARKER="# AC-08 WORKTREE TEST MARKER $(date +%s)"

# 元の内容を保存
cp "${TARGET_FILE}" "${TARGET_FILE}.bak"

# 末尾に一時コメントを追加
echo "${MARKER}" >> "${TARGET_FILE}"

# --worktree 付きで実行
set +e
bash "${PROJECT_DIR}/src/run_git_diff_treemap.sh" \
  "${BASE_REF}" "${OUT}" --worktree --no-progress 2>/dev/null
exit_code=$?
set -e

# ファイルを元に戻す
mv "${TARGET_FILE}.bak" "${TARGET_FILE}"

if [ "${exit_code}" -ne 0 ]; then
  fail "AC-08: run_git_diff_treemap.sh --worktree が異常終了 (exit ${exit_code})"
  print_summary
  exit $?
fi

# 検証: CSV が存在する
assert_file_exists "${OUT}/git_diff_file_metrics.csv" "git_diff_file_metrics.csv"

# 検証: io_models.py の変更が差分結果に含まれている
if grep -q "io_models.py" "${OUT}/git_diff_file_metrics.csv" 2>/dev/null; then
  pass "AC-08: unstaged 変更（io_models.py）が結果に反映されている"
else
  fail "AC-08: unstaged 変更が git_diff_file_metrics.csv に見つからない"
fi

cleanup_output_dir "ac08"
print_summary
