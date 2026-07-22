from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from io_models import AnalysisInputs, TaskResult, _safe_num


def _render_treemap(vis: dict, df: pd.DataFrame, out_path: Path, inputs: AnalysisInputs) -> None:
    area_col = vis.get("metric_area")
    color_col = vis.get("metric_color")
    if not area_col:
        raise ValueError("Treemap visualization must specify 'metric_area'")

    from plotly_visualize import write_treemap_by_path
    write_treemap_by_path(
        df,
        file_col="File",
        size_col=area_col,
        color_col=color_col,
        output_html=out_path,
        title=f"Treemap: Size={area_col}" + (f", Color={color_col}" if color_col else ""),
        prefix_to_remove=inputs.remove_path_prefix,
    )


def _render_pie_chart(vis: dict, df: pd.DataFrame, out_path: Path, inputs: AnalysisInputs) -> None:
    label_col = vis.get("metric")
    val_col = vis.get("value_metric")
    if not label_col:
        raise ValueError("Pie chart visualization must specify 'metric' (label column)")

    df_copy = df.copy()
    if val_col:
        df_copy[val_col] = _safe_num(df_copy[val_col])
        by_group = df_copy.groupby(label_col, dropna=False)[val_col].sum().reset_index()
        value_column = val_col
    else:
        if label_col == "cloc_language" and "cloc_code" in df.columns:
            val_col = "cloc_code"
            df_copy[val_col] = _safe_num(df_copy[val_col])
            by_group = df_copy.groupby(label_col, dropna=False)[val_col].sum().reset_index()
            value_column = val_col
        else:
            df_copy["_count"] = 1
            by_group = df_copy.groupby(label_col, dropna=False)["_count"].sum().reset_index()
            value_column = "_count"

    from plotly_visualize import write_pie_chart
    write_pie_chart(
        by_group,
        value_column=value_column,
        label_column=label_col,
        title=f"Pie Chart: {label_col} by {value_column}",
        output_html=out_path,
        exclude_label=None,
    )


def _render_sunburst(vis: dict, df: pd.DataFrame, out_path: Path, inputs: AnalysisInputs) -> None:
    path = vis.get("path")
    metric_values = vis.get("metric_values")
    if not path or not metric_values:
        raise ValueError("Sunburst visualization must specify 'path' (list of columns) and 'metric_values'")
    
    path_list = [p.strip() for p in path.split(",") if p.strip()] if isinstance(path, str) else path
    df_copy = df.copy()
    df_copy[metric_values] = _safe_num(df_copy[metric_values])
    for col in path_list:
        df_copy[col] = df_copy[col].fillna("unknown").astype(str).replace("", "unknown")

    fig = px.sunburst(df_copy, path=path_list, values=metric_values)
    fig.write_html(out_path)


def _render_plotly_px(vis: dict, df: pd.DataFrame, out_path: Path, vis_type: str) -> None:
    required = {
        "scatter": ["metric_x", "metric_y"],
        "box": ["metric_y"],
        "density_heatmap": ["metric_x", "metric_y"],
        "violin": ["metric_y"],
        "histogram": ["metric_x"],
        "ecdf": ["metric_x"],
        "bar": ["metric_x", "metric_y"],
        "line": ["metric_x", "metric_y"],
    }.get(vis_type, [])

    for r in required:
        if not vis.get(r):
            raise ValueError(f"Visualization type '{vis_type}' must specify '{r}'")

    df_copy = df.copy()
    
    num_cols = ["metric_x", "metric_y", "metric_size", "metric_color", "metric_values", "value_metric"]
    for param in num_cols:
        col = vis.get(param)
        if col and col in df_copy.columns:
            df_copy[col] = _safe_num(df_copy[col])

    kwargs = {}
    param_map = {
        "metric_x": "x",
        "metric_y": "y",
        "metric_size": "size",
        "metric_color": "color",
        "hover_name": "hover_name",
    }
    for param, px_arg in param_map.items():
        col = vis.get(param)
        if col:
            kwargs[px_arg] = col

    if vis_type == "box":
        kwargs["points"] = "all"
    elif vis_type == "violin":
        kwargs["box"] = True
        kwargs["points"] = "outliers"
    elif vis_type == "histogram":
        nbins = vis.get("nbins")
        if nbins:
            kwargs["nbins"] = int(nbins)
    elif vis_type == "bar":
        top_n = vis.get("top_n")
        y_col = vis.get("metric_y")
        if top_n and y_col:
            df_copy = df_copy.sort_values(by=y_col, ascending=False).head(int(top_n))
    elif vis_type == "line":
        x_col = vis.get("metric_x")
        if x_col:
            df_copy[x_col] = df_copy[x_col].astype(str)

    px_func = getattr(px, vis_type, None)
    if px_func is None:
        raise ValueError(f"Unsupported plotly express visualization type: {vis_type}")
        
    fig = px_func(df_copy, **kwargs)
    fig.write_html(out_path)


