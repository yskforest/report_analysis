# 要求仕様書

本リポジトリで実装するコード解析・可視化ツール群の要求を定義する。

## 1. 概要

### 1.1 本ツールが解決する課題

ソフトウェアプロジェクトのコード品質を定量評価するには、複数の解析ツール（Understand / cloc / PMD / Git diff）を個別に実行し、結果を手作業で突合する必要がある。本ツール群はこれを自動化し、統合された可視化・レポートを提供する。

### 1.2 システム構成

本リポジトリは以下の2つのエントリポイントを持つ。

| エントリポイント | 役割 |
|---|---|
| `report_analysis.py` | 各ツールの出力（CSV/XML）を入力として受け取り、解析・可視化・統合レポートを生成する |
| `run_git_diff_treemap.sh` | Git リポジトリに対して直接差分を収集し、コード量と変更量の Treemap を生成する |

### 1.3 スコープ

**対象:**
- UND / CLOC / PMD / Git 差分の解析と可視化
- 部分実行（存在する入力のみで処理を継続）
- 統合レポート（全ツール結果のマージ）
- Git リポジトリの差分 Treemap 可視化

**非対象:**
- 解析アルゴリズムそのものの精度改善
- 既存 `scripts/` ロジックの全面書き換え
- Git 未追跡ファイルの差分集計
- バイナリファイルの行数集計

### 1.4 用語定義

| 用語 | 定義 |
|---|---|
| UND | SciTools Understand の CSV エクスポート |
| CLOC | `cloc --csv` の出力 CSV |
| PMD | PMD CPD の XML レポート（複数可） |
| Git Numstat | `git diff --numstat` 形式のテキスト入力 |
| OUTPUT_DIR | 全成果物の出力ルート |
| REMOVE_PATH_PREFIX | パス正規化用プレフィックス |
| Base Ref | Git 比較元（タグ名 / ブランチ名 / コミット ID） |
| Target Ref | Git 比較先（既定: `HEAD`） |

---

## 2. ユースケース

### UC-01: 全ツール統合解析

- **アクター:** 開発者 / CI
- **事前条件:** UND CSV、CLOC CSV、PMD XML、Git Numstat がすべて存在する
- **正常フロー:**
  1. 全入力パスを指定して `report_analysis.py` を実行
  2. UND → CLOC → PMD → Git の順に解析を実行
  3. 全ツール結果を `File` 列で結合した `metrics_merge.csv` を生成
  4. `summary_report.csv` を出力し、終了コード `0` で終了
- **事後条件:** `OUTPUT_DIR` 配下に各ツールの成果物と統合レポートが配置される

### UC-02: 部分入力による解析

- **アクター:** 開発者 / CI
- **事前条件:** 一部の入力のみ存在する（例: UND と CLOC のみ）
- **正常フロー:**
  1. 存在しない入力に `none` を指定して実行
  2. 未存在入力ごとに警告ログを出力
  3. 存在する入力のみで解析を実行
  4. 生成可能な成果物のみ出力し、終了コード `0` で終了
- **例外フロー:**
  - すべての入力が未存在 → stderr にエラー出力し、終了コード `1`
- **事後条件:** 存在した入力に対応する成果物のみが配置される

### UC-03: Git 差分 Treemap 生成

- **アクター:** 開発者 / CI
- **事前条件:** 対象が Git リポジトリであり、Base Ref が解決可能
- **正常フロー:**
  1. Base Ref と OUTPUT_DIR を指定して `run_git_diff_treemap.sh` を実行
  2. Git diff から追加行数・削除行数を収集
  3. 比較先のファイルごとにコード総行数をカウント
  4. ファイル別 CSV、サマリ CSV、Treemap HTML を出力
  5. `index.html` から各成果物へ遷移可能にする
- **代替フロー:**
  - `--worktree` 指定時 → 比較先を作業ツリーに切り替え
  - `--target-ref` 指定時 → 比較先を指定 ref に変更
  - `--repo` / `--git-dir` 指定時 → 対象リポジトリを変更
