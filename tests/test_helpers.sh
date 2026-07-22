#!/usr/bin/env bash
# tests/test_helpers.sh — テスト共通ヘルパー関数
# source して使用する。各テストスクリプトの冒頭で source する。

set -uo pipefail

# ── 色定義 ──
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── カウンター ──
_PASS=0
_FAIL=0
_SKIP=0
_CURRENT_TEST=""

# ── プロジェクトパス ──
TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"; pwd)"
PROJECT_DIR="$(cd "${TESTS_DIR}/.."; pwd)"
FIXTURES_DIR="${TESTS_DIR}/fixtures"
OUT_BASE="${PROJECT_DIR}/out/tests"

# ── venv 有効化 ──
activate_venv() {
  if [ -d "${PROJECT_DIR}/venv" ]; then
    source "${PROJECT_DIR}/venv/bin/activate"
  else
    echo -e "${RED}[ERROR] venv not found at ${PROJECT_DIR}/venv${NC}" >&2
    exit 1
  fi
}

# ── テスト出力ディレクトリ管理 ──
setup_output_dir() {
  local name="$1"
  local dir="${OUT_BASE}/${name}"
  rm -rf "${dir}"
  mkdir -p "${dir}"
  echo "${dir}"
}

cleanup_output_dir() {
  local name="$1"
  rm -rf "${OUT_BASE}/${name}"
}

# ── テスト結果記録 ──
pass() {
  local msg="${1:-${_CURRENT_TEST}}"
  _PASS=$((_PASS + 1))
  echo -e "  ${GREEN}[PASS]${NC} ${msg}"
}

fail() {
  local msg="${1:-${_CURRENT_TEST}}"
  _FAIL=$((_FAIL + 1))
  echo -e "  ${RED}[FAIL]${NC} ${msg}" >&2
}

skip() {
  local msg="${1:-${_CURRENT_TEST}}"
  _SKIP=$((_SKIP + 1))
  echo -e "  ${YELLOW}[SKIP]${NC} ${msg}"
}

# ── テストセクション表示 ──
begin_test() {
  local ac_id="$1"
  local description="$2"
  _CURRENT_TEST="${ac_id}: ${description}"
  echo ""
  echo -e "${CYAN}${BOLD}── ${ac_id}: ${description} ──${NC}"
}

# ── アサーション関数 ──

# ファイルが存在し非空であることを確認
assert_file_exists() {
  local path="$1"
  local label="${2:-$(basename "$path")}"
  if [ -f "${path}" ] && [ -s "${path}" ]; then
    pass "${label} exists and non-empty"
  else
    fail "${label} missing or empty: ${path}"
  fi
}

# ファイルが存在しないことを確認
assert_file_not_exists() {
  local path="$1"
  local label="${2:-$(basename "$path")}"
  if [ ! -f "${path}" ]; then
    pass "${label} does not exist (expected)"
  else
    fail "${label} unexpectedly exists: ${path}"
  fi
}

# ディレクトリが空または存在しないことを確認
assert_dir_empty_or_missing() {
  local path="$1"
  local label="${2:-$(basename "$path")}"
  if [ ! -d "${path}" ] || [ -z "$(ls -A "${path}" 2>/dev/null)" ]; then
    pass "${label} is empty or missing (expected)"
  else
    fail "${label} unexpectedly has content: ${path}"
  fi
}

# 終了コードを検証
assert_exit_code() {
  local expected="$1"
  shift
  local label="${1}"
  shift

  # コマンドを実行し終了コードを取得（set -e を一時無効化）
  set +e
  "$@" > /dev/null 2>&1
  local actual=$?
  set -e

  if [ "${actual}" -eq "${expected}" ]; then
    pass "${label}: exit code = ${expected}"
  else
    fail "${label}: expected exit code ${expected}, got ${actual}"
  fi
}

# 終了コードを検証（stderr を変数にキャプチャ）
assert_exit_code_with_stderr() {
  local expected="$1"
  local label="$2"
  shift 2

  set +e
  local stderr_output
  stderr_output=$("$@" 2>&1 1>/dev/null)
  local actual=$?
  set -e

  if [ "${actual}" -eq "${expected}" ]; then
    pass "${label}: exit code = ${expected}"
  else
    fail "${label}: expected exit code ${expected}, got ${actual}"
  fi

  # stderr の内容を返す（呼び出し側で検証可能）
  echo "${stderr_output}"
}

