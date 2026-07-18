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
    output_file: "vis/pie.html"
EOF

# 実行
python3 "${PROJECT_DIR}/src/report_analysis.py" \
  --config "${CONFIG_FILE}" \
  none \
  "${PROJECT_DIR}/sample_data/cloc/cloc.csv" \
  none none \
  "${OUT}" "/"

# 検証: 指定された Pie Chart は生成されている
assert_file_exists "${OUT}/vis/pie.html" "pie.html"

# 検証: 指定していない可視化ファイルは生成されていない
assert_file_not_exists "${OUT}/vis/treemap.html" "treemap.html"
assert_file_not_exists "${OUT}/visualizations" "Default visualizations directory"

cleanup_output_dir "ac08"
print_summary
