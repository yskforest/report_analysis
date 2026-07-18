#!/usr/bin/env bash
# AC-07: run_git_diff_treemap.sh にタグ/コミットを指定して正常終了し、CSV と Treemap HTML が出力される
# 対応要求: FR-CLI-06, FR-GIT-04, FR-VIS-01〜05

source "$(dirname "$0")/test_helpers.sh"
activate_venv

begin_test "AC-07" "Git diff treemap 正常実行"

OUT=$(setup_output_dir "ac07")

# 対象リポジトリの決定: analysis_code/Open3D があればそれを使い、なければ本リポジトリ
GIT_TARGET_DIR="${PROJECT_DIR}/analysis_code/Open3D"
GIT_DIR_OPTS=()

if [ -d "${GIT_TARGET_DIR}/.git" ]; then
  GIT_DIR_OPTS=(--git-dir "${GIT_TARGET_DIR}")
  # Open3D のタグまたは直近コミットを Base Ref にする
  BASE_REF=$(cd "${GIT_TARGET_DIR}" && git rev-parse HEAD~1 2>/dev/null || echo "")
  if [ -z "${BASE_REF}" ]; then
    skip "AC-07: analysis_code/Open3D に十分なコミット履歴がない"
    print_summary
    exit $?
  fi
else
  # 本リポジトリ自体を対象にする（フォールバック）
  BASE_REF=$(cd "${PROJECT_DIR}" && git rev-parse HEAD~1 2>/dev/null || echo "")
  if [ -z "${BASE_REF}" ]; then
    skip "AC-07: 本リポジトリに十分なコミット履歴がない"
    print_summary
    exit $?
  fi
fi

# 実行
bash "${PROJECT_DIR}/src/run_git_diff_treemap.sh" \
  "${BASE_REF}" "${OUT}" "${GIT_DIR_OPTS[@]}" --no-progress

# 検証: CSV ファイル
assert_file_exists "${OUT}/git_diff_file_metrics.csv" "git_diff_file_metrics.csv"
assert_file_exists "${OUT}/git_diff_summary.csv" "git_diff_summary.csv"

# 検証: Treemap HTML ファイル
assert_file_exists "${OUT}/code_total_lines_treemap.html" "code_total_lines_treemap.html"
assert_file_exists "${OUT}/changed_lines_count_treemap.html" "changed_lines_count_treemap.html"
assert_file_exists "${OUT}/changed_lines_treemap.html" "changed_lines_treemap.html"
assert_file_exists "${OUT}/index.html" "index.html"

cleanup_output_dir "ac07"
print_summary
