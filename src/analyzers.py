from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from io_models import AnalysisInputs, TaskResult
from plotly_visualize import write_pie_chart, write_treemap_by_path


def _normalize_paths(df: pd.DataFrame, columns: list[str], remove_prefix: str) -> pd.DataFrame:
    prefix = (remove_prefix or "").replace("\\", "/")

    def _strip_prefix(value: str) -> str:
        if not prefix or prefix in {"/", "\\"}:
            return value
        return value[len(prefix) :] if value.startswith(prefix) else value

    out = df.copy()
    for col in columns:
        if col not in out.columns:
            continue
        out[col] = out[col].astype(str).str.replace("\\\\", "/", regex=False)
        out[col] = out[col].map(_strip_prefix)
    return out


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def run_understand(inputs: AnalysisInputs) -> TaskResult:
    if inputs.und_csv is None:
        return TaskResult(name="und", executed=False, success=True, message="UND skipped")

    out_und = inputs.output_dir / "und"
    out_plot = inputs.output_dir / "und_python_plot"
    out_und.mkdir(parents=True, exist_ok=True)
    out_plot.mkdir(parents=True, exist_ok=True)

    try:
        df = pd.read_csv(inputs.und_csv, dtype=object, na_filter=False)
        df = _normalize_paths(df, ["File", "LongName"], inputs.remove_path_prefix)

        metrics_csv = out_und / "und_metrics.csv"
        df.to_csv(metrics_csv, index=False)

        kind_col = df["Kind"].astype(str) if "Kind" in df.columns else pd.Series([""] * len(df))
        file_df = df[kind_col.str.contains("File", na=False)].copy()
        func_df = df[kind_col.str.contains("Function", na=False)].copy()
        class_df = df[kind_col.str.contains("Class", na=False)].copy()

        file_csv = out_und / "und_file.csv"
        func_csv = out_und / "und_func.csv"
        class_csv = out_und / "und_class.csv"
        file_df.to_csv(file_csv, index=False)
        func_df.to_csv(func_csv, index=False)
        class_df.to_csv(class_csv, index=False)

        code_sum = int(_safe_num(df.get("CountLineCode", pd.Series(dtype=float))).sum())
        line_sum = int(_safe_num(df.get("CountLine", pd.Series(dtype=float))).sum())
        comment_sum = int(_safe_num(df.get("CountLineComment", pd.Series(dtype=float))).sum())
        file_count = int(len(file_df.index))

        summary = pd.DataFrame(
            [
                {
                    "FileCount": file_count,
                    "CountLineCode": code_sum,
                    "CountLine": line_sum,
                    "CountLineComment": comment_sum,
                    "RatioCommentToCode": (comment_sum / code_sum * 100) if code_sum else 0,
                }
            ]
        )
        summary_csv = inputs.output_dir / "und_summary.csv"
        summary.to_csv(summary_csv, index=False)

        tree_html = out_plot / "UndCountLineCode(Area)-UndRatioCommentToFile(Color)_treemap.html"
        essential_tree_html = out_plot / "CountLineCode(Area)-Essential(FileAverage)_treemap.html"
        cyclomatic_tree_html = out_plot / "CountLineCode(Area)-Cyclomatic(FileAverage)_treemap.html"
        if not file_df.empty and "File" in file_df.columns:
            t = file_df.copy()
            t["CountLineCode"] = _safe_num(t.get("CountLineCode", pd.Series(dtype=float)))
            t["RatioCommentToCode"] = _safe_num(t.get("RatioCommentToCode", pd.Series(dtype=float)))
            write_treemap_by_path(
                t,
                file_col="File",
                size_col="CountLineCode",
                color_col="RatioCommentToCode",
                output_html=tree_html,
                title="UndCountLineCode(Area)-UndRatioCommentToFile(Color)",
                prefix_to_remove=inputs.remove_path_prefix,
            )

            if "AvgEssential" in t.columns:
                t["AvgEssential"] = _safe_num(t["AvgEssential"])
                write_treemap_by_path(
                    t,
                    file_col="File",
                    size_col="CountLineCode",
                    color_col="AvgEssential",
                    output_html=essential_tree_html,
                    title="CountLineCode(Area)-Essential(FileAverage)",
                    prefix_to_remove=inputs.remove_path_prefix,
                )

            if "AvgCyclomatic" in t.columns:
                t["AvgCyclomatic"] = _safe_num(t["AvgCyclomatic"])
                write_treemap_by_path(
                    t,
                    file_col="File",
                    size_col="CountLineCode",
                    color_col="AvgCyclomatic",
                    output_html=cyclomatic_tree_html,
                    title="CountLineCode(Area)-Cyclomatic(FileAverage)",
                    prefix_to_remove=inputs.remove_path_prefix,
                )

        return TaskResult(
            name="und",
            executed=True,
            success=True,
            outputs=[metrics_csv, file_csv, func_csv, class_csv, summary_csv],
            message="UND completed",
        )
    except Exception as exc:
        return TaskResult(name="und", executed=True, success=False, message=f"UND failed: {exc}")


