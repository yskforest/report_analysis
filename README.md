# Report Analysis & Visualizer

本リポジトリは、複数の解析・品質測定ツール（Understand, cloc, PMD, Git diff）の出力を統合し、プロジェクト全体のサマリとインタラクティブな各種可視化（Treemap, Pie chart等）を設定ファイル駆動で生成するPythonツールを提供します。

---

## Quick Reference

```bash
# 統合静的解析レポートの生成（デフォルト可視化を実行する場合）
python3 src/report_analysis.py \
  sample_data/und_metrics.csv \
  sample_data/cloc/cloc.csv \
  "sample_data/pmd/*.xml" \
  sample_data/git_numstat.tsv \
  out/report "/"

# 統合静的解析レポートの生成（config.yamlでカスタム可視化を指定する場合）
python3 src/report_analysis.py \
  --config config.yaml \
  sample_data/und_metrics.csv \
  sample_data/cloc/cloc.csv \
  "sample_data/pmd/*.xml" \
  sample_data/git_numstat.tsv \
  out/report "/"

# テスト実行
bash tests/run_tests.sh

# cloc の実行（入力データ準備用）
cloc --by-file --csv -out=${OUT_DIR}/cloc.csv ${SRC_DIR}
```

---

## 環境準備

Python 3.9 以上が必要です（3.12 推奨）。

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 使用方法

### 1. 統合静的解析レポート生成 (`report_analysis.py`)

指定された各種解析ツールの出力ファイル（省略時は `none` を指定）をパース・マージし、統合レポートと可視化を `OUTPUT_DIR` に出力します。  
各入力は省略可能で、存在する入力のみで処理を実行します（部分実行）。

#### コマンド書式

```bash
python3 src/report_analysis.py \
  [--config CONFIG_YAML] \
  {UND_CSV|none} \
  {CLOC_CSV|none} \
  {PMD_XML_GLOB_OR_LIST|none} \
  {GIT_NUMSTAT|none} \
  {OUTPUT_DIR} \
  {REMOVE_PATH_PREFIX}
```

#### 引数

| 引数 | 説明 |
|---|---|
| `--config` | 可視化構成をカスタマイズする YAML ファイル（オプション）。指定しない場合はデフォルト可視化が出力されます。 |
| `UND_CSV` | Understand から出力したメトリクス CSV。`none` で省略。 |
| `CLOC_CSV` | cloc から出力した CSV。`none` で省略。 |
| `PMD_XML_GLOB_OR_LIST` | PMD CPD の XML ファイル。glob（`*.xml`）や区切りリスト（`,` / `:`）で複数指定可。`none` で省略。 |
| `GIT_NUMSTAT` | `git diff --numstat` 形式のテキストファイル。`none` で省略。 |
| `OUTPUT_DIR` | 出力先ディレクトリ（未存在時は自動作成）。 |
| `REMOVE_PATH_PREFIX` | パス正規化時に除去するプレフィックス。 |

---

### 2. 設定ファイル (`config.yaml`) によるカスタム可視化

`--config` オプションで渡す YAML ファイルで、面積や色に割り当てるメトリクス（プレフィックス付き列名）を自由に指定して HTML の可視化ファイルを生成できます。

#### `config.yaml` の記述例

```yaml
# 出力したい可視化の定義リスト
visualizations:
  - type: treemap
    metric_area: cloc_code          # 面積: CLOCコード行数
    metric_color: pmd_clone_ratio   # 色: PMDの重複率
    output_file: "custom_cloc_pmd_treemap.html" # OUTPUT_DIRからの相対パス
  - type: treemap
    metric_area: git_ChangedLines   # 面積: Gitの合計変更行数
    metric_color: git_AddedLines    # 色: Gitの追加行数
    output_file: "custom_git_diff_treemap.html"
  - type: pie_chart
    metric: cloc_language           # 言語ごとの円グラフ
    output_file: "custom_cloc_pie.html"
```

#### 主要な出力物

