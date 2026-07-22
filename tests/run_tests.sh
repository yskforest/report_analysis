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
  echo "Usage: bash tests/run_tests.sh [ac01 ac02 ...] [-j JOBS] [--list]"
  echo ""
  echo "Options:"
  echo "  -j, --jobs N  並列実行数 (デフォルト: CPU コア数)"
  echo "  --list        テスト一覧を表示"
  echo "  --help        このヘルプを表示"
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

# ── 引数解析 ──
DEFAULT_JOBS=4
if command -v nproc >/dev/null 2>&1; then
  DEFAULT_JOBS=$(nproc)
elif command -v sysctl >/dev/null 2>&1; then
  DEFAULT_JOBS=$(sysctl -n hw.ncpu 2>/dev/null || echo 4)
fi

JOBS="${DEFAULT_JOBS}"
SELECTED_IDS=()

while [ $# -gt 0 ]; do
  case "$1" in
    -j|--jobs)
      JOBS="$2"
      shift 2
      ;;
    -j*)
      JOBS="${1#-j}"
      shift
      ;;
    --jobs=*)
      JOBS="${1#*=}"
      shift
      ;;
    *)
      SELECTED_IDS+=("$1")
      shift
      ;;
  esac
done

# ── 対象テスト抽出 ──
TARGET_TESTS=()
for entry in "${ALL_TESTS[@]}"; do
  IFS=':' read -r id file desc <<< "${entry}"
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
  TARGET_TESTS+=("${entry}")
done

# ── メイン実行 ──
echo ""
echo "======================================================"
echo -e " ${BOLD}Requirements Verification Test Runner (Jobs: ${JOBS})${NC}"
echo "======================================================"
echo ""

TOTAL_PASS=0
TOTAL_FAIL=0
TOTAL_SKIP=0
TOTAL_RUN=${#TARGET_TESTS[@]}
RESULTS=()

TMP_DIR=$(mktemp -d)
trap 'rm -rf "${TMP_DIR}"' EXIT

run_single_test() {
  local idx="$1"
  local entry="$2"
  IFS=':' read -r id file desc <<< "${entry}"
  local script_path="${TESTS_DIR}/${file}"
  local out_file="${TMP_DIR}/test_${idx}.log"
  local status_file="${TMP_DIR}/test_${idx}.status"

  if [ ! -f "${script_path}" ]; then
    echo -e "${RED}[ERROR]${NC} Test script not found: ${file}" > "${out_file}"
    echo "FAIL:0:1:0" > "${status_file}"
    return
  fi

  set +e
  bash "${script_path}" > "${out_file}" 2>&1
  local test_exit=$?
  set -e

  local output
  output=$(cat "${out_file}")
  local local_pass=$(echo "${output}" | grep -c '\[PASS\]' || true)
  local local_fail=$(echo "${output}" | grep -c '\[FAIL\]' || true)
  local local_skip=$(echo "${output}" | grep -c '\[SKIP\]' || true)

  local res_status="PASS"
  if [ "${local_fail}" -gt 0 ] || [ "${test_exit}" -ne 0 ]; then
    res_status="FAIL"
  elif [ "${local_skip}" -gt 0 ] && [ "${local_pass}" -eq 0 ]; then
    res_status="SKIP"
  fi

  echo "${res_status}:${local_pass}:${local_fail}:${local_skip}" > "${status_file}"
}

if [ "${JOBS}" -le 1 ] || [ "${TOTAL_RUN}" -le 1 ]; then
  for idx in "${!TARGET_TESTS[@]}"; do
    run_single_test "${idx}" "${TARGET_TESTS[$idx]}"
    cat "${TMP_DIR}/test_${idx}.log"
  done
else
  running=0
  for idx in "${!TARGET_TESTS[@]}"; do
    run_single_test "${idx}" "${TARGET_TESTS[$idx]}" &
    running=$((running + 1))
    if [ "${running}" -ge "${JOBS}" ]; then
      wait -n 2>/dev/null || wait
      running=$((running - 1))
    fi
  done
  wait

  for idx in "${!TARGET_TESTS[@]}"; do
    cat "${TMP_DIR}/test_${idx}.log"
  done
fi

for idx in "${!TARGET_TESTS[@]}"; do
  entry="${TARGET_TESTS[$idx]}"
  IFS=':' read -r id file desc <<< "${entry}"

  status_info=$(cat "${TMP_DIR}/test_${idx}.status" 2>/dev/null || echo "FAIL:0:1:0")
  IFS=':' read -r res_status l_pass l_fail l_skip <<< "${status_info}"

  TOTAL_PASS=$((TOTAL_PASS + l_pass))
  TOTAL_FAIL=$((TOTAL_FAIL + l_fail))
  TOTAL_SKIP=$((TOTAL_SKIP + l_skip))

  if [ "${res_status}" == "FAIL" ]; then
    RESULTS+=("${RED}FAIL${NC}  ${id}  ${desc}")
  elif [ "${res_status}" == "SKIP" ]; then
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

