# 新アーキテクチャ要求仕様書: run_report_analysis 相当処理

## 1. 目的

本仕様書は、`new_arch` 配下に実装する「`scripts/run_report_analysis.sh` と README 相当の処理仕様」を定義する。  
対象は `understand` / `cloc` / `pmd` の解析処理であり、指定された入力のうち存在するものだけで実行し、成果物を規定ディレクトリへ出力することを要求する。

## 2. スコープ

### 2.1 対象

- レポート解析のエントリポイント（CLI）
- 実行順序制御（オーケストレーション）
- Understand 解析（Win/Linux 出力CSVの両対応）
- CLOC 解析（CSV入力）
- PMD 解析（複数XML入力）
- 出力物配置（`und` / `cloc` / `pmd` と `OUTPUT_DIR` 直下）
- エラー処理・終了コード
- README 相当の利用説明（実行方法、前提、成果物）

### 2.2 非対象

- 解析アルゴリズムそのものの精度改善
- 既存 `scripts/understand/analysis/` ロジックの全面書き換え

## 3. 用語定義

- UND: Understand レポート入力（CSV）
- CLOC: cloc の集計CSV入力
- PMD: PMD CPD レポート入力（XML、複数可）
- OUTPUT_DIR: 全成果物の出力ルート
- REMOVE_PATH_PREFIX: 可視化・集計時のパス正規化用プレフィックス
- 任意入力: 入力されてもファイル未存在の場合はスキップ対象となる入力

## 4. ユースケース

1. UND / CLOC / PMD の全入力を指定して解析を実行する。
2. UND と CLOC のみ指定して解析を実行する。
3. PMD（複数XML）のみ指定して解析を実行する。
4. 指定入力の一部が未存在でも、存在する入力だけで処理を継続する。

## 5. 機能要求

### 5.1 CLI 要求

- 実行形式は以下を満たすこと。

```bash
run_report_analysis \
  {UND_CSV|none} \
  {CLOC_CSV|none} \
  {PMD_XML_GLOB_OR_LIST|none} \
  {OUTPUT_DIR} \
  {REMOVE_PATH_PREFIX}
```

- `PMD_XML_GLOB_OR_LIST` は複数の XML を解決できる入力形式（glob または区切りリスト）に対応すること。
- 引数数不正時は usage を表示して異常終了すること。
- すべての入力が未指定または未存在の場合は異常終了すること。

### 5.2 実行順序要求

以下の順序で処理を実行すること。

1. 引数バリデーション
2. 入力解決（UND/CLOC/PMD の存在確認、PMD は複数展開）
3. Understand 処理（入力存在時）
4. CLOC 処理（入力存在時）
5. PMD 処理（入力存在時）
6. 統合サマリ・複合情報出力（生成可能な場合）

### 5.3 Understand 処理要求

- UND CSV が存在する場合に実行すること。
- UND 入力は、Windows 形式パス区切り・Linux 形式パス区切りのどちらで出力された CSV でも受け付けること。
- 最低限、以下を満たすこと。
  - metrics 整形（`und_metrics.csv`）
  - サマリ出力
  - 必要時のパス正規化
  - treemap 等の可視化出力
- ツリーマップ可視化は、少なくとも以下形式を追加サポートすること。
  - `CountLineCode(Area)-Essential(FileAverage)`（カウントラインコードー本質的複雑度（ファイル平均））
  - `CountLineCode(Area)-Cyclomatic(FileAverage)`（カウントラインコードー循環的複雑度（ファイル平均））

### 5.4 CLOC 処理要求

- CLOC CSV が存在する場合に実行すること。
- 最低限、以下を満たすこと。
  - CLOC 集計可視化（pie chart 等）
  - CLOC サマリ出力
- CLOC 入力未存在時はスキップし、異常終了しないこと。

### 5.5 PMD 処理要求

- PMD XML が1件以上解決できた場合に実行すること。
- 複数XMLを入力として統合解析できること。
- 最低限、以下を満たすこと。
  - clone ratio 集計 CSV 生成
  - summary CSV 生成
  - treemap 可視化生成
