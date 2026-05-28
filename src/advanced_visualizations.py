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
    out_dir = inputs.output_dir / "visualizations"
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    notes: list[str] = []

    und_file = inputs.output_dir / "und" / "und_file.csv"
    cloc_file = inputs.output_dir / "cloc" / "cloc_filtered.csv"
    pmd_file = inputs.output_dir / "pmd" / "pmd_clone_ratio.csv"
    merge_file = inputs.output_dir / "und_pmd_merge.csv"

    und = pd.read_csv(und_file, dtype=object, na_filter=False) if und_file.exists() else pd.DataFrame()
    cloc = pd.read_csv(cloc_file) if cloc_file.exists() else pd.DataFrame()
    pmd = pd.read_csv(pmd_file) if pmd_file.exists() else pd.DataFrame()
    merged = pd.read_csv(merge_file, dtype=object, na_filter=False) if merge_file.exists() else pd.DataFrame()

    try:
        if not und.empty and "CountLineCode" in und.columns and "AvgCyclomatic" in und.columns:
            u = und.copy()
            u["CountLineCode"] = _safe_num(u["CountLineCode"])
            u["AvgCyclomatic"] = _safe_num(u["AvgCyclomatic"])
            u["CountLineComment"] = _safe_num(u.get("CountLineComment", pd.Series(dtype=float)))
            u["Kind"] = u.get("Kind", pd.Series(["File"] * len(u))).astype(str)
            u["File"] = u.get("File", pd.Series(["unknown"] * len(u))).astype(str)
            if "AvgEssential" in u.columns:
                u["AvgEssential"] = _safe_num(u["AvgEssential"])
            else:
                u["AvgEssential"] = 0

            _save(px.scatter(u, x="CountLineCode", y="AvgCyclomatic", size="CountLineComment", color="Kind", hover_name="File"), out_dir / "01_scatter_loc_vs_cyclomatic.html", outputs)
            _save(px.scatter(u, x="CountLineCode", y="AvgEssential", hover_name="File"), out_dir / "02_scatter_loc_vs_essential.html", outputs)
            _save(px.density_heatmap(u, x="CountLineCode", y="AvgCyclomatic"), out_dir / "23_density_loc_vs_cyclomatic.html", outputs)
            _save(px.box(u, y="CountLineCode"), out_dir / "06_box_loc_distribution.html", outputs)
            _save(px.box(u, y="AvgCyclomatic"), out_dir / "07_box_cyclomatic_distribution.html", outputs)
            _save(px.violin(u, y="AvgEssential", box=True, points="outliers"), out_dir / "08_violin_essential_distribution.html", outputs)
            _save(px.histogram(u, x="AvgCyclomatic", nbins=60), out_dir / "09_hist_cyclomatic.html", outputs)
            if "RatioCommentToCode" in u.columns:
                u["RatioCommentToCode"] = _safe_num(u["RatioCommentToCode"])
                _save(px.histogram(u, x="RatioCommentToCode", nbins=60), out_dir / "10_hist_comment_ratio.html", outputs)
        else:
            notes.append("UND-based charts skipped")

        if not pmd.empty:
            p = pmd.copy()
            p["PmdCloneRatio"] = _safe_num(p["PmdCloneRatio"])
            p["PmdTotalTokens"] = _safe_num(p["PmdTotalTokens"])
            p["PmdCloneTokensSum"] = _safe_num(p["PmdCloneTokensSum"])
            p["File"] = p["File"].astype(str)
            _save(px.ecdf(p, x="PmdCloneRatio"), out_dir / "11_cdf_clone_ratio.html", outputs)
            _save(px.bar(_top_n(p, "PmdCloneTokensSum", 30), x="File", y="PmdCloneTokensSum"), out_dir / "13_pareto_clone_tokens_top30.html", outputs)
            _save(px.bar(_top_n(p, "PmdCloneRatio", 30), x="File", y="PmdCloneRatio"), out_dir / "18_bar_top_clone_ratio.html", outputs)
        else:
            notes.append("PMD-based charts skipped")

        if not cloc.empty:
            c = cloc.copy()
            for col in ["code", "comment", "blank"]:
                c[col] = _safe_num(c[col])
            by_lang = c.groupby("language", dropna=False)[["code", "comment", "blank"]].sum().reset_index()
            melt = by_lang.melt(id_vars=["language"], value_vars=["code", "comment", "blank"], var_name="type", value_name="lines")
            _save(px.bar(melt, x="language", y="lines", color="type", barmode="stack"), out_dir / "14_stacked_lang_code_comment_blank.html", outputs)
            lang_total = by_lang[["code", "comment", "blank"]].sum(axis=1).replace(0, 1)
            ratio_df = by_lang.copy()
            ratio_df["code"] = ratio_df["code"] / lang_total
            ratio_df["comment"] = ratio_df["comment"] / lang_total
            ratio_df["blank"] = ratio_df["blank"] / lang_total
            ratio_melt = ratio_df.melt(id_vars=["language"], value_vars=["code", "comment", "blank"], var_name="type", value_name="ratio")
            _save(px.bar(ratio_melt, x="language", y="ratio", color="type", barmode="stack"), out_dir / "15_stacked100_lang_ratio.html", outputs)
        else:
            notes.append("CLOC-based charts skipped")

        if not merged.empty:
            m = merged.copy()
            for col in ["CountLineCode", "AvgCyclomatic", "AvgEssential", "RatioCommentToCode", "PmdCloneRatio", "PmdCloneTokensSum", "PmdTotalTokens"]:
                if col in m.columns:
                    m[col] = _safe_num(m[col])
            m["File"] = m.get("File", pd.Series(["unknown"] * len(m))).astype(str)
            if "PmdCloneRatio" in m.columns and "CountLineCode" in m.columns:
                _save(px.scatter(m, x="CountLineCode", y="PmdCloneRatio", size="PmdCloneTokensSum", hover_name="File"), out_dir / "03_bubble_clone_ratio_vs_loc.html", outputs)
            metric_cols = [c for c in ["CountLineCode", "AvgCyclomatic", "AvgEssential", "RatioCommentToCode", "PmdCloneRatio", "PmdCloneTokensSum"] if c in m.columns]
            if metric_cols:
                corr = m[metric_cols].corr(numeric_only=True).fillna(0)
                _save(px.imshow(corr, text_auto=True, aspect="auto"), out_dir / "05_correlation_heatmap.html", outputs)

            if "CountLineCode" in m.columns:
                _save(px.bar(_top_n(m, "CountLineCode", 30), x="File", y="CountLineCode"), out_dir / "12_pareto_loc_top30.html", outputs)
            if "AvgCyclomatic" in m.columns:
                _save(px.bar(_top_n(m, "AvgCyclomatic", 30), x="File", y="AvgCyclomatic"), out_dir / "16_bar_top_cyclomatic.html", outputs)
            if "AvgEssential" in m.columns:
                _save(px.bar(_top_n(m, "AvgEssential", 30), x="File", y="AvgEssential"), out_dir / "17_bar_top_essential.html", outputs)

            # directory-based charts
            m["dir1"] = m["File"].str.split("/").str[0].replace("", "root")
            agg_map = {}
            for col, fn in [
                ("CountLineCode", "sum"),
                ("AvgCyclomatic", "mean"),
                ("AvgEssential", "mean"),
                ("RatioCommentToCode", "mean"),
                ("PmdCloneRatio", "mean"),
                ("PmdCloneTokensSum", "sum"),
            ]:
                if col in m.columns:
                    agg_map[col] = (col, fn)
            by_dir = m.groupby("dir1", dropna=False).agg(**agg_map).reset_index()
            if len(by_dir.columns) > 1:
                _save(px.imshow(by_dir.set_index("dir1").T, aspect="auto"), out_dir / "04_heatmap_dir_metrics.html", outputs)

            if "CountLineCode" in m.columns and "PmdCloneRatio" in m.columns:
                _save(px.treemap(m, path=["dir1", "File"], values="CountLineCode", color="PmdCloneRatio"), out_dir / "21_treemap_loc_clone_ratio.html", outputs)
            if "CountLineCode" in m.columns and "RatioCommentToCode" in m.columns:
                _save(px.treemap(m, path=["dir1", "File"], values="CountLineCode", color="RatioCommentToCode"), out_dir / "22_treemap_loc_comment_ratio.html", outputs)
            if "CountLineCode" in m.columns:
                _save(px.sunburst(m, path=["dir1", "File"], values="CountLineCode"), out_dir / "20_sunburst_loc.html", outputs)

            q = m.copy()
            q["risk_score"] = q.get("AvgCyclomatic", 0) * 0.4 + q.get("AvgEssential", 0) * 0.3 + q.get("PmdCloneRatio", 0) * 0.3
            q["quadrant"] = q.apply(
                lambda r: "High-High"
                if r.get("CountLineCode", 0) >= q["CountLineCode"].median() and r.get("risk_score", 0) >= q["risk_score"].median()
                else "Other",
                axis=1,
            )
            _save(px.scatter(q, x="CountLineCode", y="risk_score", color="quadrant", hover_name="File"), out_dir / "27_quadrant_priority.html", outputs)
            _save(px.bar(_top_n(q, "risk_score", 40), x="File", y="risk_score"), out_dir / "24_rank_table_like_risk_score.html", outputs)

            # radar (top directories)
            radar = by_dir.head(8).copy()
            radar_cols = [c for c in ["CountLineCode", "AvgCyclomatic", "AvgEssential", "RatioCommentToCode", "PmdCloneRatio"] if c in radar.columns]
            for _, row in radar.iterrows():
                fig = go.Figure()
                if not radar_cols:
                    continue
                cats = radar_cols
                vals = [row[c] for c in cats]
                vals.append(vals[0])
                cats2 = cats + [cats[0]]
                fig.add_trace(go.Scatterpolar(r=vals, theta=cats2, fill="toself", name=str(row["dir1"])))
                _save(fig, out_dir / f"25_radar_{str(row['dir1']).replace('/', '_')}.html", outputs)

            kpi = pd.DataFrame(
                [
                    {"metric": "total_loc", "value": float(m.get("CountLineCode", pd.Series(dtype=float)).sum())},
                    {"metric": "avg_cyclomatic", "value": float(m.get("AvgCyclomatic", pd.Series(dtype=float)).mean())},
                    {"metric": "high_risk_files", "value": float((q["risk_score"] > q["risk_score"].quantile(0.9)).sum())},
                ]
            )
            _save(px.bar(kpi, x="metric", y="value"), out_dir / "26_kpi_cards_like.html", outputs)

            # sankey-like using sunburst fallback for compatibility
            if not cloc.empty and "filename" in cloc.columns and "language" in cloc.columns:
                s = cloc.copy()
                s["filename"] = s["filename"].astype(str)
                s["dir1"] = s["filename"].str.split("/").str[0].replace("", "root")
                lang_dir = s.groupby(["dir1", "language"], dropna=False)["code"].sum().reset_index()
                _save(px.sunburst(lang_dir, path=["dir1", "language"], values="code"), out_dir / "19_sankey_like_dir_lang.html", outputs)
        else:
            notes.append("Merged UND/PMD charts skipped")

        # Time-series related charts if history is present
        hist = inputs.output_dir / "history_metrics.csv"
        if hist.exists():
            h = pd.read_csv(hist)
            if "date" in h.columns:
                for col, fname in [("CountLineCode", "28_trend_loc.html"), ("AvgCyclomatic", "28_trend_cyclomatic.html"), ("PmdCloneRatio", "28_trend_clone_ratio.html")]:
                    if col in h.columns:
                        _save(px.line(h, x="date", y=col), out_dir / fname, outputs)
                if "AvgCyclomatic" in h.columns:
                    avg = h["AvgCyclomatic"].mean()
                    std = h["AvgCyclomatic"].std()
                    fig = px.line(h, x="date", y="AvgCyclomatic")
                    fig.add_hline(y=avg + 2 * std, line_dash="dash")
                    fig.add_hline(y=avg - 2 * std, line_dash="dash")
                    _save(fig, out_dir / "29_control_chart_cyclomatic.html", outputs)
                if "CountLineCode" in h.columns:
                    h2 = h.sort_values("date")
                    h2["delta"] = h2["CountLineCode"].diff().fillna(0)
                    _save(px.bar(h2, x="date", y="delta"), out_dir / "30_waterfall_like_delta_loc.html", outputs)
        else:
            notes.append("time-series charts skipped (history_metrics.csv not found)")

        return TaskResult(
            name="visualize",
            executed=True,
            success=True,
            outputs=outputs,
            message=f"advanced visualization completed ({len(outputs)} files). {'; '.join(notes)}",
        )
    except Exception as exc:
        return TaskResult(name="visualize", executed=True, success=False, outputs=outputs, message=f"visualization failed: {exc}")
