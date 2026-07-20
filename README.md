# Report Analysis & Visualizer

複数の静的解析・品質計測ツール（Understand / cloc / PMD / Git diff）の出力と、ファイルメトリクス収集結果を **1 つの統合 CSV にマージ** し、設定ファイル駆動で **インタラクティブな HTML 可視化**（Treemap・散布図・円グラフ等）を生成する Python ツールです。

---

## Quick Start

```bash
# 1. 環境構築（Python 3.9+、推奨 3.12）
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. ファイルメトリクスを収集（任意）
python3 src/file_metrics.py {SCAN_DIR} sample_data/file_metrics.csv \
  --remove-prefix {PREFIX}

# 3. 統合レポート生成
python3 src/report_analysis.py --config config.yaml \
  sample_data/und_metrics.csv \
  sample_data/cloc/cloc.csv \
  "sample_data/pmd/*.xml" \
  sample_data/git_numstat.tsv \
  sample_data/file_metrics.csv \
  out/report "/"
```

---

## ツール構成

本リポジトリは **2 つのスクリプト** で構成されます。

| スクリプト | 役割 |
|---|---|
| `src/report_analysis.py` | 各種ツール出力を統合・可視化するメインオーケストレーター |
| `src/file_metrics.py` | ディレクトリを走査してファイル属性（サイズ・エンコーディング・改行コード等）を CSV 出力 |

---

## 1. report_analysis.py — 統合レポート生成

### コマンド書式

```bash
python3 src/report_analysis.py [--config CONFIG_YAML] \
  {UND_CSV|none} {CLOC_CSV|none} {PMD_XML|none} \
  {GIT_NUMSTAT|none} {FILE_METRICS_CSV|none} \
  {OUTPUT_DIR} {REMOVE_PATH_PREFIX}
```

各入力は **`none` で省略可能**（存在する入力のみで処理を実行）。

### 引数一覧

| 引数 | 説明 |
|---|---|
| `--config` | カスタム可視化・閾値を定義する YAML（省略時はデフォルト出力のみ） |
| `UND_CSV` | Understand メトリクス CSV |
| `CLOC_CSV` | cloc 出力 CSV |
| `PMD_XML` | PMD CPD の XML（glob `*.xml` やカンマ/コロン区切りで複数指定可） |
| `GIT_NUMSTAT` | `git diff --numstat` 形式テキスト |
| `FILE_METRICS_CSV` | `file_metrics.py` で生成した CSV |
| `OUTPUT_DIR` | 出力先ディレクトリ（自動作成） |
| `REMOVE_PATH_PREFIX` | パス正規化で除去するプレフィックス |

### 出力物

| パス | 内容 |
|---|---|
| `metrics_merge.csv` | 全ツール結果を `File` 列で外部結合した統合 CSV |
| `summary.csv` | タスク実行サマリ |
| `metrics_report.xlsx` | 統合 Excel レポート |
| `und/` | Understand 解析結果・閾値超過レポート・Treemap |
| `cloc/` | CLOC 解析結果・言語比率グラフ |
| `pmd/` | PMD 解析結果・clone ratio CSV・Treemap |
| `git/` | Git diff ファイル別・サマリ CSV |
| `file/` | ファイルメトリクス CSV（`fm_` プレフィックスでマージ結合） |
| `vis/` | 複合・カスタム可視化 HTML |

### 終了コード

- **`0`** — 正常終了（1 つ以上のタスクが成功）
- **`1`** — 異常終了（引数不正・全入力無効・config エラー等）

---

## 2. file_metrics.py — ファイルメトリクス収集

### コマンド書式

```bash
python3 src/file_metrics.py {SCAN_DIR} {OUTPUT_CSV} \
  [--remove-prefix PREFIX] [--exclude GLOB ...]
```

### 引数一覧

| 引数 | 説明 |
|---|---|
| `SCAN_DIR` | 再帰走査するルートディレクトリ |
| `OUTPUT_CSV` | 出力 CSV パス |
| `--remove-prefix` | ファイルパスから除去するプレフィックス |
| `--exclude` | 追加の除外パターン（fnmatch 形式）。デフォルトで `.git`・`node_modules` 等を除外 |

### 収集メトリクス

| 列名 | 内容 |
|---|---|
| `file` | 正規化済みファイルパス |
| `file_size_bytes` | ファイルサイズ（バイト） |
| `is_binary` | バイナリ判定 |
| `encoding` | 文字コード推定（バイナリは空） |
| `encoding_confidence` | エンコーディング信頼度（0.0〜1.0） |
| `line_ending` | 改行コード（`LF` / `CRLF` / `CR` / `mixed` / `N/A`） |
| `line_count` | 総行数（バイナリは 0） |
| `extension` | 拡張子 |
| `mime_type` | MIME タイプ推定 |
| `has_bom` | BOM 有無 |
| `last_modified` | 最終更新日時（ISO 8601） |

> `metrics_merge.csv` に結合時は `fm_` プレフィックスが付与されます（例: `fm_file_size_bytes`）。

---

## 3. config.yaml — カスタム可視化と閾値設定

`--config` で渡す YAML ファイルで **可視化の種類・使用カラム・出力先** を自由に定義できます。