from concurrent.futures import ThreadPoolExecutor


def generate_index_html(inputs: AnalysisInputs, vis_outputs: list[Path]) -> Path:
    index_path = inputs.output_dir / "index.html"
    
    summary_csv = inputs.output_dir / "summary.csv"
    summary_rows = []
    if summary_csv.exists():
        try:
            summary_df = pd.read_csv(summary_csv)
            summary_rows = summary_df.to_dict("records")
        except Exception:
            pass

    loc_total = "-"
    file_total = "-"
    clone_ratio = "-"

    for r in summary_rows:
        val_loc = r.get("und_CountLineCode") or r.get("cloc_CountLineCode")
        if val_loc:
            try:
                loc_total = f"{int(float(val_loc)):,}"
            except ValueError:
                pass

        val_files = r.get("fm_TotalFiles") or r.get("und_FileCount") or r.get("cloc_Files")
        if val_files:
            try:
                file_total = f"{int(float(val_files)):,}"
            except ValueError:
                pass

        val_clone = r.get("pmd_CloneRatio")
        if val_clone:
            try:
                clone_ratio = f"{float(val_clone):.2f}%"
            except ValueError:
                pass

    vis_cards = ""
    for out in sorted(vis_outputs):
        try:
            rel_path = out.relative_to(inputs.output_dir).as_posix()
        except ValueError:
            rel_path = out.name
        name = out.stem.replace("_", " ").title()
        vis_cards += f"""
        <a class="card" href="{rel_path}" target="_blank">
          <div class="card-icon">📊</div>
          <div class="card-title">{name}</div>
          <div class="card-sub">{rel_path}</div>
        </a>"""

    if not vis_cards:
        vis_cards = "<p class='no-vis'>可視化ファイルは生成されていません。</p>"

    artifacts = [
        ("metrics_report.xlsx", "統合 Excel レポート", "📊", "エクセル形式の多角的詳細分析データ"),
        ("metrics_merge.csv", "統合マスタ CSV", "📄", "全解析ツールの結合マスタデータ"),
        ("summary.csv", "タスク実行サマリ CSV", "📝", "各タスクの実行結果とKPI概要"),
    ]
    art_cards = ""
    for file_name, label, icon, desc in artifacts:
        p = inputs.output_dir / file_name
        if p.exists():
            art_cards += f"""
            <a class="card art-card" href="{file_name}">
              <div class="card-icon">{icon}</div>
              <div class="card-title">{label}</div>
              <div class="card-sub">{file_name} — {desc}</div>
            </a>"""

    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Report Analysis Dashboard</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0f172a;
      --card-bg: #1e293b;
      --accent: #38bdf8;
      --text: #f8fafc;
      --subtext: #94a3b8;
      --border: #334155;
    }}
    body {{
      font-family: 'Inter', sans-serif;
      background-color: var(--bg);
      color: var(--text);
      margin: 0;
      padding: 30px;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 30px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 20px;
    }}
    h1 {{ font-size: 26px; margin: 0; color: var(--accent); }}
    .kpi-container {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 15px;
      margin-bottom: 35px;
    }}
    .kpi-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 18px;
    }}
    .kpi-title {{ font-size: 13px; color: var(--subtext); margin-bottom: 6px; }}
    .kpi-value {{ font-size: 24px; font-weight: 700; color: var(--accent); }}
    
    .section-title {{
      font-size: 18px;
      margin-bottom: 15px;
      border-left: 4px solid var(--accent);
      padding-left: 10px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 20px;
      margin-bottom: 35px;
    }}
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      text-decoration: none;
      color: var(--text);
      transition: transform 0.2s, border-color 0.2s;
      display: block;
    }}
    .card:hover {{
      transform: translateY(-3px);
      border-color: var(--accent);
    }}
    .card-icon {{ font-size: 28px; margin-bottom: 10px; }}
    .card-title {{ font-size: 16px; font-weight: 600; margin-bottom: 6px; }}
    .card-sub {{ font-size: 12px; color: var(--subtext); word-break: break-all; }}
    .art-card {{ border-color: #3b82f6; }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>Report Analysis Dashboard</h1>
      <p style="color: var(--subtext); margin: 5px 0 0 0;">静的解析・品質評価 統合レポートポータル</p>
    </div>
  </div>

  <div class="kpi-container">
    <div class="kpi-card">
      <div class="kpi-title">総コード行数 (LoC)</div>
      <div class="kpi-value">{loc_total}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">総ファイル数</div>
      <div class="kpi-value">{file_total}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">コード重複率 (PMD)</div>
      <div class="kpi-value">{clone_ratio}</div>
    </div>
  </div>

  <div class="section-title">📊 インタラクティブ可視化 HTML レポート</div>
  <div class="grid">
    {vis_cards}
  </div>

  <div class="section-title">📦 集計データ・ファイル成果物</div>
  <div class="grid">
    {art_cards}
  </div>
</body>
</html>"""

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return index_path


def run_advanced_visualizations(inputs: AnalysisInputs) -> TaskResult:
    if inputs.config_path is None:
        index_p = generate_index_html(inputs, [])
        return TaskResult(
            name="visualize",
            executed=False,
            success=True,
            outputs=[index_p],
            message="No config file specified, skipping visualizations",
        )

    outputs: list[Path] = []
    try:
        merge_file = inputs.output_dir / "metrics_merge.csv"
        if not merge_file.exists():
            if inputs.visualizations:
                raise FileNotFoundError(
                    f"Merged metrics file '{merge_file}' not found, but visualizations are requested in config."
                )
            index_p = generate_index_html(inputs, [])
            return TaskResult(
                name="visualize",
                executed=True,
                success=True,
                outputs=[index_p],
                message="No visualizations executed (merge file not found and config visualizations list empty)",
            )

        df = pd.read_csv(merge_file)

        def check_col(col_name: str, vis_type: str):
            if col_name not in df.columns:
                raise KeyError(
                    f"Column '{col_name}' specified in '{vis_type}' visualization not found in metrics_merge.csv"
                )

        def render_single_vis(vis: dict) -> Path:
            vis_type = vis.get("type")
            out_rel = vis.get("output_file")
            if not vis_type or not out_rel:
                raise ValueError("Visualization spec must contain 'type' and 'output_file'")

            out_path = inputs.output_dir / out_rel
            out_path.parent.mkdir(parents=True, exist_ok=True)

            cols_to_check = ["metric_area", "metric_color", "metric", "value_metric", "metric_x", "metric_y", "metric_size", "hover_name", "metric_values"]
            for param in cols_to_check:
                col = vis.get(param)
                if col:
                    check_col(col, vis_type)

            if vis_type == "sunburst" and vis.get("path"):
                path_val = vis["path"]
                path_list = [p.strip() for p in path_val.split(",") if p.strip()] if isinstance(path_val, str) else path_val
                for p in path_list:
                    check_col(p, vis_type)

            if vis_type == "treemap":
                _render_treemap(vis, df, out_path, inputs)
            elif vis_type == "pie_chart":
                _render_pie_chart(vis, df, out_path, inputs)
            elif vis_type == "sunburst":
                _render_sunburst(vis, df, out_path, inputs)
            else:
                _render_plotly_px(vis, df, out_path, vis_type)

            return out_path

        # 並列レンダリング (ThreadPoolExecutor)
        if len(inputs.visualizations) > 1:
            with ThreadPoolExecutor() as executor:
                outputs = list(executor.map(render_single_vis, inputs.visualizations))
        else:
            outputs = [render_single_vis(v) for v in inputs.visualizations]

        index_p = generate_index_html(inputs, outputs)
        outputs.append(index_p)

        return TaskResult(
            name="visualize",
            executed=True,
            success=True,
            outputs=outputs,
            message=f"Custom visualizations generated ({len(outputs) - 1} files + index.html)",
        )
    except Exception as exc:
        index_p = generate_index_html(inputs, outputs)
        return TaskResult(
            name="visualize",
            executed=True,
            success=False,
            outputs=outputs + [index_p],
            message=f"Visualization failed: {exc}",
        )

