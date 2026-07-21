#!/usr/bin/env bash
# AC-12: UND CSV を入力すると `OUTPUT_DIR/func_metrics.xlsx` が生成され、
# 期待されるシート群と集計結果が正しく含まれていること。

source "$(dirname "$0")/test_helpers.sh"
activate_venv

begin_test "AC-12" "関数メトリクス Excel レポート検証"

OUT=$(setup_output_dir "ac12")

# 実行
python3 "${PROJECT_DIR}/src/report_analysis.py" \
  "${PROJECT_DIR}/sample_data/und_metrics.csv" \
  none none none \
  none \
  "${OUT}" "/"

# 検証
XLSX_FILE="${OUT}/metrics_report.xlsx"
assert_file_exists "${XLSX_FILE}" "metrics_report.xlsx"

# Excelのシート構造を Python を使って確認
python3 -c "
import openpyxl
wb = openpyxl.load_workbook('${XLSX_FILE}', read_only=True)
sheets = wb.sheetnames
for s in ['summary', 'func_detail', 'func_level_agg', 'func_dist_nesting', 'func_dist_cyclomatic', 'func_dist_essential']:
    assert s in sheets, f'Missing {s} sheet'

# func_detail シートの簡易データ検証
ws = wb['func_detail']
headers = [cell.value for cell in next(ws.iter_rows(max_row=1))]
assert 'Level0' in headers, 'Missing Level0 col'
assert 'Level15' in headers, 'Missing Level15 col'
assert 'MaxNesting' in headers, 'Missing MaxNesting col'
print('Excel sheets and function columns validated successfully')
" || fail "Excel sheet validation failed"

cleanup_output_dir "ac12"
print_summary