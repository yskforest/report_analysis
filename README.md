# 新アーキテクチャ実行設計 (new_arch)

## 目的
本リポジトリは、`understand`（UND）、`cloc`、および `pmd` の解析を統合し、指定された入力ファイルから必要なメトリクスと可視化を生成する CLI ツールを提供します。CLI は **`run_report_analysis.sh`** を起点に `report_analysis.py` がオーケストレートし、各解析は `analyzers.py` 内の専用関数で実装されます。

## Quic Reference
```bash
bash src/run_report_analysis.sh sample_data/und_metrics.csv sample_data/cloc/cloc.csv "sample_data/pmd/*.xml" out analysis_code/
```

## Git 差分 Treemap 可視化
特定のタグまたはコミット ID から現在のコードまでの差分を集計し、コード総行数と変更行数を Treemap HTML と CSV で出力できます。

```bash
bash src/run_git_diff_treemap.sh {BASE_REF} out/git_diff
```

例:

```bash
# 指定コミットから HEAD までを集計
bash src/run_git_diff_treemap.sh abc1234 out/git_diff

# 指定タグから現在の作業ツリーまでを集計
bash src/run_git_diff_treemap.sh v1.0.0 out/git_diff --worktree

# analysis_code/Open3D のような別 Git ディレクトリを指定
bash src/run_git_diff_treemap.sh v1.0.0 out/open3d_git_diff --git-dir analysis_code/Open3D

# 対象 Git ディレクトリと拡張子を指定
bash src/run_git_diff_treemap.sh v1.0.0 out/open3d_git_diff --git-dir analysis_code/Open3D --extensions py,cpp,h

# 大規模リポジトリ向け: Treemap 階層を浅くして描画を軽量化
bash src/run_git_diff_treemap.sh v1.0.0 out/open3d_git_diff --git-dir analysis_code/Open3D --treemap-max-depth 5
```

主な出力:

- `git_diff_file_metrics.csv` – ファイル別の総行数、追加行数、削除行数、変更行数
- `git_diff_summary.csv` – 全体サマリ
- `code_total_lines_treemap.html` – コード総行数 Treemap（色: 変更率）
- `changed_lines_count_treemap.html` – 変更行数カラーマップ Treemap（色: 変更行数）
- `changed_lines_treemap.html` – 変更行数 Treemap（面積: 変更行数）
- `index.html` – 出力 HTML へのリンク集

大規模リポジトリでは進捗が標準エラーに表示されます。進捗表示間隔は `--progress-interval`、無効化は `--no-progress`、Treemap の描画負荷調整は `--treemap-max-depth` で指定できます。

詳細仕様は `doc/GIT_DIFF_TREEMAP_REQUIREMENTS.md` を参照してください。

## ディレクトリ構成
```
new_arch/
  run_report_analysis.sh          # CLI 入口（薄いスクリプト）
  run_git_diff_treemap.sh         # Git 差分 Treemap 可視化 CLI
  report_analysis.py              # オーケストレーター本体
  git_diff_treemap.py             # Git 差分集計・Treemap 生成
  analyzers.py                    # UND/CLOC/PMD の新規解析実装
  io_models.py                    # 入力解決・設定・結果モデル（dataclass）
  README.md                       # 実行方法・入出力説明
  RUN_REPORT_ANALYSIS_REQUIREMENTS.md   # 要求仕様書
  GIT_DIFF_TREEMAP_REQUIREMENTS.md      # Git 差分 Treemap 要求仕様書
  RUN_REPORT_ANALYSIS_DESIGN.md         # 実行設計書
```

## CLI インターフェース
### 実行形式
```bash
bash new_arch/run_report_analysis.sh \
  {UND_CSV|none} \
  {CLOC_CSV|none} \
  {PMD_XML_GLOB_OR_LIST|none} \
  {OUTPUT_DIR} \
  {REMOVE_PATH_PREFIX}
```
- **`UND_CSV`** – Understand 解析用 CSV ファイル（省略可）
- **`CLOC_CSV`** – CLOC 解析用 CSV ファイル（省略可）
- **`PMD_XML_GLOB_OR_LIST`** – PMD XML ファイルの glob 文字列または `,`/`:` 区切りリスト（省略可）
- **`OUTPUT_DIR`** – 処理結果を出力するディレクトリ（必須）
- **`REMOVE_PATH_PREFIX`** – 入力ファイルパスから一貫して除去するプレフィックス（省略可）