- **例外フロー:**
  - Git リポジトリでない → 終了コード `1`
  - Base Ref / Target Ref が解決不可 → 終了コード `1`
- **事後条件:** `OUTPUT_DIR` に CSV と Treemap HTML が配置される

### UC-04: 変更規模の大きいファイルの特定

- **アクター:** 開発者
- **事前条件:** UC-01 または UC-03 が完了済み
- **正常フロー:**
  1. 出力された CSV（`git_diff_file_metrics.csv` や `metrics_merge.csv`）を開く
  2. 変更行数や複雑度でソートし、注目すべきファイルを特定する
  3. Treemap HTML でディレクトリ階層ごとの全体像を俯瞰する

---

## 3. 機能要求

### 3.1 CLI

#### report_analysis.py

- **[FR-CLI-01]** 以下の形式で実行できること。
  ```bash
  python3 src/report_analysis.py \
    {UND_CSV|none} {CLOC_CSV|none} {PMD_XML_GLOB_OR_LIST|none} \
    {GIT_NUMSTAT|none} {OUTPUT_DIR} {REMOVE_PATH_PREFIX}
  ```
- **[FR-CLI-02]** `none` / `false` / `-` を未指定として扱うこと。
- **[FR-CLI-03]** PMD 引数は glob（例: `data/pmd/*.xml`）および区切りリスト（`,` or `:`）に対応すること。
- **[FR-CLI-04]** 引数数不正時は usage を表示して終了コード `1` で終了すること。
- **[FR-CLI-05]** すべての入力が未指定または未存在の場合は終了コード `1` で終了すること。

#### run_git_diff_treemap.sh

- **[FR-CLI-06]** 以下の形式で実行できること。
  ```bash
  bash src/run_git_diff_treemap.sh {BASE_REF} {OUTPUT_DIR} [OPTIONS]
  ```
- **[FR-CLI-07]** 比較先は既定で `HEAD` とし、`--target-ref` で変更できること。
- **[FR-CLI-08]** `--worktree` で比較先を作業ツリーに切り替えられること。
- **[FR-CLI-09]** `--repo` / `--git-dir` で対象リポジトリを指定できること。
- **[FR-CLI-10]** `--extensions` で集計対象拡張子を制御できること。`all` 指定時は拡張子フィルタを無効化すること。
- **[FR-CLI-11]** `--exclude` で除外 glob を追加指定できること。
- **[FR-CLI-12]** `--treemap-max-depth` で Treemap の最大階層深さを指定できること。
- **[FR-CLI-13]** `--no-progress` で進捗表示を無効化できること。`--progress-interval` で進捗表示間隔を指定できること。

### 3.2 Understand 解析

