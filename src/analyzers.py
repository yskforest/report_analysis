from __future__ import annotations

import csv
import os
import xml.etree.ElementTree as ET
from pathlib import Path
import shutil

import pandas as pd

from io_models import AnalysisInputs, TaskResult, clean_path
from plotly_visualize import write_pie_chart, write_treemap_by_path


def _normalize_paths(df: pd.DataFrame, columns: list[str], remove_prefix: str) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            continue
        out[col] = out[col].map(lambda val: clean_path(val, remove_prefix))
    return out


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _build_hierarchy_agg(df: pd.DataFrame, path_col: str, max_level: int | None = None) -> pd.DataFrame:
    work = df.copy()
    work[path_col] = work[path_col].astype(str).str.replace("\\\\", "/", regex=False).str.strip("/")
    parts = work[path_col].str.split("/")
    depth = int(parts.map(len).max()) if len(work.index) else 0
    use_depth = min(depth, max_level) if max_level is not None else depth

    rows: list[pd.DataFrame] = []
    total_row = pd.DataFrame(
        [
            {
                "Level": 0,
                "Path": "ALL_FILES",
                "SourceLines": int(_safe_num(work["SourceLines"]).sum()),
                "TotalLines": int(_safe_num(work["TotalLines"]).sum()),
                "CommentLines": int(_safe_num(work["CommentLines"]).sum()),
                "FileCount": int(len(work.index)),
            }
        ]
    )
    rows.append(total_row)

    for i in range(1, use_depth + 1):
        key = parts.map(lambda x: "/".join(x[:i]) if len(x) >= i else "")
        tmp = work.copy()
        tmp["Path"] = key.replace("", "root")
        agg = (
            tmp.groupby("Path", dropna=False)[["SourceLines", "TotalLines", "CommentLines"]]
            .sum(numeric_only=True)
            .reset_index()
        )
        file_count = tmp.groupby("Path", dropna=False).size().reset_index(name="FileCount")
        agg = agg.merge(file_count, on="Path", how="left")
        agg.insert(0, "Level", i)
        agg = agg.sort_values(by=["SourceLines", "TotalLines"], ascending=False)
        rows.append(agg)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def run_file_metrics_excel(inputs: AnalysisInputs) -> TaskResult:
    out_file = inputs.output_dir / "file_metrics_hierarchy.xlsx"
    try:
        max_level = int(os.getenv("FILE_METRICS_MAX_LEVEL", "8"))
        if max_level < 0:
            max_level = 8

        metrics = pd.DataFrame()
        und_csv = inputs.output_dir / "und" / "und_file.csv"
        source_name = "understand"

        if und_csv.exists():
            u = pd.read_csv(und_csv, dtype=object, na_filter=False)
            if {"File", "CountLineCode", "CountLineComment", "CountLine"}.issubset(u.columns):
                metrics = pd.DataFrame(
                    {
                        "File": u["File"].astype(str),
                        "SourceLines": _safe_num(u["CountLineCode"]),
                        "CommentLines": _safe_num(u["CountLineComment"]),
                        "TotalLines": _safe_num(u["CountLine"]),
                    }
                )

        if metrics.empty:
            return TaskResult(
                name="file_metrics_excel",
                executed=False,
                success=True,
                message="file metrics excel skipped (no usable understand file metrics)",
            )

        metrics = _normalize_paths(metrics, ["File"], inputs.remove_path_prefix)
        metrics = metrics[metrics["File"].astype(str) != ""].copy()
        # Exclude hidden files such as Open3D/.codacy.yml
        metrics = metrics[
            ~metrics["File"]
            .astype(str)
            .str.split("/")
            .map(lambda parts: any(part.startswith(".") for part in parts if part))
        ].copy()
        metrics["SourceLines"] = _safe_num(metrics["SourceLines"])
        metrics["CommentLines"] = _safe_num(metrics["CommentLines"])
        metrics["TotalLines"] = _safe_num(metrics["TotalLines"])
        metrics = metrics.sort_values(by=["SourceLines", "TotalLines"], ascending=False)

        # Aggregate by directory hierarchy only (exclude per-file rows)
        metrics["Dir"] = metrics["File"].astype(str).map(lambda p: str(Path(p).parent).replace("\\", "/"))
        metrics["Dir"] = metrics["Dir"].replace(".", "").str.strip("/")
        metrics = metrics[metrics["Dir"] != ""].copy()

        hierarchy = _build_hierarchy_agg(metrics, "Dir", max_level=max_level)
        summary = pd.DataFrame(
            [
                {
                    "Source": source_name,
                    "MaxLevel": max_level,
                    "Rows": int(len(metrics.index)),
                    "TotalSourceLines": int(metrics["SourceLines"].sum()),
                    "TotalLines": int(metrics["TotalLines"].sum()),
                    "TotalCommentLines": int(metrics["CommentLines"].sum()),
                }
            ]
        )

        with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
            summary.to_excel(writer, sheet_name="summary", index=False)
            hierarchy.to_excel(writer, sheet_name="hierarchy", index=False)

        return TaskResult(
            name="file_metrics_excel",
            executed=True,
            success=True,
            outputs=[out_file],
            message=f"file metrics excel generated ({out_file.name})",
        )
    except Exception as exc:
        return TaskResult(
            name="file_metrics_excel",
            executed=True,
            success=False,
            message=f"file metrics excel failed: {exc}",
        )


