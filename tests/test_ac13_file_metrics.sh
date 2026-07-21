#!/usr/bin/env bash
# AC-13〜17: file_metrics.py および report_analysis.py 連携の検証
# 対応要求: FR-FM-01〜07, AC-13〜17

source "$(dirname "$0")/test_helpers.sh"
activate_venv

begin_test "AC-13-17" "ファイルメトリクス収集・連携の総合検証"

OUT=$(setup_output_dir "ac13")
TEST_SCAN_DIR="${OUT}/scan_dir"
mkdir -p "${TEST_SCAN_DIR}"

# テストファイルの作成
# 1. LF 改行コードのテキストファイル
echo -e "line1\nline2\nline3" > "${TEST_SCAN_DIR}/file_lf.txt"
# 2. CRLF 改行コード of テキストファイル
printf "line1\r\nline2\r\nline3\r\n" > "${TEST_SCAN_DIR}/file_crlf.txt"
# 3. バイナリファイル (先頭にNULバイトを含む)
printf "\x00\x01\x02\x03hello" > "${TEST_SCAN_DIR}/file_binary.bin"

# 実行 1: file_metrics.py の単体実行
FM_CSV="${OUT}/file_metrics_out.csv"
python3 "${PROJECT_DIR}/src/file_metrics.py" "${TEST_SCAN_DIR}" "${FM_CSV}" --remove-prefix "${TEST_SCAN_DIR}"

# 検証: AC-13 - CSVが存在し全カラムが含まれるか
assert_file_exists "${FM_CSV}" "file_metrics_out.csv"
assert_csv_has_column "${FM_CSV}" "file"
assert_csv_has_column "${FM_CSV}" "file_size_bytes"
assert_csv_has_column "${FM_CSV}" "is_binary"
assert_csv_has_column "${FM_CSV}" "encoding"
assert_csv_has_column "${FM_CSV}" "encoding_confidence"
assert_csv_has_column "${FM_CSV}" "line_ending"
assert_csv_has_column "${FM_CSV}" "line_count"
assert_csv_has_column "${FM_CSV}" "extension"
assert_csv_has_column "${FM_CSV}" "mime_type"
assert_csv_has_column "${FM_CSV}" "has_bom"
assert_csv_has_column "${FM_CSV}" "last_modified"

# 各出力行の値検証 (Pythonを使用)
python3 -c "
import csv
with open('${FM_CSV}', newline='') as f:
    rows = {row['file']: row for row in csv.DictReader(f)}
    
    # AC-14: バイナリファイルの検証
    bin_row = rows.get('file_binary.bin')
    assert bin_row is not None, 'file_binary.bin missing'
    assert bin_row['is_binary'] == 'True', 'Expected is_binary=True'
    assert bin_row['encoding'] == '', f'Expected empty encoding, got {bin_row[\"encoding\"]}'
    assert bin_row['line_ending'] == 'N/A', f'Expected line_ending=N/A, got {bin_row[\"line_ending\"]}'
    
    # AC-15: 改行コードの検証
    lf_row = rows.get('file_lf.txt')
    assert lf_row is not None, 'file_lf.txt missing'
    assert lf_row['line_ending'] == 'LF', f'Expected line_ending=LF, got {lf_row[\"line_ending\"]}'
    assert int(lf_row['line_count']) == 3, f'Expected line_count=3, got {lf_row[\"line_count\"]}'
    
    crlf_row = rows.get('file_crlf.txt')
    assert crlf_row is not None, 'file_crlf.txt missing'
    assert crlf_row['line_ending'] == 'CRLF', f'Expected line_ending=CRLF, got {crlf_row[\"line_ending\"]}'
    assert int(crlf_row['line_count']) == 3, f'Expected line_count=3, got {crlf_row[\"line_count\"]}'
    
print('[PASS] AC-14 & AC-15: file metrics rows and line endings validated successfully')
" || fail "AC-14 / AC-15 validation failed"

# 実行 2: report_analysis.py への連携 (AC-16)
OUT_REPORT="${OUT}/report"
python3 "${PROJECT_DIR}/src/report_analysis.py" \
  none none none none \
  "${FM_CSV}" \
  "${OUT_REPORT}" "/"

# 検証: AC-16
# 1. OUTPUT_DIR/file/file_metrics.csv が生成されているか
assert_file_exists "${OUT_REPORT}/file/file_metrics.csv" "file_metrics.csv in report output"

# 2. metrics_merge.csv に fm_ プレフィックス列が含まれるか
MERGE_CSV="${OUT_REPORT}/metrics_merge.csv"
assert_file_exists "${MERGE_CSV}" "metrics_merge.csv"
assert_csv_has_column "${MERGE_CSV}" "fm_file_size_bytes"
assert_csv_has_column "${MERGE_CSV}" "fm_is_binary"
assert_csv_has_column "${MERGE_CSV}" "fm_encoding"

# 3. metrics_report.xlsx に file_metrics シートが存在するか
XLSX_FILE="${OUT_REPORT}/metrics_report.xlsx"
assert_file_exists "${XLSX_FILE}" "metrics_report.xlsx"
python3 -c "
import openpyxl
wb = openpyxl.load_workbook('${XLSX_FILE}', read_only=True)
assert 'file_metrics' in wb.sheetnames, 'Missing file_metrics sheet in Excel'
ws = wb['file_metrics']
headers = [cell.value for cell in next(ws.iter_rows(max_row=1))]
assert 'File' in headers, 'file_metrics sheet missing File header'
assert 'is_binary' in headers, 'file_metrics sheet missing is_binary header'
" || fail "Excel file_metrics validation failed"

# 実行 3: FILE_METRICS_CSV に none を指定した場合のスキップ検証 (AC-17)
OUT_SKIP="${OUT}/report_skip"
assert_exit_code 0 "AC-17: FILE_METRICS_CSV=none で exit 0" \
  python3 "${PROJECT_DIR}/src/report_analysis.py" \
  "${PROJECT_DIR}/sample_data/und_metrics.csv" \
  none none none \
  none \
  "${OUT_SKIP}" "/"

# ファイルメトリクス関連の出力がスキップされ空であることの確認
assert_file_not_exists "${OUT_SKIP}/file/file_metrics.csv" "skipped file_metrics.csv"

cleanup_output_dir "ac13"
print_summary
