#!/usr/bin/env bash
# AC-09: config.yaml の構文エラーや、存在しない列を指定した場合は終了コード 1 で異常終了する
# 対応要求: AC-09

source "$(dirname "$0")/test_helpers.sh"
activate_venv

begin_test "AC-09" "config.yaml 異常系エラーハンドリング"

OUT=$(setup_output_dir "ac09")

# 1. 構文エラーのある YAML のテスト
CONFIG_SYNTAX_ERROR="${OUT}/config_syntax_error.yaml"
cat <<EOF > "${CONFIG_SYNTAX_ERROR}"
visualizations:
  - type: treemap
  [invalid syntax here
EOF

assert_exit_code 1 "AC-09: YAML 構文エラーで終了コード 1" \
  python3 "${PROJECT_DIR}/src/report_analysis.py" \
  --config "${CONFIG_SYNTAX_ERROR}" \
  none \
  "${PROJECT_DIR}/sample_data/cloc/cloc.csv" \
  none none \
  none \
  "${OUT}" "/"

# 2. 存在しない列（カラム）を指定した YAML のテスト
CONFIG_INVALID_COLUMN="${OUT}/config_invalid_column.yaml"
cat <<EOF > "${CONFIG_INVALID_COLUMN}"
visualizations:
  - type: treemap
    metric_area: nonexistent_column_xyz
    output_file: "invalid_treemap.html"
EOF

assert_exit_code 1 "AC-09: 存在しない列の指定で終了コード 1" \
  python3 "${PROJECT_DIR}/src/report_analysis.py" \
  --config "${CONFIG_INVALID_COLUMN}" \
  none \
  "${PROJECT_DIR}/sample_data/cloc/cloc.csv" \
  none none \
  none \
  "${OUT}" "/"

cleanup_output_dir "ac09"
print_summary