# CSV に指定列が存在することを確認
assert_csv_has_column() {
  local csv="$1"
  local column="$2"
  local label="${3:-${column} column in $(basename "$csv")}"

  if [ ! -f "${csv}" ]; then
    fail "${label}: CSV file not found: ${csv}"
    return
  fi

  local header
  header=$(head -n1 "${csv}")
  if echo "${header}" | grep -q "${column}"; then
    pass "${label}"
  else
    fail "${label}: column '${column}' not found in header"
  fi
}

# CSV の指定列にバックスラッシュが含まれないことを確認
assert_csv_no_backslash() {
  local csv="$1"
  local column="$2"
  local label="${3:-No backslash in ${column} column}"

  if [ ! -f "${csv}" ]; then
    fail "${label}: CSV file not found: ${csv}"
    return
  fi

  # Python で列を抽出して \ を検索
  local result
  result=$(python3 -c "
import csv, sys
with open('${csv}', newline='') as f:
    reader = csv.DictReader(f)
    if '${column}' not in reader.fieldnames:
        print('COLUMN_NOT_FOUND')
        sys.exit(0)
    for row in reader:
        if '\\\\' in row.get('${column}', ''):
            print('FOUND')
            sys.exit(0)
print('OK')
")

  case "${result}" in
    OK) pass "${label}" ;;
    COLUMN_NOT_FOUND) fail "${label}: column '${column}' not found" ;;
    FOUND) fail "${label}: backslash found in column '${column}'" ;;
    *) fail "${label}: unexpected result: ${result}" ;;
  esac
}

# CSV の行数が最低値以上であることを確認（ヘッダー除く）
assert_csv_min_rows() {
  local csv="$1"
  local min="$2"
  local label="${3:-$(basename "$csv") has >= ${min} data rows}"

  if [ ! -f "${csv}" ]; then
    fail "${label}: CSV file not found: ${csv}"
    return
  fi

  local count
  count=$(tail -n +2 "${csv}" | wc -l | tr -d ' ')
  if [ "${count}" -ge "${min}" ]; then
    pass "${label} (${count} rows)"
  else
    fail "${label}: expected >= ${min} rows, got ${count}"
  fi
}

# ── フィクスチャ生成 ──

# UND CSV の先頭N行からWindows形式パスのテストCSVを生成
generate_und_win_fixture() {
  local source_csv="${PROJECT_DIR}/sample_data/und_metrics.csv"
  local output_csv="${FIXTURES_DIR}/und_win_paths.csv"

  mkdir -p "${FIXTURES_DIR}"

  if [ -s "${output_csv}" ]; then
    echo "${output_csv}"
    return 0
  fi

  if [ ! -f "${source_csv}" ]; then
    echo "[WARN] Source UND CSV not found: ${source_csv}" >&2
    return 1
  fi

  # ヘッダー + 先頭50行を取り出し、パス区切りを \ に変換
  python3 -c "
import csv, sys

with open('${source_csv}', newline='') as fin, \
     open('${output_csv}', 'w', newline='') as fout:
    reader = csv.DictReader(fin)
    writer = csv.DictWriter(fout, fieldnames=reader.fieldnames)
    writer.writeheader()
    for i, row in enumerate(reader):
        if i >= 50:
            break
        # File 列と Name 列のパス区切りを Windows 形式に変換
        for col in ['File', 'Name']:
            if col in row and row[col]:
                row[col] = row[col].replace('/', '\\\\')
        writer.writerow(row)
"
  echo "${output_csv}"
}

# ── サマリ表示 ──
print_summary() {
  local total=$((_PASS + _FAIL + _SKIP))
  echo ""
  echo "=================================================="
  echo -e " Results: ${GREEN}${_PASS} passed${NC}, ${RED}${_FAIL} failed${NC}, ${YELLOW}${_SKIP} skipped${NC} / ${total} total"
  echo "=================================================="

  if [ "${_FAIL}" -gt 0 ]; then
    return 1
  fi
  return 0
}