def run_cloc(inputs: AnalysisInputs) -> TaskResult:
    if inputs.cloc_csv is None:
        return TaskResult(name="cloc", executed=False, success=True, message="CLOC skipped")

    out_cloc = inputs.output_dir / "cloc"
    out_cloc.mkdir(parents=True, exist_ok=True)

    try:
        df = pd.read_csv(inputs.cloc_csv)
        required = ["language", "filename", "blank", "comment", "code"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"missing columns: {missing}")

        f = df[df["language"].astype(str) != "SUM"].copy()
        f["filename"] = f["filename"].astype(str).str.replace("\\\\", "/", regex=False)
        if inputs.remove_path_prefix and inputs.remove_path_prefix not in {"/", "\\"}:
            normalized_prefix = inputs.remove_path_prefix.replace("\\", "/")
            f["filename"] = f["filename"].map(
                lambda p: (p[len(normalized_prefix) :] if p.startswith(normalized_prefix) else p)
            )

        filtered_csv = out_cloc / "cloc_filtered.csv"
        f[required].to_csv(filtered_csv, index=False)

        pie_html = out_cloc / "cloc_pie_chart.html"
        p = f.copy()
        p["code"] = _safe_num(p["code"])
        by_lang = p.groupby("language", dropna=False)["code"].sum().reset_index()
        write_pie_chart(
            by_lang,
            value_column="code",
            label_column="language",
            title="Cloc Count Line Code Pie Chart",
            output_html=pie_html,
            exclude_label=None,
        )

        summary_csv = inputs.output_dir / "summary_cloc.csv"
        pd.DataFrame(
            [
                {
                    "CountLineCode": int(_safe_num(f["code"]).sum()),
                    "CountLineComment": int(_safe_num(f["comment"]).sum()),
                    "CountLineBlank": int(_safe_num(f["blank"]).sum()),
                    "Files": int(len(f.index)),
                }
            ]
        ).to_csv(summary_csv, index=False)

        return TaskResult(
            name="cloc",
            executed=True,
            success=True,
            outputs=[filtered_csv, pie_html, summary_csv],
            message="CLOC completed",
        )
    except Exception as exc:
        return TaskResult(name="cloc", executed=True, success=False, message=f"CLOC failed: {exc}")


def _parse_pmd_file(xml_file: Path, min_lines: int = 10) -> pd.DataFrame:
    tree = ET.parse(xml_file)
    root = tree.getroot()

    tokens_by_file: dict[str, int] = {}
    clone_token_sets: dict[str, set[int]] = {}

    for f in root.findall(".//{*}file"):
        path = f.attrib.get("path", "")
        total = int(f.attrib.get("totalNumberOfTokens", "0"))
        tokens_by_file[path] = tokens_by_file.get(path, 0) + total
        clone_token_sets.setdefault(path, set())

    for d in root.findall(".//{*}duplication"):
        lines = int(d.attrib.get("lines", "0"))
        tokens = int(d.attrib.get("tokens", "0"))
        if lines < min_lines:
            continue
        for file_node in d.findall(".//{*}file"):
            path = file_node.attrib.get("path", "")
            begin = int(file_node.attrib.get("begintoken", "0"))
            s = clone_token_sets.setdefault(path, set())
            for i in range(begin, begin + tokens):
                s.add(i)

    rows = []
    for path, total in tokens_by_file.items():
        clone = len(clone_token_sets.get(path, set()))
        ratio = (clone / total * 100) if total else 0
        rows.append(
            {
                "File": path,
                "PmdTotalTokens": total,
                "PmdCloneTokensSum": clone,
                "PmdCloneRatio": ratio,
            }
        )
    return pd.DataFrame(rows)


