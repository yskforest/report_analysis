# 新アーキテクチャ実行設計: report analysis

## 1. 目的

本設計書は、[requirements.md](file:///home/korver/code/hc_new_arch/docs/requirements.md) を実現するための実行設計を定義する。  
本設計では **既存 `scripts/*` のコードを利用しない** ことを前提とし、`new_arch` 配下のみで完結する新規実装とする。

優先順位は以下とする。

1. 拡張性
2. 可読性
3. コード行数の少なさ

## 2. 設計方針

- UND/CLOC/PMD は同一オーケストレーターから呼び出し、部分実行を標準動作にする。
- 既存スクリプトの呼び出し・import は行わない。
- 分割粒度は「理解コスト削減」と「将来追加容易性」のバランスで決める。

## 3. ディレクトリ/ファイル構成

```text
src/
  report_analysis.py              # オーケストレーター本体
  analyzers.py                    # UND/CLOC/PMD の新規解析実装
  io_models.py                    # 入力解決・設定・結果モデル（dataclass）
  advanced_visualizations.py      # 可視化ロジック
docs/
  requirements.md
  design.md
README.md                         # 実行方法・入出力説明 (プロジェクトルート)
```

## 4. CLI インターフェース設計

## 4.1 実行形式

```bash
python3 src/report_analysis.py \
  [--config config.yaml] \
  {UND_CSV|none} \
  {CLOC_CSV|none} \
  {PMD_XML_GLOB_OR_LIST|none} \
  {GIT_NUMSTAT|none} \
  {OUTPUT_DIR} \
  {REMOVE_PATH_PREFIX}
```

## 4.2 引数解釈

1. `config.yaml`（オプション）
2. `UND_CSV|none`
3. `CLOC_CSV|none`
4. `PMD_XML_GLOB_OR_LIST|none`
5. `GIT_NUMSTAT|none`
6. `OUTPUT_DIR`
7. `REMOVE_PATH_PREFIX`

- `none` / `false` / `-` は未指定扱い。
- `PMD_XML_GLOB_OR_LIST` は以下を許容:
  - glob 文字列（例: `sample_data/pmd/*.xml`）
  - 区切りリスト（`,` or `:`）
- パス解決後に実在ファイルのみ有効入力として扱う。
- `--config` が指定されている場合、`config.yaml` の構文チェックを行い、`visualizations` のリストを読み込む。

## 5. 論理アーキテクチャ

```text
report_analysis.py
  -> io_models.resolve_inputs()          [--config 指定時は config.yaml もパース]
  -> analyzers.run_understand()          [if UND exists]
  -> analyzers.run_cloc()                [if CLOC exists]
  -> analyzers.run_pmd()                 [if PMD list non-empty]
  -> analyzers.run_git_numstat()         [if GIT_NUMSTAT exists]
  -> analyzers.run_comprehensive_merge() [if files resolved]
  -> advanced_visualizations.run_advanced_visualizations() [config またはデフォルト可視化の実行]
  -> analyzers.write_global_summary()
```

## 5.1 UML: コンポーネント図

```mermaid
flowchart LR
    User[User/CI] --> RA[report_analysis.py]

    RA --> IO[io_models.py]
    RA --> AN[analyzers.py]
    RA --> AV[advanced_visualizations.py]
    RA --> SUM[summary_report.csv]

    IO --> IN1[(UND CSV)]
    IO --> IN2[(CLOC CSV)]
    IO --> IN3[(PMD XML xN)]
    IO --> IN4[(Git Numstat TSV)]
    IO --> CONF[(config.yaml)]

    AN --> O1[(output_dir/und)]
    AN --> O2[(output_dir/cloc)]
    AN --> O3[(output_dir/pmd)]
    AN --> O4[(output_dir/git)]
    AN --> O5[(output_dir/metrics_merge.csv)]
    AV --> O6[(output_dir/visualizations またはカスタム出力先)]
```

## 5.2 コアデータモデル

`io_models.py` で以下の dataclass を定義する。

- `AnalysisInputs`
  - `und_csv: Optional[Path]`
  - `cloc_csv: Optional[Path]`
  - `pmd_xmls: list[Path]`
  - `git_numstat: Optional[Path]`
  - `output_dir: Path`
  - `remove_path_prefix: str`
  - `config_path: Optional[Path]`
  - `visualizations: list[dict]`
  - `warnings: list[str]`（未存在入力など）

- `TaskResult`
  - `name: str`（`und` / `cloc` / `pmd` / `git` / `visualize` など）
  - `executed: bool`
  - `success: bool`
  - `outputs: list[Path]`
  - `message: str`

## 5.3 UML: クラス図

```mermaid
classDiagram
    class AnalysisInputs {
      +Path|None und_csv
      +Path|None cloc_csv
      +list~Path~ pmd_xmls
      +Path output_dir
      +str remove_path_prefix
      +list~str~ warnings
    }

    class TaskResult {
      +str name
      +bool executed
      +bool success
      +list~Path~ outputs
      +list~dict~ summary_rows
      +str message
    }

    class ReportAnalysis {
      +main(argv) int
    }

    class IOModels {
      +resolve_inputs(...)
      +_resolve_optional_file(...)
      +_resolve_pmd_files(...)
    }

    class Analyzers {
      +run_understand(inputs) TaskResult
      +run_cloc(inputs) TaskResult
      +run_pmd(inputs) TaskResult
      +run_file_metrics_excel(inputs) TaskResult
      +write_global_summary(inputs, results) Path
    }

    class AdvancedVisualizations {
      +run_advanced_visualizations(inputs) TaskResult
    }

    ReportAnalysis --> IOModels : uses
    ReportAnalysis --> Analyzers : orchestrates
    ReportAnalysis --> AdvancedVisualizations : orchestrates
    IOModels --> AnalysisInputs : creates
    Analyzers --> TaskResult : returns
    AdvancedVisualizations --> TaskResult : returns
```

## 6. 処理シーケンス設計

## 6.1 前処理

1. 引数数チェック
2. `OUTPUT_DIR` 作成
3. UND/CLOC/PMD/Git Numstat 入力解決
4. 全入力未指定または未存在なら `exit 1`

## 6.1.1 UML: メインシーケンス図

```mermaid
sequenceDiagram
    participant U as User
    participant RA as report_analysis.py
    participant IO as io_models.py
    participant AN as analyzers.py
    participant AV as advanced_visualizations.py

    U->>RA: python report_analysis.py ...
    RA->>IO: resolve_inputs(...)
    IO-->>RA: AnalysisInputs(warnings含む)
    RA->>RA: output_dir作成 / warning出力

    alt 有効入力が0件
      RA-->>U: exit 1
    else 有効入力あり
      RA->>AN: run_understand(inputs)
      AN-->>RA: TaskResult(und)
      RA->>AN: run_cloc(inputs)
      AN-->>RA: TaskResult(cloc)
      RA->>AN: run_pmd(inputs)
      AN-->>RA: TaskResult(pmd)
      RA->>AN: run_git_numstat(inputs)
      AN-->>RA: TaskResult(git)
      RA->>AN: run_file_metrics_excel(inputs)
      AN-->>RA: TaskResult(file_metrics_excel)
      RA->>AN: run_comprehensive_merge(inputs)
      AN-->>RA: TaskResult(comprehensive_merge)
      RA->>AV: run_advanced_visualizations(inputs)
      AV-->>RA: TaskResult(visualize)
      RA->>AN: write_global_summary(inputs, results)
      AN-->>RA: summary_report.csv
      RA-->>U: exit 0 or exit 1
    end
```

## 6.2 UND 解析（新規実装）

- 入力: UND CSV（1ファイル）
- 処理:
  - CSV読込
  - `File` / `LongName` の区切り文字正規化（`\\` -> `/`）
  - `REMOVE_PATH_PREFIX` の除去
  - `Kind` に基づく `File/Function/Class` 分割
  - 集計サマリ作成
  - treemap HTML 作成
- 出力先:
  - `OUTPUT_DIR/und/`
  - `OUTPUT_DIR/und/`
  - `OUTPUT_DIR/und_summary.csv`

## 6.3 CLOC 解析（新規実装）

- 入力: CLOC CSV（1ファイル）
- 処理:
  - 必須列検証（`language, filename, blank, comment, code`）
  - `SUM` 行除外
  - ファイルパス正規化
  - 言語別 pie chart 生成
  - サマリ作成
- 出力先:
  - `OUTPUT_DIR/cloc/`
  - `OUTPUT_DIR/summary_cloc.csv`

## 6.4 PMD 解析（新規実装）

- 入力: PMD XML（複数）
- 処理:
  - XMLを `xml.etree.ElementTree` で解析
  - `file` / `duplication` 情報からファイルごとの clone token を算出
  - 複数XMLを統合集計
  - clone ratio CSV / summary CSV / treemap 生成
  - UND入力がある場合は UND/PMD マージCSVと summary作成
- 出力先:
  - `OUTPUT_DIR/pmd/`
  - `OUTPUT_DIR/und_pmd_merge.csv`（条件付き）
  - `OUTPUT_DIR/pmd_summary.csv`（条件付き）

## 6.5 Git Numstat 解析（新規実装）

- 入力: Raw `git diff --numstat` テキスト/TSV（1ファイル）
- 処理:
  - テキストファイルを行単位でパース（スペース/タブ区切り）
  - 各行から `AddedLines`, `DeletedLines`, `File` を抽出（バイナリファイルなどの `-` は `0` とみなす）
  - パスを `clean_path` で正規化
  - 同一ファイル名の重複があれば行数を合算（groupby & sum）
  - `ChangedLines` = `AddedLines` + `DeletedLines` を算出
  - 変更行数別CSV / summary CSV生成
- 出力先:
  - `OUTPUT_DIR/git/git_diff_file_metrics.csv`
  - `OUTPUT_DIR/git/git_diff_summary.csv`

## 6.6 総合マージ（新規実装）

- 入力: 存在する全ての中間成果物（und/cloc/pmd/git）
- 処理:
  - 各CSVのジョイン列を `File` に統一（CLOC は `filename` からリネーム）
  - 各CSVのカラム名（`File` 以外）にツール別のプレフィックス（`und_`, `cloc_`, `pmd_`, `git_`）を付与
  - `File` 列に対して外部結合（Outer Join）を施し、単一の結合表を生成
- 出力先:
  - `OUTPUT_DIR/metrics_merge.csv`

## 6.7 統合サマリ

- タスク実行結果を `summary_report.csv` として `OUTPUT_DIR` 直下に保存する。

## 6.8 UML: アクティビティ図（終了コード判定）

```mermaid
flowchart TD
    A([Start]) --> B{引数数は6か}
    B -- No --> X1[usage出力] --> Z1([Exit 1])
    B -- Yes --> C[resolve_inputs]
    C --> D{und/cloc/pmd/git すべて無効か}
    D -- Yes --> X2[no valid inputs] --> Z2([Exit 1])
    D -- No --> E[run_understand]
    E --> F[run_cloc]
    F --> G[run_pmd]
    G --> H[run_git_numstat]
    H --> I[run_file_metrics_excel]
    I --> J[run_func_metrics_excel]
    J --> K[run_comprehensive_merge]
    K --> L[run_advanced_visualizations]
    L --> M[write_global_summary]
    M --> N{executedタスクが全失敗か}
    N -- Yes --> Z3([Exit 1])
    N -- No --> Z4([Exit 0])
```

## 6.9 UML: 出力マッピング図

```mermaid
flowchart LR
    U[run_understand] --> U1[output_dir/und/und_metrics.csv]
    U --> U2[output_dir/und/und_file.csv]
    U --> U3[output_dir/und/und_func.csv]
    U --> U4[output_dir/und/und_class.csv]
    U --> U5[output_dir/und/*.html]
    U --> U6[output_dir/und_summary.csv]

    C[run_cloc] --> C1[output_dir/cloc/cloc_filtered.csv]
    C --> C2[output_dir/cloc/cloc_pie_chart.html]
    C --> C3[output_dir/summary_cloc.csv]

    P[run_pmd] --> P1[output_dir/pmd/pmd_clone_ratio.csv]
    P --> P2[output_dir/pmd/pmd_clone_ratio_summary.csv]
    P --> P3[output_dir/pmd/*.html]
    P --> P4[output_dir/und_pmd_merge.csv]
    P --> P5[output_dir/pmd_summary.csv]

    G[run_git_numstat] --> G1[output_dir/git/git_diff_file_metrics.csv]
    G --> G2[output_dir/git/git_diff_summary.csv]

    M[run_comprehensive_merge] --> M1[output_dir/metrics_merge.csv]
```

## 7. エラー/終了コード設計

- `exit 0`: 1つ以上の解析が実行され、全実行タスクが失敗でない
- `exit 1`: 以下のいずれか
  - 引数不正
  - 入力がすべて無効
  - 実行対象タスクがすべて失敗

## 8. ログ設計

- ログ形式:
  - `[INFO]`
  - `[WARN]`
  - `[ERROR]`
- 必須ログ:
  - 入力解決結果
  - スキップ理由（未指定/未存在）
  - タスクごとの結果
  - summary出力先

## 9. 拡張性設計

- 新規解析追加は `analyzers.py` に `run_<name>()` を1関数追加し、`report_analysis.py` の実行リストへ1行追加する。
- 入力種別追加は `io_models.py` の解決ロジックに追記する。

## 10. 可読性/コード量最適化指針

- 早期 return と dataclass 利用で分岐を平坦化する。
- 文字列連結より `Path` と DataFrame 操作を優先する。
- パス正規化ロジックを共通化して重複を削減する。
- 4ファイル構成を維持し、過分割を避ける。

## 11. テスト設計（最小）

- 単体:
  - 入力解決（none/未存在/glob/複数XML）
  - PMD XML解析（複製トークン算出）
- 結合:
  - UNDのみ
  - CLOCのみ
  - PMDのみ（複数XML）
  - UND+CLOC+PMD
  - 一部未存在
  - 全未存在（exit 1）

## 12. 実装制約

- `new_arch` は `scripts/*` に依存しない単独実装とする。
- 必要ライブラリは `pandas` / `plotly` / 標準ライブラリを使用する。
