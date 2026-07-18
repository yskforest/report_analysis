from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from io_models import AnalysisInputs, TaskResult


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _save(fig, out: Path, outputs: list[Path]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(out)
    outputs.append(out)


def _top_n(df: pd.DataFrame, col: str, n: int = 30) -> pd.DataFrame:
    return df.sort_values(by=col, ascending=False).head(n).copy()


def run_advanced_visualizations(inputs: AnalysisInputs) -> TaskResult:
    outputs: list[Path] = []
    notes: list[str] = []

    # Case 1: Config file specified -> execute only the specified custom visualizations
    if inputs.config_path is not None:
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

                # Resolve output path relative to output_dir (allowing subdirectories)
                out_path = inputs.output_dir / out_rel
                out_path.parent.mkdir(parents=True, exist_ok=True)

                if vis_type == "treemap":
                    area_col = vis.get("metric_area")
                    color_col = vis.get("metric_color")
                    if not area_col:
                        raise ValueError("Treemap visualization must specify 'metric_area'")

                    check_col(area_col, "treemap")
                    if color_col:
                        check_col(color_col, "treemap")

                    # Lazy import to avoid circular dependency or import order issues
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
                    outputs.append(out_path)

                elif vis_type == "pie_chart":
                    label_col = vis.get("metric")
                    val_col = vis.get("value_metric")
                    if not label_col:
                        raise ValueError("Pie chart visualization must specify 'metric' (label column)")

                    check_col(label_col, "pie_chart")

                    df_copy = df.copy()
                    if val_col:
                        check_col(val_col, "pie_chart")
                        df_copy[val_col] = pd.to_numeric(df_copy[val_col], errors="coerce").fillna(0)
                        by_group = df_copy.groupby(label_col, dropna=False)[val_col].sum().reset_index()
                        value_column = val_col
                    else:
                        # Auto-fallback to cloc_code if label is cloc_language
                        if label_col == "cloc_language" and "cloc_code" in df.columns:
                            val_col = "cloc_code"
                            df_copy[val_col] = pd.to_numeric(df_copy[val_col], errors="coerce").fillna(0)
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
                    outputs.append(out_path)
                elif vis_type == "scatter":
                    metric_x = vis.get("metric_x")
                    metric_y = vis.get("metric_y")
                    metric_size = vis.get("metric_size")
                    metric_color = vis.get("metric_color")
                    hover_name = vis.get("hover_name")

                    if not metric_x or not metric_y:
                        raise ValueError("Scatter visualization must specify 'metric_x' and 'metric_y'")
                    check_col(metric_x, "scatter")
                    check_col(metric_y, "scatter")

                    df_copy = df.copy()
                    df_copy[metric_x] = _safe_num(df_copy[metric_x])
                    df_copy[metric_y] = _safe_num(df_copy[metric_y])

                    kwargs = {}
                    if metric_size:
                        check_col(metric_size, "scatter")
                        df_copy[metric_size] = _safe_num(df_copy[metric_size])
                        kwargs["size"] = metric_size
                    if metric_color:
                        check_col(metric_color, "scatter")
                        kwargs["color"] = metric_color
                    if hover_name:
                        check_col(hover_name, "scatter")
                        kwargs["hover_name"] = hover_name

                    fig = px.scatter(df_copy, x=metric_x, y=metric_y, **kwargs)
                    fig.write_html(out_path)
                    outputs.append(out_path)

                elif vis_type == "box":
                    metric_x = vis.get("metric_x")
                    metric_y = vis.get("metric_y")

                    if not metric_y:
                        raise ValueError("Box visualization must specify 'metric_y'")
                    check_col(metric_y, "box")

                    df_copy = df.copy()
                    df_copy[metric_y] = _safe_num(df_copy[metric_y])

                    kwargs = {}
                    if metric_x:
                        check_col(metric_x, "box")
                        kwargs["x"] = metric_x

                    fig = px.box(df_copy, y=metric_y, points="all", **kwargs)
                    fig.write_html(out_path)
                    outputs.append(out_path)

                elif vis_type == "density_heatmap":
                    metric_x = vis.get("metric_x")
                    metric_y = vis.get("metric_y")

                    if not metric_x or not metric_y:
                        raise ValueError("Density heatmap visualization must specify 'metric_x' and 'metric_y'")
                    check_col(metric_x, "density_heatmap")
                    check_col(metric_y, "density_heatmap")

                    df_copy = df.copy()
                    df_copy[metric_x] = _safe_num(df_copy[metric_x])
                    df_copy[metric_y] = _safe_num(df_copy[metric_y])

                    fig = px.density_heatmap(df_copy, x=metric_x, y=metric_y)
                    fig.write_html(out_path)
                    outputs.append(out_path)

                elif vis_type == "violin":
                    metric_y = vis.get("metric_y")
                    metric_x = vis.get("metric_x")

                    if not metric_y:
                        raise ValueError("Violin visualization must specify 'metric_y'")
                    check_col(metric_y, "violin")

                    df_copy = df.copy()
                    df_copy[metric_y] = _safe_num(df_copy[metric_y])

                    kwargs = {}
                    if metric_x:
                        check_col(metric_x, "violin")
                        kwargs["x"] = metric_x

                    fig = px.violin(df_copy, y=metric_y, box=True, points="outliers", **kwargs)
                    fig.write_html(out_path)
                    outputs.append(out_path)

                elif vis_type == "histogram":
                    metric_x = vis.get("metric_x")
                    nbins = vis.get("nbins")

                    if not metric_x:
                        raise ValueError("Histogram visualization must specify 'metric_x'")
                    check_col(metric_x, "histogram")

                    df_copy = df.copy()
                    df_copy[metric_x] = _safe_num(df_copy[metric_x])

                    kwargs = {}
                    if nbins:
                        kwargs["nbins"] = int(nbins)

                    fig = px.histogram(df_copy, x=metric_x, **kwargs)
                    fig.write_html(out_path)
                    outputs.append(out_path)

                elif vis_type == "ecdf":
                    metric_x = vis.get("metric_x")

                    if not metric_x:
                        raise ValueError("ECDF visualization must specify 'metric_x'")
                    check_col(metric_x, "ecdf")

                    df_copy = df.copy()
                    df_copy[metric_x] = _safe_num(df_copy[metric_x])

                    fig = px.ecdf(df_copy, x=metric_x)
                    fig.write_html(out_path)
                    outputs.append(out_path)

                elif vis_type == "bar":
                    metric_x = vis.get("metric_x")
                    metric_y = vis.get("metric_y")
                    metric_color = vis.get("metric_color")
                    top_n = vis.get("top_n")

                    if not metric_x or not metric_y:
                        raise ValueError("Bar visualization must specify 'metric_x' and 'metric_y'")
                    check_col(metric_x, "bar")
                    check_col(metric_y, "bar")

                    df_copy = df.copy()
                    df_copy[metric_y] = _safe_num(df_copy[metric_y])

                    if top_n:
                        df_copy = df_copy.sort_values(by=metric_y, ascending=False).head(int(top_n))

                    kwargs = {}
                    if metric_color:
                        check_col(metric_color, "bar")
                        kwargs["color"] = metric_color

                    fig = px.bar(df_copy, x=metric_x, y=metric_y, **kwargs)
                    fig.write_html(out_path)
                    outputs.append(out_path)

                elif vis_type == "sunburst":
                    path = vis.get("path")
                    metric_values = vis.get("metric_values")

                    if not path or not metric_values:
                        raise ValueError("Sunburst visualization must specify 'path' (list of columns) and 'metric_values'")
                    
                    if isinstance(path, str):
                        path_list = [p.strip() for p in path.split(",") if p.strip()]
                    else:
                        path_list = path

                    for p in path_list:
                        check_col(p, "sunburst")
                    check_col(metric_values, "sunburst")

                    df_copy = df.copy()
                    df_copy[metric_values] = _safe_num(df_copy[metric_values])
                    for col in path_list:
                        df_copy[col] = df_copy[col].fillna("unknown").astype(str).replace("", "unknown")

                    fig = px.sunburst(df_copy, path=path_list, values=metric_values)
                    fig.write_html(out_path)
                    outputs.append(out_path)

                elif vis_type == "line":
                    metric_x = vis.get("metric_x")
                    metric_y = vis.get("metric_y")

                    if not metric_x or not metric_y:
                        raise ValueError("Line visualization must specify 'metric_x' and 'metric_y'")
                    check_col(metric_x, "line")
                    check_col(metric_y, "line")

                    df_copy = df.copy()
                    df_copy[metric_x] = df_copy[metric_x].astype(str)
                    df_copy[metric_y] = _safe_num(df_copy[metric_y])

                    fig = px.line(df_copy, x=metric_x, y=metric_y)
                    fig.write_html(out_path)
                    outputs.append(out_path)
                else:
                    raise ValueError(f"Unsupported visualization type: {vis_type}")

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

    # Case 2: Config file not specified -> skip visualizations
    return TaskResult(
        name="visualize",
        executed=False,
        success=True,
        message="No config file specified, skipping visualizations",
    )