| 出力先 | 内容 |
|---|---|
| `OUTPUT_DIR/summary_report.csv` | 全体タスクサマリ |
| `OUTPUT_DIR/metrics_merge.csv` | 全ツール結果の統合マージ（`File` 列で外部結合） |
| `OUTPUT_DIR/und/` | Understand 解析結果（CSV、Treemap HTML） |
| `OUTPUT_DIR/cloc/` | CLOC 解析結果（言語比率円グラフ等） |
| `OUTPUT_DIR/pmd/` | PMD 解析結果（clone ratio CSV、Treemap HTML） |
| `OUTPUT_DIR/git/` | Git diff 解析結果（ファイル別 CSV、サマリ CSV） |

#### 終了コード

- `0`: 正常終了（タスクのうち1つ以上が成功）
- `1`: 異常終了（引数不正、全入力が無効、または config.yaml の構文・カラム指定にエラーがある等）

---

## テスト

受け入れ基準（AC-01〜AC-09）を自動検証するテストスイートを提供しています。  
テスト仕様の詳細は [docs/requirements.md](docs/requirements.md) の「7. 受け入れ基準」を参照してください。

### テスト実行

```bash
# 全テスト実行
bash tests/run_tests.sh

# 個別テスト指定（スペース区切りで複数可）
bash tests/run_tests.sh ac01 ac05

# テスト一覧の表示
bash tests/run_tests.sh --list
```

### テスト一覧

| ID | テストファイル | 検証内容 |
|---|---|---|
| ac01 | `test_ac01_und_path_normalization.sh` | UND CSV の Windows 形式パスが `/` に正規化される |
| ac02 | `test_ac02_cloc_output.sh` | CLOC 入力で pie chart HTML と CSV が生成される |
| ac03 | `test_ac03_pmd_integration.sh` | 複数 PMD XML が統合解析される |
| ac04 | `test_ac04_partial_input.sh` | 一部入力のみで正常終了する（部分実行） |
| ac05 | `test_ac05_all_none.sh` | 全入力なしで終了コード 1 を返す |
| ac06 | `test_ac06_merge_prefix.sh` | `metrics_merge.csv` にツール別プレフィックスが付与される |
| ac07 | `test_ac07_config_visualization.sh` | `config.yaml` で指定したカスタム可視化 HTML が正常に生成される |
| ac08 | `test_ac08_config_exclusion.sh` | `config.yaml` に指定のない可視化は生成されない |
| ac09 | `test_ac09_config_invalid.sh` | YAMLの構文エラーや存在しない列の指定で終了コード 1 を返す |

---

## ドキュメント

| ファイル | 内容 |
|---|---|
| [docs/requirements.md](docs/requirements.md) | 要求仕様書（機能要求・非機能要求・受け入れ基準） |
| [docs/design.md](docs/design.md) | 実行設計書（アーキテクチャ・データモデル・処理シーケンス） |

---

## ディレクトリ構成

```text
hc_new_arch/
├── README.md                          # 本ドキュメント
├── requirements.txt                   # 依存ライブラリ
├── docker-compose.yml                 # コンテナ実行用構成
├── Dockerfile                         # コンテナイメージビルド用
├── docs/
│   ├── requirements.md                # 要求仕様書
│   └── design.md                      # 実行設計書
├── tests/
│   ├── run_tests.sh                   # テストランナー
│   ├── test_helpers.sh                # テスト共通ヘルパー関数
│   └── test_ac{01-09}_*.sh            # 受け入れ基準別テスト
├── sample_data/                       # テスト・サンプルデータ群
│   ├── cloc/cloc.csv
│   ├── pmd/*.xml
│   ├── und_metrics.csv
│   └── git_numstat.tsv
└── src/
    ├── report_analysis.py             # 統合レポートオーケストレーター
    ├── analyzers.py                   # UND/CLOC/PMD/Git の解析ロジック
    ├── io_models.py                   # I/O モデルと入力解決処理
    ├── advanced_visualizations.py     # 高度・カスタム可視化処理
    └── plotly_visualize.py            # Plotly 汎用可視化ユーティリティ
```

---

## アーキテクチャ

`report_analysis.py` がオーケストレーターとなり、入力ファイルを `io_models.py` で検証・解決したうえで、`analyzers.py` で個別のツール出力を解析し `metrics_merge.csv` にマージします。

最後に `advanced_visualizations.py` を呼び出し、`--config` で指定された `visualizations` の定義（またはデフォルト定義）に沿って `metrics_merge.csv` 内のカラムから汎用的かつ動的に HTML 可視化（Treemap 等）を生成します。
