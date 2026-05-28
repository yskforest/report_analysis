from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px


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
    color_col: str,
    output_html: Path,
    title: str,
    prefix_to_remove: str | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
    max_depth: int | None = None,
) -> None:
    data = df.copy()
    data[size_col] = pd.to_numeric(data[size_col], errors="coerce")
    data[color_col] = pd.to_numeric(data[color_col], errors="coerce")
    data = data[data[size_col] > 0].dropna(subset=[size_col, color_col])
    if data.empty:
        return

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

    color_min = float(vmin) if vmin is not None else float(data[color_col].min())
    color_max = float(vmax) if vmax is not None else float(data[color_col].max())

    fig = px.treemap(
        data,
        path=[f"level_{i}" for i in range(use_depth)],
        values=size_col,
        color=color_col,
        color_continuous_scale="OrRd",
        range_color=[color_min, color_max],
        title=title,
    )
    fig.update_traces(marker=dict(line=dict(width=1, color="black")))
    fig.update_layout(margin=dict(t=50, l=25, r=25, b=25))
    fig.write_html(output_html)
