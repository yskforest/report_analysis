from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def write_pie_chart(
    df: pd.DataFrame,
    value_column: str,
    label_column: str,
    title: str,
    output_html: Path,
    *,
    exclude_label: str | None = "SUM",
    hole: float = 0.4,
) -> None:
    data = df.copy()
    if exclude_label is not None:
        data = data[data[label_column].astype(str) != exclude_label]

    data[value_column] = pd.to_numeric(data[value_column], errors="coerce").fillna(0)
    data = data.sort_values(by=value_column, ascending=False)
    total_value = float(data[value_column].sum())

    fig = px.pie(data, values=value_column, names=label_column, title=title, hole=hole)
    fig.update_traces(textinfo="label+value+percent", textposition="inside")
    fig.update_layout(
        annotations=[dict(text=f"Total: {total_value:,.0f}", x=0.5, y=0.5, font_size=28, showarrow=False)]
    )
    fig.write_html(output_html)


def write_treemap_by_path(
    df: pd.DataFrame,
    *,
    file_col: str,
    size_col: str,
    color_col: str | None = None,
    output_html: Path,
    title: str,
    prefix_to_remove: str | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
    max_depth: int | None = None,
    empty_label: str | None = None,
    aggregate: bool = False,
    color_agg: str = "weighted_mean",
    color_continuous_scale="OrRd",
) -> None:
    data = df.copy()
    data = data.dropna(subset=[file_col])
    # 欠損値や空文字を排除
    data = data[data[file_col].astype(str).str.strip() != ""]
    
    data[size_col] = pd.to_numeric(data[size_col], errors="coerce")
    if color_col is not None:
        data[color_col] = pd.to_numeric(data[color_col], errors="coerce")
        data = data[data[size_col] > 0].dropna(subset=[size_col, color_col])
    else:
        data = data[data[size_col] > 0].dropna(subset=[size_col])

    if data.empty:
        if empty_label is None:
            return
        empty_row = {file_col: empty_label, size_col: 1}
        if color_col is not None:
            empty_row[color_col] = 0
        data = pd.DataFrame([empty_row])

    paths = data[file_col].astype(str).str.replace("\\\\", "/", regex=False)
    if prefix_to_remove:
        normalized_prefix = prefix_to_remove.replace("\\", "/")
        if normalized_prefix not in {"/", "\\"}:
            paths = paths.apply(lambda p: (p[len(normalized_prefix) :] if p.startswith(normalized_prefix) else p))
    path_parts = paths.str.strip("/").str.split("/")

    full_depth = int(path_parts.map(len).max())
    use_depth = max_depth if max_depth is not None else full_depth
    use_depth = max(1, use_depth)

    for i in range(use_depth):
        data[f"level_{i}"] = path_parts.map(lambda x: x[i] if i < len(x) else np.nan)

    level_cols = [f"level_{i}" for i in range(use_depth)]
    if aggregate:
        if color_col is not None and color_agg not in {"weighted_mean", "sum", "mean", "max"}:
            raise ValueError(f"unsupported color_agg: {color_agg}")
        nodes = _aggregate_treemap_nodes(data, path_parts, size_col=size_col, color_col=color_col, color_agg=color_agg)

        marker_opts = {"line": {"width": 1, "color": "black"}}
        if color_col is not None:
            color_min = float(vmin) if vmin is not None else float(nodes[color_col].min())
            color_max = float(vmax) if vmax is not None else float(nodes[color_col].max())
            marker_opts.update(
                {
                    "colors": nodes[color_col],
                    "colorscale": color_continuous_scale,
                    "cmin": color_min,
                    "cmax": color_max,
                    "colorbar": {"title": color_col},
                }
            )
            customdata = np.stack([nodes[size_col], nodes[color_col]], axis=-1)
            hovertemplate = (
                "%{label}<br>"
                f"{size_col}: " + "%{customdata[0]:,.0f}<br>"
                f"{color_col}: " + "%{customdata[1]:,.6g}"
                "<extra></extra>"
            )
        else:
            customdata = np.stack([nodes[size_col]], axis=-1)
            hovertemplate = "%{label}<br>" f"{size_col}: " + "%{customdata[0]:,.0f}<br>" "<extra></extra>"

        fig = go.Figure(
            go.Treemap(
                ids=nodes["id"],
                labels=nodes["label"],
                parents=nodes["parent"],
                values=nodes[size_col],
                branchvalues="total",
                marker=marker_opts,
                customdata=customdata,
                hovertemplate=hovertemplate,
            )
        )
        fig.update_layout(title=title, margin=dict(t=50, l=25, r=25, b=25))
        fig.write_html(output_html)
        return

    if color_col is not None:
        color_min = float(vmin) if vmin is not None else float(data[color_col].min())
        color_max = float(vmax) if vmax is not None else float(data[color_col].max())

        fig = px.treemap(
            data,
            path=level_cols,
            values=size_col,
            color=color_col,
            color_continuous_scale=color_continuous_scale,
            range_color=[color_min, color_max],
            title=title,
        )
    else:
        fig = px.treemap(
            data,
            path=level_cols,
            values=size_col,
            title=title,
        )

    fig.update_traces(marker=dict(line=dict(width=1, color="black")))
    fig.update_layout(margin=dict(t=50, l=25, r=25, b=25))
    fig.write_html(output_html)


