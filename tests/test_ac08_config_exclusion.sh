#!/usr/bin/env bash
# AC-08: config.yaml の visualizations セクションで指定されていない可視化ファイルは生成されない
# 対応要求: FR-CLI-06, AC-08

source "$(dirname "$0")/test_helpers.sh"
activate_venv

begin_test "AC-08" "指定外の可視化ファイルが生成されない検証"

OUT=$(setup_output_dir "ac08")

# 一時的な config.yaml を作成（Pieのみ指定、Treemapは指定しない）
CONFIG_FILE="${OUT}/config.yaml"
cat <<EOF > "${CONFIG_FILE}"
visualizations:
  - type: pie_chart
    metric: cloc_language
    output_file: "custom_pie.html"
EOF

# 実行
python3 "${PROJECT_DIR}/src/report_analysis.py" \
  --config "${CONFIG_FILE}" \
  none \
  "${PROJECT_DIR}/sample_data/cloc/cloc.csv" \
  none none \
  "${OUT}" "/"

# 検証: 指定された Pie Chart は生成されている
assert_file_exists "${OUT}/custom_pie.html" "custom_pie.html"

# 検証: 指定していない可視化ファイルは生成されていない
assert_file_not_exists "${OUT}/custom_treemap.html" "custom_treemap.html"
assert_file_not_exists "${OUT}/visualizations/16_treemap_loc_vs_cyclomatic.html" "Default treemap 1"
assert_file_not_exists "${OUT}/visualizations/17_treemap_loc_vs_clone_ratio.html" "Default treemap 2"

cleanup_output_dir "ac08"
print_summary
