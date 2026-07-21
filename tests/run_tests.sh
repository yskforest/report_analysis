#!/usr/bin/env bash
# tests/run_tests.sh — テストランナー
# 使い方:
#   bash tests/run_tests.sh              # 全テスト実行
#   bash tests/run_tests.sh ac01 ac05    # 個別テスト指定
#   bash tests/run_tests.sh --list       # テスト一覧表示

set -uo pipefail

TESTS_DIR="$(cd "$(dirname "$0")"; pwd)"

# ── 色定義 ──
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── 全テスト一覧（順序付き） ──
ALL_TESTS=(
  "ac01:test_ac01_und_path_normalization.sh:UND パス正規化"
  "ac02:test_ac02_cloc_output.sh:CLOC 出力生成"
  "ac03:test_ac03_pmd_integration.sh:PMD 複数XML統合"
  "ac04:test_ac04_partial_input.sh:部分入力での正常終了"
  "ac05:test_ac05_all_none.sh:全入力なしでの異常終了"
  "ac06:test_ac06_merge_prefix.sh:metrics_merge プレフィックス"
  "ac07:test_ac07_config_visualization.sh:カスタム可視化生成"
  "ac08:test_ac08_config_exclusion.sh:指定外の可視化除外"
  "ac09:test_ac09_config_invalid.sh:設定異常系エラーハンドリング"
  "ac10:test_ac10_thresholds.sh:基準値超過関数の集計検証"
  "ac11:test_ac11_file_excel.sh:ファイル階層 Excel レポート検証"
  "ac12:test_ac12_func_excel.sh:関数メトリクス Excel レポート検証"
  "ac13:test_ac13_file_metrics.sh:ファイルメトリクス収集・連携検証"
)

# ── ヘルプ / リスト表示 ──
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
  echo "Usage: bash tests/run_tests.sh [ac01 ac02 ...] [--list]"
  echo ""
  echo "Options:"
  echo "  --list    テスト一覧を表示"
  echo "  --help    このヘルプを表示"
  echo ""
  echo "引数なしで全テスト実行。テストIDを指定すると個別実行。"
  exit 0
fi

if [[ "${1:-}" == "--list" ]]; then
  echo "Available tests:"
  for entry in "${ALL_TESTS[@]}"; do
    IFS=':' read -r id file desc <<< "${entry}"
    printf "  %-6s  %-45s  %s\n" "${id}" "${file}" "${desc}"
  done
  exit 0
fi

# ── 実行対象の決定 ──
SELECTED_IDS=()
if [ $# -gt 0 ]; then
  SELECTED_IDS=("$@")
fi

# ── メイン実行 ──
echo ""
echo "======================================================"
echo -e " ${BOLD}Requirements Verification Test Runner${NC}"
echo "======================================================"
echo ""

TOTAL_PASS=0
TOTAL_FAIL=0
TOTAL_SKIP=0
TOTAL_RUN=0
RESULTS=()

for entry in "${ALL_TESTS[@]}"; do
  IFS=':' read -r id file desc <<< "${entry}"

  # フィルタリング: 指定がある場合は一致するもののみ実行
  if [ ${#SELECTED_IDS[@]} -gt 0 ]; then
    match=false
    for sel in "${SELECTED_IDS[@]}"; do
      if [[ "${id}" == "${sel}" ]]; then
        match=true
        break
      fi
    done
    if [ "${match}" == "false" ]; then
      continue
    fi
  fi

  TOTAL_RUN=$((TOTAL_RUN + 1))
  script_path="${TESTS_DIR}/${file}"

  if [ ! -f "${script_path}" ]; then
    echo -e "${RED}[ERROR]${NC} Test script not found: ${file}"
    TOTAL_FAIL=$((TOTAL_FAIL + 1))
    RESULTS+=("${RED}FAIL${NC}  ${id}  ${desc}")
    continue
  fi

  # 各テストをサブシェルで実行（テスト間の状態汚染を防止）
  set +e
  output=$(bash "${script_path}" 2>&1)
  test_exit=$?
  set -e

  # テスト出力を表示
  echo "${output}"

  # 結果を集計
  local_pass=$(echo "${output}" | grep -c '\[PASS\]' || true)
  local_fail=$(echo "${output}" | grep -c '\[FAIL\]' || true)
  local_skip=$(echo "${output}" | grep -c '\[SKIP\]' || true)

  TOTAL_PASS=$((TOTAL_PASS + local_pass))
  TOTAL_FAIL=$((TOTAL_FAIL + local_fail))
  TOTAL_SKIP=$((TOTAL_SKIP + local_skip))

  if [ "${local_fail}" -gt 0 ] || [ "${test_exit}" -ne 0 ]; then
    RESULTS+=("${RED}FAIL${NC}  ${id}  ${desc}")
  elif [ "${local_skip}" -gt 0 ] && [ "${local_pass}" -eq 0 ]; then
    RESULTS+=("${YELLOW}SKIP${NC}  ${id}  ${desc}")
  else
    RESULTS+=("${GREEN}PASS${NC}  ${id}  ${desc}")
  fi
done

# ── サマリ ──
echo ""
echo "======================================================"
echo -e " ${BOLD}Test Summary${NC}"
echo "======================================================"
echo ""

for result in "${RESULTS[@]}"; do
  echo -e "  ${result}"
done

echo ""
TOTAL=$((TOTAL_PASS + TOTAL_FAIL + TOTAL_SKIP))
echo -e " Assertions: ${GREEN}${TOTAL_PASS} passed${NC}, ${RED}${TOTAL_FAIL} failed${NC}, ${YELLOW}${TOTAL_SKIP} skipped${NC} / ${TOTAL} total"
echo -e " Test files: ${TOTAL_RUN} executed"
echo "======================================================"

if [ "${TOTAL_FAIL}" -gt 0 ]; then
  echo -e "${RED}${BOLD}RESULT: FAILED${NC}"
  exit 1
else
  echo -e "${GREEN}${BOLD}RESULT: PASSED${NC}"
  exit 0
fi
