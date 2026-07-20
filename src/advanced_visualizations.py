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


def run_advanced_visualizations(inputs: AnalysisInputs) -> TaskResult:
    if inputs.config_path is None:
        return TaskResult(
            name="visualize",
            executed=False,
            success=True,
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
            return TaskResult(
                name="visualize",
                executed=True,
                success=True,
                message="No visualizations executed (merge file not found and config visualizations list empty)",
            )

        df = pd.read_csv(merge_file)

        def check_col(col_name: str, vis_type: str):
            if col_name not in df.columns:
                raise KeyError(
                    f"Column '{col_name}' specified in '{vis_type}' visualization not found in metrics_merge.csv"
                )

        for i, vis in enumerate(inputs.visualizations):
            vis_type = vis.get("type")
            out_rel = vis.get("output_file")
            if not vis_type or not out_rel:
                raise ValueError(f"Visualization spec at index {i} must contain 'type' and 'output_file'")

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

            outputs.append(out_path)

        return TaskResult(
            name="visualize",
            executed=True,
            success=True,
            outputs=outputs,
            message=f"Custom visualizations generated ({len(outputs)} files)",
        )
    except Exception as exc:
        return TaskResult(
            name="visualize",
            executed=True,
            success=False,
            outputs=outputs,
            message=f"Visualization failed: {exc}",
        )