### 引数解釈
1. `UND_CSV|none` – 未指定または `none` は UND 解析をスキップ。
2. `CLOC_CSV|none` – 未指定または `none` は CLOC 解析をスキップ。
3. `PMD_XML_GLOB_OR_LIST|none` – 未指定または `none` は PMD 解析をスキップ。
4. `OUTPUT_DIR` – 出力ディレクトリが存在しない場合自動作成。
5. `REMOVE_PATH_PREFIX` – パスから一貫して除去される文字列。

### エラー/終了コード
- **`exit 1`** – 入力ファイルが未存在または全て無効な場合。
- **成功時** – `0` を返す。 

## 論理アーキテクチャ
```text
run_report_analysis.sh
  -> report_analysis.py
      -> io_models.resolve_inputs()
      -> analyzers.run_understand()   [if UND exists]
      -> analyzers.run_cloc()         [if CLOC exists]
      -> analyzers.run_pmd()          [if PMD list non‑empty]
      -> analyzers.write_global_summary()
```

## 解析詳細
### 6.1 前処理
1. 引数数チェック
2. `OUTPUT_DIR` 作成
3. UND/CLOC/PMD 入力解決（glob、パス正規化）
4. 全入力未指定または未存在なら `exit 1`

### 6.2 UND 解析（新規実装）
- **入力**: `UND_CSV`（1ファイル）
- **処理**:
  - CSV 読込、`File`/`LongName` 正規化、`REMOVE_PATH_PREFIX` 削除
  - `Kind` に基づく `File/Function/Class` 分割
  - 集計サマリ作成
  - treemap HTML 生成
- **出力先**: `OUTPUT_DIR/und/`, `OUTPUT_DIR/und_summary.csv`

### 6.3 CLOC 解析（新規実装）
- **入力**: `CLOC_CSV`（1ファイル）
- **処理**:
  - 必須列検証 (`language, filename, blank, comment, code`) 
  - `SUM` 行除外、ファイルパス正規化
  - 言語別 pie chart 生成
  - サマリ作成
- **出力先**: `OUTPUT_DIR/cloc/`, `OUTPUT_DIR/summary_cloc.csv`

### 6.4 PMD 解析（新規実装）
- **入力**: `PMD_XML_GLOB_OR_LIST`（複数可）
- **処理**:
  - XML ファイル解析、クローン比率計算
- **出力先**: `OUTPUT_DIR/pmd/`, 各種 CSV / HTML

### 6.5 統合サマリ
`analyzers.write_global_summary()` により各タスクの成功・失敗をまとめた `summary_report.csv` を生成。

## 拡張性設計
- 新規解析は `analyzers.py` に `run_<name>()` を1関数追加し、`report_analysis.py` の実行リストへ1行追加する。
- 入力種別追加は `io_models.py` の解決ロジックに追記する。

## テスト設計（最小）
- 単体:
  - 入力解決（none/未存在/glob/複数XML）
  - PMD XML 解析（複製トークン算出）
- 結合:
  - UND のみ、CLOC のみ、PMD のみ（複数XML）、UND+CLOC+PMD、一部未存在、全未存在（exit 1）

## 必要ライブラリ
- `pandas`
- `plotly`
- 標準ライブラリ (`os`, `sys`, `pathlib`, `csv`, `json`, …)

## 実行例
```bash
bash new_arch/run_report_analysis.sh \
  sample_data/und_metrics.csv \
  sample_data/cloc/cloc.csv \
  "sample_data/pmd/*.xml" \
  out \
  /home/korver/code/hc_new_arch
```
このコマンドは `out` ディレクトリに以下のファイルを生成します：
- `und/` – Understand 解析結果
- `cloc/` – CLOC 解析結果
- `pmd/` – PMD 解析結果
- `summary_report.csv` – 全タスクサマリ

**以上が本リポジトリの解析内容です。** ご不明な点や追加要件については、`RUN_REPORT_ANALYSIS_REQUIREMENTS.md` を参照してください。