def run_pmd(inputs: AnalysisInputs) -> TaskResult:
    if not inputs.pmd_xmls:
        return TaskResult(name="pmd", executed=False, success=True, message="PMD skipped")

    out_pmd = inputs.output_dir / "pmd"
    out_pmd.mkdir(parents=True, exist_ok=True)

    try:
        frames = []
        for xml in inputs.pmd_xmls:
            frames.append(_parse_pmd_file(xml))
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        if df.empty:
            return TaskResult(name="pmd", executed=True, success=True, message="PMD completed (no records)")

        df = _normalize_paths(df, ["File"], inputs.remove_path_prefix)
        df = (
            df.groupby("File", dropna=False)[["PmdTotalTokens", "PmdCloneTokensSum"]]
            .sum(numeric_only=True)
            .reset_index()
        )
        df["PmdCloneRatio"] = df.apply(
            lambda r: (r["PmdCloneTokensSum"] / r["PmdTotalTokens"] * 100) if r["PmdTotalTokens"] else 0,
            axis=1,
        )
        df = df.sort_values(by="PmdCloneRatio", ascending=False)

        ratio_csv = out_pmd / "pmd_clone_ratio.csv"
        df.to_csv(ratio_csv, index=False)

        total_tokens = int(_safe_num(df["PmdTotalTokens"]).sum())
        clone_tokens = int(_safe_num(df["PmdCloneTokensSum"]).sum())
        clone_ratio = (clone_tokens / total_tokens * 100) if total_tokens else 0

        summary_csv = out_pmd / "pmd_clone_ratio_summary.csv"
        pd.DataFrame(
            [
                {
                    "TotalFileTokens": total_tokens,
                    "CloneUniqueTokens": clone_tokens,
                    "CloneRatio": clone_ratio,
                }
            ]
        ).to_csv(summary_csv, index=False)

        tree_html = out_pmd / "PmdCloneTokens(Area)-PmdCloneRatio(Color)_treemap.html"
        t = df[df["PmdTotalTokens"] > 0].copy()
        write_treemap_by_path(
            t,
            file_col="File",
            size_col="PmdTotalTokens",
            color_col="PmdCloneRatio",
            output_html=tree_html,
            title="PmdCloneTokens(Area)-PmdCloneRatio(Color)",
            prefix_to_remove=inputs.remove_path_prefix,
        )

        merge_out = None
        pmd_summary_out = None
        if inputs.und_csv is not None:
            und_df = pd.read_csv(inputs.und_csv, dtype=object, na_filter=False)
            und_df = _normalize_paths(und_df, ["File"], inputs.remove_path_prefix)
            if "Kind" in und_df.columns:
                und_df = und_df[und_df["Kind"].astype(str).str.contains("File", na=False)].copy()
            keep_cols = [
                c
                for c in [
                    "File",
                    "CountLineCode",
                    "CountLine",
                    "CountLineComment",
                    "RatioCommentToCode",
                    "AvgCyclomatic",
                    "AvgEssential",
                ]
                if c in und_df.columns
            ]
            und_df = und_df[keep_cols].copy()

            merged = und_df.merge(df, how="outer", on="File")
            merge_out = inputs.output_dir / "und_pmd_merge.csv"
            merged.to_csv(merge_out, index=False)

            pmd_summary_out = inputs.output_dir / "pmd_summary.csv"
            pd.DataFrame(
                [
                    {
                        "CountLineCode": int(_safe_num(merged.get("CountLineCode", pd.Series(dtype=float))).sum()),
                        "CountLine": int(_safe_num(merged.get("CountLine", pd.Series(dtype=float))).sum()),
                        "CountLineComment": int(
                            _safe_num(merged.get("CountLineComment", pd.Series(dtype=float))).sum()
                        ),
                        "PmdTotalTokens": int(_safe_num(merged.get("PmdTotalTokens", pd.Series(dtype=float))).sum()),
                        "PmdCloneTokensSum": int(
                            _safe_num(merged.get("PmdCloneTokensSum", pd.Series(dtype=float))).sum()
                        ),
                    }
                ]
            ).to_csv(pmd_summary_out, index=False)

        outputs = [ratio_csv, summary_csv, tree_html]
        if merge_out and merge_out.exists():
            outputs.append(merge_out)
        if pmd_summary_out and pmd_summary_out.exists():
            outputs.append(pmd_summary_out)
        return TaskResult(name="pmd", executed=True, success=True, outputs=outputs, message="PMD completed")
    except Exception as exc:
        return TaskResult(name="pmd", executed=True, success=False, message=f"PMD failed: {exc}")


def write_global_summary(inputs: AnalysisInputs, results: list[TaskResult]) -> Path:
    out = inputs.output_dir / "summary_report.csv"
    rows = [
        {
            "Task": r.name,
            "Executed": r.executed,
            "Success": r.success,
            "Outputs": len(r.outputs),
            "Message": r.message,
        }
        for r in results
    ]
    with out.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=["Task", "Executed", "Success", "Outputs", "Message"])
        writer.writeheader()
        writer.writerows(rows)
    return out
