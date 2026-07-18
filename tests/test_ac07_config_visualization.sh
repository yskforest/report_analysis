#!/usr/bin/env bash
# AC-07: report_analysis.py に config.yaml で指定した可視化構成を渡すと、指定された面積/色マッピングのHTMLが生成される
# 対応要求: FR-CLI-06, FR-CLI-01

source "$(dirname "$0")/test_helpers.sh"
activate_venv

begin_test "AC-07" "config.yaml によるカスタム可視化生成"

OUT=$(setup_output_dir "ac07")

# 一時的な config.yaml を作成
CONFIG_FILE="${OUT}/config.yaml"
cat <<EOF > "${CONFIG_FILE}"
visualizations:
  - type: treemap
    metric_area: cloc_code
    metric_color: git_ChangedLines
    output_file: "vis/treemap.html"
  - type: pie_chart
    metric: cloc_language
    output_file: "vis/pie.html"
EOF

# 実行
python3 "${PROJECT_DIR}/src/report_analysis.py" \
  --config "${CONFIG_FILE}" \
  none \
  "${PROJECT_DIR}/sample_data/cloc/cloc.csv" \
  none \
  "${PROJECT_DIR}/sample_data/git_numstat.tsv" \
  "${OUT}" "/"

# 検証: 指定されたファイルが生成されている
assert_file_exists "${OUT}/vis/treemap.html" "treemap.html"
assert_file_exists "${OUT}/vis/pie.html" "pie.html"

cleanup_output_dir "ac07"
print_summary
