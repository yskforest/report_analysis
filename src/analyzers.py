from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
import pandas as pd

from io_models import AnalysisInputs, TaskResult, clean_path, _safe_num, _normalize_paths


def run_understand(inputs: AnalysisInputs) -> TaskResult:
    if inputs.und_csv is None:
        return TaskResult(name="und", executed=False, success=True, message="UND skipped")

    out_und = inputs.output_dir / "und"
    out_und.mkdir(parents=True, exist_ok=True)

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

        summary_metrics = {
            "und_FileCount": file_count,
            "und_CountLineCode": code_sum,
            "und_CountLine": line_sum,
            "und_CountLineComment": comment_sum,
            "und_RatioCommentToCode": (comment_sum / code_sum * 100) if code_sum else 0,
        }

        return TaskResult(
            name="und",
            executed=True,
            success=True,
            outputs=[file_csv, func_csv, class_csv],
            summary_metrics=summary_metrics,
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

        summary_metrics = {
            "cloc_CountLineCode": int(_safe_num(f["code"]).sum()),
            "cloc_CountLineComment": int(_safe_num(f["comment"]).sum()),
            "cloc_CountLineBlank": int(_safe_num(f["blank"]).sum()),
            "cloc_Files": int(len(f.index)),
        }

        return TaskResult(
            name="cloc",
            executed=True,
            success=True,
            outputs=[filtered_csv],
            summary_metrics=summary_metrics,
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

        summary_metrics = {
            "pmd_TotalFileTokens": total_tokens,
            "pmd_CloneUniqueTokens": clone_tokens,
            "pmd_CloneRatio": clone_ratio,
        }

        return TaskResult(
            name="pmd",
            executed=True,
            success=True,
            outputs=[ratio_csv],
            summary_metrics=summary_metrics,
            message="PMD completed",
        )
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
        
        summary_metrics = {
            "git_AddedLines": int(df["AddedLines"].sum()) if not df.empty else 0,
            "git_DeletedLines": int(df["DeletedLines"].sum()) if not df.empty else 0,
            "git_ChangedLines": int(df["ChangedLines"].sum()) if not df.empty else 0,
            "git_Files": int(len(df.index)),
        }
        
        return TaskResult(
            name="git",
            executed=True,
            success=True,
            outputs=[],
            summary_metrics=summary_metrics,
            message="Git diff integration completed",
        )
    except Exception as exc:
        return TaskResult(name="git", executed=True, success=False, message=f"Git diff integration failed: {exc}")


def run_comprehensive_merge(inputs: AnalysisInputs) -> TaskResult:
    out_file = inputs.output_dir / "metrics_merge.csv"
    try:
        merged_df = None
        dfs_to_merge = []
        
        # 1. Understand
        und_csv = inputs.output_dir / "und" / "und_file.csv"
        if und_csv.exists():
            dfs_to_merge.append((pd.read_csv(und_csv, dtype=object, na_filter=False), "und", "File"))
            
        # 2. Threshold Check
        df_thresh = inputs.shared_dfs.get("threshold_summary")
        if df_thresh is not None:
            dfs_to_merge.append((df_thresh.copy(), "und", "File"))
        else:
            thresh_csv = inputs.output_dir / "und" / "threshold_exceeded_summary.csv"
            if thresh_csv.exists():
                dfs_to_merge.append((pd.read_csv(thresh_csv, dtype=object, na_filter=False), "und", "File"))
                
        # 3. CLOC
        cloc_csv = inputs.output_dir / "cloc" / "cloc_filtered.csv"
        if cloc_csv.exists():
            dfs_to_merge.append((pd.read_csv(cloc_csv, dtype=object, na_filter=False), "cloc", "filename"))
            
        # 4. PMD
        pmd_csv = inputs.output_dir / "pmd" / "pmd_clone_ratio.csv"
        if pmd_csv.exists():
            dfs_to_merge.append((pd.read_csv(pmd_csv, dtype=object, na_filter=False), "pmd", "File"))
            
        # 5. Git
        df_git = inputs.shared_dfs.get("git")
        if df_git is not None:
            dfs_to_merge.append((df_git.copy(), "git", "File"))
        else:
            git_csv = inputs.output_dir / "git" / "git_diff_file_metrics.csv"
            if git_csv.exists():
                dfs_to_merge.append((pd.read_csv(git_csv, dtype=object, na_filter=False), "git", "File"))
                
        for df, prefix, key_col in dfs_to_merge:
            if df.empty or key_col not in df.columns:
                continue
            if key_col != "File":
                df = df.rename(columns={key_col: "File"})
            df = df.rename(columns={c: f"{prefix}_{c}" for c in df.columns if c != "File"})
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


def run_threshold_check(inputs: AnalysisInputs) -> TaskResult:
    if inputs.und_csv is None or not inputs.thresholds:
        return TaskResult(
            name="threshold_check",
            executed=False,
            success=True,
            message="Threshold check skipped (no und_csv or thresholds configured)",
        )

    out_und = inputs.output_dir / "und"
    out_und.mkdir(parents=True, exist_ok=True)

    try:
        if "und" in inputs.shared_dfs:
            df = inputs.shared_dfs["und"]
        else:
            df = pd.read_csv(inputs.und_csv, dtype=object, na_filter=False)
            df = _normalize_paths(df, ["File", "LongName"], inputs.remove_path_prefix)
            inputs.shared_dfs["und"] = df

        kind_col = df["Kind"].astype(str) if "Kind" in df.columns else pd.Series([""] * len(df))
        func_df = df[kind_col.str.contains("Function|Method", na=False)].copy()

        valid_metrics = [m for m in inputs.thresholds if m in func_df.columns]

        functions_csv = out_und / "threshold_exceeded_functions.csv"
        summary_csv = out_und / "threshold_exceeded_summary.csv"
        dir_summary_csv = out_und / "threshold_exceeded_dir_summary.csv"

        if not valid_metrics or func_df.empty:
            empty_cols = ["File", "total_functions"] + [f"{m}_exceeded_count" for m in inputs.thresholds] + ["total_exceeded_count", "exceeded_ratio"]
            pd.DataFrame(columns=empty_cols).to_csv(summary_csv, index=False)
            pd.DataFrame(columns=["File", "Name", "Kind"] + list(inputs.thresholds.keys()) + ["exceeded_metrics"]).to_csv(functions_csv, index=False)
            pd.DataFrame(columns=["Dir", "total_functions"] + [f"{m}_exceeded_count" for m in inputs.thresholds] + ["total_exceeded_count", "exceeded_ratio"]).to_csv(dir_summary_csv, index=False)
            return TaskResult(
                name="threshold_check",
                executed=True,
                success=True,
                outputs=[summary_csv, functions_csv, dir_summary_csv],
                message="Threshold check completed (no functions or valid metrics found)",
            )

        for metric in valid_metrics:
            func_df[metric] = _safe_num(func_df[metric])

        exceeded_df = pd.DataFrame(index=func_df.index)
        for metric in valid_metrics:
            exceeded_df[metric] = func_df[metric] > inputs.thresholds[metric]

        exceeded_mask = exceeded_df.any(axis=1)
        func_df["exceeded_metrics"] = exceeded_df.apply(lambda r: ",".join([m for m in valid_metrics if r[m]]), axis=1)

        exceeded_funcs_df = func_df[exceeded_mask][["File", "Name", "Kind"] + valid_metrics + ["exceeded_metrics"]].copy()
        exceeded_funcs_df.to_csv(functions_csv, index=False)

        func_df["File"] = func_df["File"].astype(str)
        file_total_funcs = func_df.groupby("File").size().reset_index(name="total_functions")

        summary_df = file_total_funcs
        for metric in valid_metrics:
            counts = func_df[exceeded_df[metric]].groupby("File").size().reset_index(name=f"{metric}_exceeded_count")
            summary_df = summary_df.merge(counts, on="File", how="left")

        file_total_exceeded = func_df[exceeded_mask].groupby("File").size().reset_index(name="total_exceeded_count")
        summary_df = summary_df.merge(file_total_exceeded, on="File", how="left")

        for col in summary_df.columns:
            if col != "File":
                summary_df[col] = summary_df[col].fillna(0).astype(int)

        summary_cols = ["File", "total_functions"] + [f"{m}_exceeded_count" for m in valid_metrics] + ["total_exceeded_count"]
        summary_df = summary_df[summary_cols]
        summary_df.to_csv(summary_csv, index=False)

        dir_data = {}
        for _, row in summary_df.iterrows():
            file_parts = row["File"].replace("\\", "/").strip("/").split("/")
            for i in range(1, len(file_parts)):
                ancestor = "/".join(file_parts[:i])
                d = dir_data.setdefault(ancestor, {"total_functions": 0, "total_exceeded_count": 0})
                d["total_functions"] += row["total_functions"]
                d["total_exceeded_count"] += row["total_exceeded_count"]
                for m in valid_metrics:
                    col = f"{m}_exceeded_count"
                    d[col] = d.get(col, 0) + row[col]

        dir_rows = []
        all_row = {"Dir": "ALL_FILES", "total_functions": int(summary_df["total_functions"].sum()), "total_exceeded_count": int(summary_df["total_exceeded_count"].sum())}
        for m in valid_metrics:
            all_row[f"{m}_exceeded_count"] = int(summary_df[f"{m}_exceeded_count"].sum())
        dir_rows.append(all_row)

        for ancestor, metrics in sorted(dir_data.items()):
            row = {"Dir": ancestor, "total_functions": metrics["total_functions"], "total_exceeded_count": metrics["total_exceeded_count"]}
            for m in valid_metrics:
                col = f"{m}_exceeded_count"
                row[col] = metrics[col]
            dir_rows.append(row)

        dir_summary_df = pd.DataFrame(dir_rows)
        for df in [summary_df, dir_summary_df]:
            df["exceeded_ratio"] = (df["total_exceeded_count"] / df["total_functions"]).fillna(0.0)

        # Re-save with ratio included
        summary_cols = ["File", "total_functions"] + [f"{m}_exceeded_count" for m in valid_metrics] + ["total_exceeded_count", "exceeded_ratio"]
        summary_df[summary_cols].to_csv(summary_csv, index=False)

        dir_cols = ["Dir", "total_functions"] + [f"{m}_exceeded_count" for m in valid_metrics] + ["total_exceeded_count", "exceeded_ratio"]
        dir_summary_df[dir_cols].to_csv(dir_summary_csv, index=False)

        inputs.shared_dfs["threshold_summary"] = summary_df.copy()

        return TaskResult(
            name="threshold_check",
            executed=True,
            success=True,
            outputs=[summary_csv, functions_csv, dir_summary_csv],
            message=f"threshold check completed: found {len(exceeded_funcs_df)} functions exceeding thresholds",
        )
    except Exception as exc:
        return TaskResult(
            name="threshold_check",
            executed=True,
            success=False,
            message=f"threshold check failed: {exc}",
        )


def write_global_summary(inputs: AnalysisInputs, results: list[TaskResult]) -> Path:
    out = inputs.output_dir / "summary.csv"
    rows = []
    for r in results:
        row = {"Task": r.name, "Executed": r.executed, "Success": r.success, "Outputs": len(r.outputs), "Message": r.message}
        row.update(r.summary_metrics)
        rows.append(row)
    pd.DataFrame(rows).fillna("").to_csv(out, index=False)
    return out