- UND 結果が存在する場合のみ UND/PMD 複合情報を生成すること。

### 5.6 部分実行要求（重要）

- UND/CLOC/PMD のいずれかが未指定または未存在でも、存在する入力のみで処理を実行すること。
- 未存在入力は警告ログとして記録し、他処理は継続すること。
- すべて未存在の場合のみ異常終了とすること。

### 5.7 README 相当要求

新アーキテクチャ実装には README 相当として以下情報を必須記載すること。

- 実行コマンド
- 引数説明（UND/CLOC/PMD の任意性、PMD 複数指定方法）
- 前提条件（依存ツール・入力ファイル）
- 典型実行例（全入力、UNDのみ、PMDのみ、欠損入力あり）
- 出力先と主要成果物
- 異常終了条件と対処

## 6. 入出力要求

### 6.1 入力要求

- UND: 1ファイルのCSV入力（Win/Linux 形式双方対応）
- CLOC: 1ファイルのCSV入力
- PMD: 1件以上のXML入力（複数可）
- OUTPUT_DIR: 未存在の場合は作成可能であること。

### 6.2 出力要求

出力は以下のルールに従うこと。

- UND成果物は `OUTPUT_DIR/und/` に配置
- CLOC成果物は `OUTPUT_DIR/cloc/` に配置
- PMD成果物は `OUTPUT_DIR/pmd/` に配置
- summary や UND/PMD などの複合情報は `OUTPUT_DIR` 直下に配置

最低限の代表成果物例:

- `OUTPUT_DIR/und/und_metrics.csv`
- `OUTPUT_DIR/und/` 配下の可視化成果物
- `OUTPUT_DIR/und_python_plot/CountLineCode(Area)-Essential(FileAverage)_treemap.html`
- `OUTPUT_DIR/und_python_plot/CountLineCode(Area)-Cyclomatic(FileAverage)_treemap.html`
- `OUTPUT_DIR/cloc/cloc_pie_chart.html`
- `OUTPUT_DIR/pmd/pmd_clone_ratio.csv`
- `OUTPUT_DIR/pmd/pmd_clone_ratio_summary.csv`
- `OUTPUT_DIR/summary*.csv`（総合サマリ）
- `OUTPUT_DIR/*merge*.csv`（複合情報、生成条件付き）

## 7. エラー処理要求

- 終了コード:
  - `0`: 正常終了（少なくとも1入力を処理）
  - `1`: 異常終了
- 異常終了条件:
  - 引数不足または引数不正
  - 入力がすべて未指定または未存在
- ログ要件:
  - スキップ理由（UND/CLOC/PMDごとの未指定・未存在）を明示すること。
  - 異常理由は標準エラーに出力すること。

## 8. 非機能要求

- 冪等性: 同一入力・同一出力先で再実行可能であること。
- 保守性: 入口層は薄く保ち、処理責務をタスク層へ分離すること。
- 可観測性: 実行された処理・スキップされた処理がログで判別できること。
- 拡張性: 新規解析タスクを追加可能なモジュール構造であること。

## 9. 受け入れ基準

1. UND 入力で Win/Linux 形式 CSV の両方を正しく処理できること。
2. CLOC CSV 入力を受け取り、`OUTPUT_DIR/cloc/` に成果物を出力できること。
3. PMD 複数XML入力を統合解析し、`OUTPUT_DIR/pmd/` に成果物を出力できること。
4. UND/CLOC/PMD の一部が未存在でも、存在入力のみで正常終了できること。
5. summary と複合情報が `OUTPUT_DIR` 直下に配置されること。
6. 全入力未存在時のみ終了コード1を返すこと。

## 10. 実装制約

- 既存成果物のパス互換を可能な範囲で維持し、下流連携影響を最小化すること。
- 既存 Python スクリプト群との互換実行を優先し、段階的置換を許容すること。