### 可視化タイプ一覧

| type | 説明 | 主要パラメータ |
|---|---|---|
| `treemap` | ツリーマップ | `metric_area`, `metric_color` |
| `pie_chart` | 円グラフ | `metric`, `value_metric` |
| `scatter` | 散布図 | `metric_x`, `metric_y`, `metric_size` |
| `bar` | 棒グラフ | `metric_x`, `metric_y`, `top_n` |
| `box` | 箱ひげ図 | `metric_x`, `metric_y` |
| `violin` | バイオリン図 | `metric_x`, `metric_y` |
| `histogram` | ヒストグラム | `metric_x`, `nbins` |
| `density_heatmap` | 密度ヒートマップ | `metric_x`, `metric_y` |
| `ecdf` | 累積分布関数 | `metric_x` |
| `sunburst` | サンバースト図 | `path`, `metric_values` |
| `line` | 折れ線グラフ | `metric_x`, `metric_y` |

### config.yaml 記述例

```yaml
visualizations:
  - type: treemap
    metric_area: cloc_code            # 面積: コード行数
    metric_color: pmd_PmdCloneRatio   # 色: 重複率
    output_file: "vis/cloc_pmd_treemap.html"

  - type: treemap
    metric_area: und_total_functions  # 面積: ファイル中の関数数
    metric_color: und_exceeded_ratio  # 色: 基準値超過率
    output_file: "und/func_count_exceeded_ratio_treemap.html"

  - type: pie_chart
    metric: cloc_language
    value_metric: cloc_code
    output_file: "cloc/language_pie.html"

# メトリクス基準値（Understand 関数単位）
thresholds:
  MaxNesting: 5
  Essential: 4
  Cyclomatic: 15
  CountLine: 200
  CountLineCode: 150
```

### メトリクスカラムのプレフィックス規則

`metrics_merge.csv` では各ツール出力のカラムにプレフィックスが付与されます。`config.yaml` ではこのプレフィックス付きカラム名を指定します。

| プレフィックス | 元ツール | 例 |
|---|---|---|
| `und_` | Understand | `und_CountLineCode`, `und_AvgCyclomatic`, `und_exceeded_ratio` |
| `cloc_` | cloc | `cloc_code`, `cloc_language` |
| `pmd_` | PMD | `pmd_PmdCloneRatio`, `pmd_PmdTotalTokens` |
| `git_` | Git diff | `git_AddedLines`, `git_ChangedLines` |
| `fm_` | file_metrics.py | `fm_file_size_bytes`, `fm_is_binary` |

---

## テスト

```bash
bash tests/run_tests.sh           # 全テスト
bash tests/run_tests.sh ac01 ac05 # 個別指定
bash tests/run_tests.sh --list    # 一覧表示
```

| ID | 検証内容 |
|---|---|
| ac01 | UND CSV パス正規化（`\` → `/`） |
| ac02 | CLOC 入力で pie chart・CSV 生成 |
| ac03 | 複数 PMD XML の統合解析 |
| ac04 | 部分入力での正常終了 |
| ac05 | 全入力なしで終了コード 1 |
| ac06 | マージ CSV にツール別プレフィックス付与 |
| ac07 | config 指定のカスタム可視化 HTML 生成 |
| ac08 | config 未指定の可視化は非生成 |
| ac09 | YAML 構文エラー・不正カラムで終了コード 1 |

詳細な受け入れ基準（AC-13〜AC-17 含む）は [docs/requirements.md](docs/requirements.md) を参照。

---

## ディレクトリ構成

```text
hc_new_arch/
├── config.yaml                    # 可視化・閾値設定サンプル
├── requirements.txt               # Python 依存ライブラリ
├── Dockerfile / docker-compose.yml
├── docs/
│   ├── requirements.md            # 要求仕様書
│   └── design.md                  # 実行設計書
├── tests/
│   ├── run_tests.sh               # テストランナー
│   └── test_ac{01-09}_*.sh        # 受け入れ基準別テスト
├── sample_data/                   # サンプル入力データ
│   ├── und_metrics.csv
│   ├── cloc/cloc.csv
│   ├── pmd/*.xml
│   ├── git_numstat.tsv
│   └── file_metrics.csv
└── src/
    ├── report_analysis.py         # メインオーケストレーター
    ├── file_metrics.py            # ファイルメトリクス収集
    ├── analyzers.py               # 各ツール解析ロジック
    ├── io_models.py               # I/O モデル・入力解決
    ├── advanced_visualizations.py # カスタム可視化エンジン
    ├── excel_reports.py           # Excel レポート生成
    └── plotly_visualize.py        # Plotly 汎用ユーティリティ
```

---

## アーキテクチャ

```text
入力ファイル群 ──→ io_models.py（検証・解決）
                        │
                        ▼
               report_analysis.py（オーケストレーター）
                 ┌──────┼──────────────┐
                 ▼      ▼              ▼
           analyzers.py            excel_reports.py
          (UND/CLOC/PMD/           (Excel 出力)
           Git/FileMetrics)
                 │
                 ▼
          metrics_merge.csv
                 │
                 ▼
       advanced_visualizations.py
       (config.yaml に基づき HTML 可視化を生成)
```