def _aggregate_treemap_nodes(
    data: pd.DataFrame,
    path_parts: pd.Series,
    *,
    size_col: str,
    color_col: str | None,
    color_agg: str,
) -> pd.DataFrame:
    nodes: dict[str, dict[str, object]] = {}

    def ensure_node(node_id: str, label: str, parent: str) -> dict[str, object]:
        if node_id not in nodes:
            node = {
                "id": node_id,
                "label": label,
                "parent": parent,
                size_col: 0.0,
            }
            if color_col is not None:
                node[color_col] = 0.0
                node["_weighted"] = 0.0
                node["_count"] = 0
            nodes[node_id] = node
        return nodes[node_id]

    ensure_node("__root__", "ALL_FILES", "")
    for row, parts in zip(data.to_dict("records"), path_parts, strict=False):
        clean_parts = [str(part) for part in parts if pd.notna(part) and str(part)]
        if not clean_parts:
            clean_parts = ["NO_DATA"]
        size_value = float(row.get(size_col, 0) or 0)
        color_value = float(row.get(color_col, 0) or 0) if color_col is not None else 0.0

        parent = "__root__"
        prefixes = [("__root__", "ALL_FILES", "")]
        current_parts: list[str] = []
        for part in clean_parts:
            current_parts.append(part)
            node_id = "path:" + "/".join(current_parts)
            prefixes.append((node_id, part, parent))
            parent = node_id

        for node_id, label, node_parent in prefixes:
            node = ensure_node(node_id, label, node_parent)
            node[size_col] = float(node[size_col]) + size_value
            if color_col is not None:
                if color_agg == "weighted_mean":
                    node["_weighted"] = float(node["_weighted"]) + color_value * size_value
                elif color_agg == "sum":
                    node[color_col] = float(node[color_col]) + color_value
                elif color_agg == "max":
                    node[color_col] = max(float(node[color_col]), color_value)
                elif color_agg == "mean":
                    node[color_col] = float(node[color_col]) + color_value
                    node["_count"] = int(node["_count"]) + 1

    if color_col is not None:
        for node in nodes.values():
            if color_agg == "weighted_mean":
                size_value = float(node[size_col])
                node[color_col] = float(node["_weighted"]) / size_value if size_value else 0.0
            elif color_agg == "mean":
                count = int(node["_count"])
                node[color_col] = float(node[color_col]) / count if count else 0.0

    out = pd.DataFrame(nodes.values())
    if color_col is not None:
        out = out.drop(columns=["_weighted", "_count"])
    return out