- **[FR-UND-01]** UND CSV が存在する場合に実行すること。未存在時はスキップ。
- **[FR-UND-02]** Windows 形式パス区切り（`\`）・Linux 形式パス区切り（`/`）の両方を受け付け、出力時は `/` に統一すること。
- **[FR-UND-03]** metrics 整形結果を `und_metrics.csv` として出力すること。
- **[FR-UND-04]** `Kind` に基づきファイル / 関数 / クラス別の CSV を出力すること。
- **[FR-UND-05]** `REMOVE_PATH_PREFIX` を適用してパスを正規化すること。
- **[FR-UND-06]** 以下の Treemap 可視化を HTML で出力すること。
  - `CountLineCode(Area)-Essential(FileAverage)_treemap.html`
  - `CountLineCode(Area)-Cyclomatic(FileAverage)_treemap.html`

### 3.3 CLOC 解析

- **[FR-CLOC-01]** CLOC CSV が存在する場合に実行すること。未存在時はスキップ。
- **[FR-CLOC-02]** 必須列（`language`, `filename`, `blank`, `comment`, `code`）を検証し、`SUM` 行を除外すること。
- **[FR-CLOC-03]** 言語別 pie chart を HTML で出力すること。
- **[FR-CLOC-04]** フィルタ済み CSV とサマリ CSV を出力すること。

### 3.4 PMD 解析

- **[FR-PMD-01]** PMD XML が1件以上存在する場合に実行すること。未存在時はスキップ。
- **[FR-PMD-02]** 複数 XML を統合解析できること。
- **[FR-PMD-03]** ファイルごとの clone ratio CSV、サマリ CSV、Treemap HTML を出力すること。
- **[FR-PMD-04]** UND 結果が存在する場合のみ、UND/PMD マージ情報を生成すること。

### 3.5 Git 差分解析

#### report_analysis 経由（Numstat 入力）

- **[FR-GIT-01]** `git diff --numstat` 形式のテキストをパースし、ファイルごとの追加行数・削除行数・変更行数を CSV 出力すること。
- **[FR-GIT-02]** バイナリファイル（`-` 表記）は行数 `0` として扱うこと。
- **[FR-GIT-03]** `REMOVE_PATH_PREFIX` を適用してパスを正規化すること。同一ファイルの重複行は合算すること。

#### run_git_diff_treemap 経由（直接収集）

- **[FR-GIT-04]** Git diff の `numstat` 情報から追加行数・削除行数を取得すること。変更行数は `追加 + 削除` で算出。
- **[FR-GIT-05]** リネームされたファイルは比較先パスを代表パスとして扱うこと。
- **[FR-GIT-06]** 比較先が Git ref の場合、Git blob を一括読み出しして行数集計すること（ファイルごとのプロセス起動を避ける）。
- **[FR-GIT-07]** NUL バイトを含むファイルはバイナリとみなし総行数を `0` とすること。
- **[FR-GIT-08]** 処理段階（ファイル一覧取得 → 差分取得 → 行数カウント → 出力）をログ表示すること。行数カウント中は処理済み/総数/経過秒を表示すること。

### 3.6 可視化（Git Treemap）

- **[FR-VIS-01]** `code_total_lines_treemap.html`: コード総行数を面積、変更率を色として表示すること。
- **[FR-VIS-02]** `changed_lines_count_treemap.html`: コード総行数を面積、変更行数を色として表示すること。
- **[FR-VIS-03]** `changed_lines_treemap.html`: 変更行数を面積として表示すること。
- **[FR-VIS-04]** Treemap はディレクトリ階層とファイル階層を表現すること。
- **[FR-VIS-05]** `index.html` から各成果物へ遷移できること。
- **[FR-VIS-06]** `--treemap-max-depth` 指定時、指定階層でデータを集約して描画負荷を抑制すること。

### 3.7 統合処理

- **[FR-MERGE-01]** 存在する全ツールの結果 CSV を `File` 列で外部結合（Outer Join）し、`metrics_merge.csv` を生成すること。各列にはツール別プレフィックス（`und_`, `cloc_`, `pmd_`, `git_`）を付与すること。
- **[FR-MERGE-02]** 全タスクの実行結果を `summary_report.csv` として `OUTPUT_DIR` 直下に出力すること。

### 3.8 部分実行

- **[FR-PART-01]** UND / CLOC / PMD / Git のいずれかが未指定・未存在でも、存在する入力のみで処理を実行すること。
- **[FR-PART-02]** 未存在入力は警告ログとして記録し、他処理は継続すること。
- **[FR-PART-03]** すべての入力が未存在の場合のみ異常終了とすること。

---

## 4. 入出力仕様

### 4.1 入力

| 入力 | 形式 | 必須列 / フォーマット |
|---|---|---|
| UND CSV | CSV（1ファイル） | `Kind`, `File`, `CountLineCode` 等 |
| CLOC CSV | CSV（1ファイル） | `language`, `filename`, `blank`, `comment`, `code` |
| PMD XML | XML（1件以上） | `<duplication>` 要素を含む PMD CPD 出力 |
| Git Numstat | TSV（1ファイル） | `<added>\t<deleted>\t<file_path>` |
| Git リポジトリ | ディレクトリ | `.git` を持つ有効なリポジトリ |

### 4.2 出力（report_analysis）

| 出力先 | 主要成果物 |
|---|---|
| `OUTPUT_DIR/und/` | `und_metrics.csv`, `und_file.csv`, `und_func.csv`, `und_class.csv`, `*_treemap.html` |
| `OUTPUT_DIR/cloc/` | `cloc_filtered.csv`, `cloc_pie_chart.html` |
| `OUTPUT_DIR/pmd/` | `pmd_clone_ratio.csv`, `pmd_clone_ratio_summary.csv`, `*_treemap.html` |
| `OUTPUT_DIR/git/` | `git_diff_file_metrics.csv`, `git_diff_summary.csv` |
| `OUTPUT_DIR/` | `summary_report.csv`, `metrics_merge.csv` |

### 4.3 出力（git_diff_treemap）

| 出力先 | 主要成果物 |
|---|---|
| `OUTPUT_DIR/` | `git_diff_file_metrics.csv`（列: `File`, `TotalLines`, `AddedLines`, `DeletedLines`, `ChangedLines`, `ChangeRatio`） |
| `OUTPUT_DIR/` | `git_diff_summary.csv`（比較元/先, ファイル数, 変更ファイル数, 各行数合計） |
| `OUTPUT_DIR/` | `code_total_lines_treemap.html`, `changed_lines_count_treemap.html`, `changed_lines_treemap.html`, `index.html` |

---

## 5. エラー処理

### 5.1 終了コード

| コード | 条件 |
|---|---|
| `0` | 1つ以上の解析が実行され、全実行タスクが失敗でない |
| `1` | 引数不正 / 全入力が無効 / 全タスク失敗 / Git ref 解決不可 |

### 5.2 ログ

- スキップ理由（入力ごとの未指定・未存在）を `[WARN]` で出力すること。
- 異常理由は `[ERROR]` で stderr に出力すること。
- 各タスクの実行結果を `[INFO]` で出力すること。

---

## 6. 非機能要求

- **[NFR-01]** 冪等性: 同一入力・同一出力先で再実行した場合、同一の結果を生成すること。
- **[NFR-02]** 保守性: エントリポイントは薄く保ち、処理責務をタスク層へ分離すること。新規解析の追加は関数1つとオーケストレーター1行の変更で完了できること。
- **[NFR-03]** 可観測性: 実行された処理・スキップされた処理がログで判別できること。
- **[NFR-04]** 互換性: Python 3.9+、pandas、plotly、Git CLI で動作すること。

---

## 7. 受け入れ基準

| ID | 基準 | 検証方法 |
|---|---|---|
| AC-01 | Windows 形式パス（`\`）の UND CSV を入力すると、出力 CSV のパスが `/` 区切りに統一されている | 出力 CSV に `\` が含まれないことを確認 |
| AC-02 | CLOC CSV を入力すると `OUTPUT_DIR/cloc/` に pie chart HTML と CSV が生成される | ファイル存在確認 |
| AC-03 | 複数 PMD XML を入力すると、統合された clone ratio CSV が生成される | 出力行数が全 XML の合計を反映 |
| AC-04 | 一部入力が未存在でも、存在する入力のみで終了コード `0` で完了する | UND のみ指定で実行し正常終了を確認 |
| AC-05 | 全入力が未存在の場合、終了コード `1` を返す | 全引数に `none` を指定 |
| AC-06 | `metrics_merge.csv` が存在するツール結果を `File` 列で結合している | 列名にプレフィックスが付与されていることを確認 |
| AC-07 | `run_git_diff_treemap.sh` にタグを指定して正常終了し、CSV と Treemap HTML が出力される | ファイル存在確認 |
| AC-08 | `--worktree` 指定時に作業ツリーを比較先として差分を集計する | unstaged 変更が結果に反映されることを確認 |
| AC-09 | Base Ref が不正な場合、終了コード `1` でエラー理由を出力する | 存在しないタグを指定 |

---

## 8. 制約

- 既存成果物のパス互換を可能な範囲で維持し、下流連携影響を最小化すること。
- 既存 `scripts/*` に依存しない新規実装とすること。