def _split_path_levels(series: pd.Series, max_level: int = 15) -> pd.DataFrame:
    clean = series.astype(str).str.replace("\\\\", "/", regex=False).str.strip("/")
    parts = clean.str.split("/")
    level_cols: dict[str, pd.Series] = {}
    for i in range(max_level + 1):
        level_cols[f"Level{i}"] = parts.map(lambda xs: xs[i] if isinstance(xs, list) and len(xs) > i else "")
    return pd.DataFrame(level_cols, index=series.index)


def _distribution(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col not in df.columns:
        return pd.DataFrame(columns=[col, "Count"])
    s = _safe_num(df[col]).round(0).astype(int)
    out = s.value_counts(dropna=False).sort_index().reset_index()
    out.columns = [col, "Count"]
    return out


def run_func_metrics_excel(inputs: AnalysisInputs) -> TaskResult:
    out_file = inputs.output_dir / "func_metrics.xlsx"
    try:
        und_func_csv = inputs.output_dir / "und" / "und_func.csv"
        if not und_func_csv.exists():
            return TaskResult(
                name="func_metrics_excel",
                executed=False,
                success=True,
                message="func metrics excel skipped (und_func.csv not found)",
            )

        f = pd.read_csv(und_func_csv, dtype=object, na_filter=False)
        if f.empty or "File" not in f.columns:
            return TaskResult(
                name="func_metrics_excel",
                executed=False,
                success=True,
                message="func metrics excel skipped (no usable function rows)",
            )

        f = _normalize_paths(f, ["File"], inputs.remove_path_prefix)
        f = f[f["File"].astype(str) != ""].copy()
        f = f[
            ~f["File"].astype(str).str.split("/").map(lambda parts: any(part.startswith(".") for part in parts if part))
        ].copy()
        if f.empty:
            return TaskResult(
                name="func_metrics_excel",
                executed=False,
                success=True,
                message="func metrics excel skipped (all rows filtered)",
            )

        level_df = _split_path_levels(f["File"], max_level=15)
        out_df = pd.concat([f.reset_index(drop=True), level_df.reset_index(drop=True)], axis=1)
        for c in ["MaxNesting", "Cyclomatic", "Essential"]:
            if c in out_df.columns:
                out_df[c] = _safe_num(out_df[c])

        agg_keys = [f"Level{i}" for i in range(16)]
        agg_map: dict[str, tuple[str, str]] = {"FunctionCount": ("File", "size")}
        if "MaxNesting" in out_df.columns:
            agg_map["MaxNesting_Avg"] = ("MaxNesting", "mean")
        if "Cyclomatic" in out_df.columns:
            agg_map["Cyclomatic_Avg"] = ("Cyclomatic", "mean")
        if "Essential" in out_df.columns:
            agg_map["Essential_Avg"] = ("Essential", "mean")
        agg_df = out_df.groupby(agg_keys, dropna=False).agg(**agg_map).reset_index()
        for c in ["MaxNesting_Avg", "Cyclomatic_Avg", "Essential_Avg"]:
            if c in agg_df.columns:
                agg_df[c] = pd.to_numeric(agg_df[c], errors="coerce").round(3)

        dist_maxnesting = _distribution(out_df, "MaxNesting")
        dist_cyclomatic = _distribution(out_df, "Cyclomatic")
        dist_essential = _distribution(out_df, "Essential")

        summary_row = {
            "Rows": int(len(out_df.index)),
            "UniqueFiles": int(out_df["File"].nunique()),
            "UniqueLevel0": int(out_df["Level0"].nunique()),
        }
        if "MaxNesting" in out_df.columns:
            summary_row["MaxNestingMean"] = float(_safe_num(out_df["MaxNesting"]).mean())
        if "Cyclomatic" in out_df.columns:
            summary_row["CyclomaticMean"] = float(_safe_num(out_df["Cyclomatic"]).mean())
        if "Essential" in out_df.columns:
            summary_row["EssentialMean"] = float(_safe_num(out_df["Essential"]).mean())
        summary_df = pd.DataFrame([summary_row])

        with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
            summary_df.to_excel(writer, sheet_name="summary", index=False)
            out_df.to_excel(writer, sheet_name="functions_with_levels", index=False)
            agg_df.to_excel(writer, sheet_name="level_agg", index=False)
            dist_maxnesting.to_excel(writer, sheet_name="dist_maxnesting", index=False)
            dist_cyclomatic.to_excel(writer, sheet_name="dist_cyclomatic", index=False)
            dist_essential.to_excel(writer, sheet_name="dist_essential", index=False)

        return TaskResult(
            name="func_metrics_excel",
            executed=True,
            success=True,
            outputs=[out_file],
            message=f"func metrics excel generated ({out_file.name})",
        )
    except Exception as exc:
        return TaskResult(
            name="func_metrics_excel",
            executed=True,
            success=False,
            message=f"func metrics excel failed: {exc}",
        )


def run_understand(inputs: AnalysisInputs) -> TaskResult:
    if inputs.und_csv is None:
        return TaskResult(name="und", executed=False, success=True, message="UND skipped")

    out_und = inputs.output_dir / "und"
    out_plot = out_und
    out_und.mkdir(parents=True, exist_ok=True)
    out_plot.mkdir(parents=True, exist_ok=True)

    try:
        df = pd.read_csv(inputs.und_csv, dtype=object, na_filter=False)
        df = _normalize_paths(df, ["File", "LongName"], inputs.remove_path_prefix)
        inputs.shared_dfs["und"] = df

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

        return TaskResult(
            name="und",
            executed=True,
            success=True,
            outputs=[file_csv, func_csv, class_csv, summary_csv],
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
        f["filename"] = f["filename"].map(lambda p: clean_path(p, inputs.remove_path_prefix))

        filtered_csv = out_cloc / "cloc_filtered.csv"
        f[required].to_csv(filtered_csv, index=False)

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
            outputs=[filtered_csv, summary_csv],
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

        outputs = [ratio_csv, summary_csv]
        if pmd_summary_out and pmd_summary_out.exists():
            outputs.append(pmd_summary_out)
        return TaskResult(name="pmd", executed=True, success=True, outputs=outputs, message="PMD completed")
    except Exception as exc:
        return TaskResult(name="pmd", executed=True, success=False, message=f"PMD failed: {exc}")


def run_git_numstat(inputs: AnalysisInputs) -> TaskResult:
    if inputs.git_numstat is None:
        return TaskResult(name="git", executed=False, success=True, message="Git diff skipped")

    out_git = inputs.output_dir / "git"
    out_git.mkdir(parents=True, exist_ok=True)

    try:
        rows = []
        with open(inputs.git_numstat, "r", encoding="utf-8", errors="replace") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(None, 2)
                if len(parts) < 3:
                    continue
                added_raw, deleted_raw, file_raw = parts
                
                added = 0 if added_raw == "-" else int(added_raw)
                deleted = 0 if deleted_raw == "-" else int(deleted_raw)
                
                rows.append({
                    "File": clean_path(file_raw, inputs.remove_path_prefix),
                    "AddedLines": added,
                    "DeletedLines": deleted,
                })
        
        df = pd.DataFrame(rows)
        if df.empty:
            df = pd.DataFrame(columns=["File", "AddedLines", "DeletedLines", "ChangedLines"])
        else:
            df = df.groupby("File", dropna=False)[["AddedLines", "DeletedLines"]].sum().reset_index()
            df["ChangedLines"] = df["AddedLines"] + df["DeletedLines"]
            df = df.sort_values(by="ChangedLines", ascending=False)
            
        inputs.shared_dfs["git"] = df
        
        summary_csv = out_git / "git_diff_summary.csv"
        summary_df = pd.DataFrame([{
            "CountFilesChanged": int(len(df.index)),
            "TotalAddedLines": int(df["AddedLines"].sum()) if not df.empty else 0,
            "TotalDeletedLines": int(df["DeletedLines"].sum()) if not df.empty else 0,
            "TotalChangedLines": int(df["ChangedLines"].sum()) if not df.empty else 0,
        }])
        summary_df.to_csv(summary_csv, index=False)
        
        return TaskResult(
            name="git",
            executed=True,
            success=True,
            outputs=[summary_csv],
            message="Git diff integration completed",
        )
    except Exception as exc:
        return TaskResult(name="git", executed=True, success=False, message=f"Git diff integration failed: {exc}")


def run_comprehensive_merge(inputs: AnalysisInputs) -> TaskResult:
    out_file = inputs.output_dir / "metrics_merge.csv"
    try:
        merged_df = None
        
        # 1. Understand
        und_csv = inputs.output_dir / "und" / "und_file.csv"
        if und_csv.exists():
            df = pd.read_csv(und_csv, dtype=object, na_filter=False)
            if not df.empty and "File" in df.columns:
                df.rename(columns={c: f"und_{c}" for c in df.columns if c != "File"}, inplace=True)
                merged_df = df
                
        # 2. CLOC
        cloc_csv = inputs.output_dir / "cloc" / "cloc_filtered.csv"
        if cloc_csv.exists():
            df = pd.read_csv(cloc_csv, dtype=object, na_filter=False)
            if not df.empty and "filename" in df.columns:
                df.rename(columns={"filename": "File"}, inplace=True)
                df.rename(columns={c: f"cloc_{c}" for c in df.columns if c != "File"}, inplace=True)
                if merged_df is None:
                    merged_df = df
                else:
                    merged_df = pd.merge(merged_df, df, on="File", how="outer")
                    
        # 3. PMD
        pmd_csv = inputs.output_dir / "pmd" / "pmd_clone_ratio.csv"
        if pmd_csv.exists():
            df = pd.read_csv(pmd_csv, dtype=object, na_filter=False)
            if not df.empty and "File" in df.columns:
                df.rename(columns={c: f"pmd_{c}" for c in df.columns if c != "File"}, inplace=True)
                if merged_df is None:
                    merged_df = df
                else:
                    merged_df = pd.merge(merged_df, df, on="File", how="outer")
                    
        # 4. Git Diff
        df_git = inputs.shared_dfs.get("git")
        if df_git is not None:
            df = df_git.copy()
            if not df.empty and "File" in df.columns:
                df.rename(columns={c: f"git_{c}" for c in df.columns if c != "File"}, inplace=True)
                if merged_df is None:
                    merged_df = df
                else:
                    merged_df = pd.merge(merged_df, df, on="File", how="outer")
        else:
            git_csv = inputs.output_dir / "git" / "git_diff_file_metrics.csv"
            if git_csv.exists():
                df = pd.read_csv(git_csv, dtype=object, na_filter=False)
                if not df.empty and "File" in df.columns:
                    df.rename(columns={c: f"git_{c}" for c in df.columns if c != "File"}, inplace=True)
                    if merged_df is None:
                        merged_df = df
                    else:
                        merged_df = pd.merge(merged_df, df, on="File", how="outer")
                    
        if merged_df is None or merged_df.empty:
            return TaskResult(
                name="comprehensive_merge",
                executed=False,
                success=True,
                message="comprehensive merge skipped (no source files found)",
            )
            
        merged_df.to_csv(out_file, index=False)
        return TaskResult(
            name="comprehensive_merge",
            executed=True,
            success=True,
            outputs=[out_file],
            message=f"comprehensive merge generated ({out_file.name})",
        )
    except Exception as exc:
        return TaskResult(
            name="comprehensive_merge",
            executed=True,
            success=False,
            message=f"comprehensive merge failed: {exc}",
        )


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
