#!/usr/bin/env bash
# AC-11: UND CSV を入力すると `OUTPUT_DIR/file_metrics_hierarchy.xlsx` が生成され、
# summary シートと hierarchy シートが正しく含まれていること。

source "$(dirname "$0")/test_helpers.sh"
activate_venv

begin_test "AC-11" "ファイルメトリクス階層 Excel レポート検証"

OUT=$(setup_output_dir "ac11")

# 実行
python3 "${PROJECT_DIR}/src/report_analysis.py" \
  "${PROJECT_DIR}/sample_data/und_metrics.csv" \
  none none none \
  "${OUT}" "/"

# 検証
XLSX_FILE="${OUT}/metrics_report.xlsx"
assert_file_exists "${XLSX_FILE}" "metrics_report.xlsx"

# Excelのシート構造を Python を使って確認
python3 -c "
import openpyxl
wb = openpyxl.load_workbook('${XLSX_FILE}', read_only=True)
sheets = wb.sheetnames
assert 'summary' in sheets, 'Missing summary sheet'
assert 'file_hierarchy' in sheets, 'Missing file_hierarchy sheet'

# file_hierarchy シートの簡易データ検証
ws = wb['file_hierarchy']
headers = [cell.value for cell in next(ws.iter_rows(max_row=1))]
assert 'Level' in headers, 'Missing Level col'
assert 'Path' in headers, 'Missing Path col'
assert 'SourceLines' in headers, 'Missing SourceLines col'
print('Excel sheets and hierarchy columns validated successfully')
" || fail "Excel sheet validation failed"

cleanup_output_dir "ac11"
print_summary