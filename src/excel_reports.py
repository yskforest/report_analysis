from __future__ import annotations

import os
from pathlib import Path
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from io_models import AnalysisInputs, TaskResult, _safe_num, _normalize_paths


def _build_hierarchy_agg(df: pd.DataFrame, path_col: str, max_level: int) -> pd.DataFrame:
    work = df.copy()
    work[path_col] = work[path_col].astype(str).str.replace("\\\\", "/", regex=False).str.strip("/")
    parts = work[path_col].str.split("/")
    depth = int(parts.map(len).max()) if len(work) else 0
    use_depth = min(depth, max_level)

    rows = [{
        "Level": 0,
        "Path": "ALL_FILES",
        "SourceLines": int(work["SourceLines"].sum()),
        "TotalLines": int(work["TotalLines"].sum()),
        "CommentLines": int(work["CommentLines"].sum()),
        "FileCount": len(work),
    }]

    for i in range(1, use_depth + 1):
        tmp = work.copy()
        tmp["Path"] = parts.map(lambda x: "/".join(x[:i]) if len(x) >= i else "").replace("", "root")
        agg = tmp.groupby("Path", dropna=False).agg(
            SourceLines=("SourceLines", "sum"),
            TotalLines=("TotalLines", "sum"),
            CommentLines=("CommentLines", "sum"),
            FileCount=("SourceLines", "size")
        ).reset_index()
        agg.insert(0, "Level", i)
        agg = agg.sort_values(by=["SourceLines", "TotalLines"], ascending=False)
        rows.extend(agg.to_dict("records"))

    return pd.DataFrame(rows)


def _split_path_levels(series: pd.Series, max_level: int = 15) -> pd.DataFrame:
    parts = series.astype(str).str.replace("\\\\", "/", regex=False).str.strip("/").str.split("/")
    return pd.DataFrame({
        f"Level{i}": parts.map(lambda x: x[i] if len(x) > i else "")
        for i in range(max_level + 1)
    }, index=series.index)


def _distribution(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col not in df.columns:
        return pd.DataFrame(columns=[col, "Count"])
    s = _safe_num(df[col]).round(0).astype(int)
    out = s.value_counts(dropna=False).sort_index().reset_index()
    out.columns = [col, "Count"]
    return out


def _apply_common_styles(ws: openpyxl.worksheet.worksheet.Worksheet, has_header: bool = True, freeze_panes: str | None = None, enable_filter: bool = True) -> None:
    # ヘッダー背景色: ディープネイビー (#1F4E79)、文字: 白太字
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    
    max_row = ws.max_row
    max_col = ws.max_column
    
    # 1. ヘッダーの装飾とオートフィルター適用
    if has_header and max_row >= 1:
        for c in range(1, max_col + 1):
            cell = ws.cell(row=1, column=c)
            cell.fill = header_fill
            cell.font = header_font
            
        if enable_filter and max_row > 1:
            ws.auto_filter.ref = f"A1:{get_column_letter(max_col)}{max_row}"
            
    # 2. ウィンドウ枠固定
    if freeze_panes:
        ws.freeze_panes = freeze_panes
        
    # 3. 列幅の自動調整 (先頭50行サンプリングによる簡易適用)
    for col_idx in range(1, max_col + 1):
        col_letter = get_column_letter(col_idx)
        max_len = 0
        for row_idx in range(1, min(max_row, 50) + 1):
            val = str(ws.cell(row=row_idx, column=col_idx).value or '')
            max_len = max(max_len, len(val))
        ws.column_dimensions[col_letter].width = max(min(max_len + 3, 50), 10)


def run_excel_report(inputs: AnalysisInputs) -> TaskResult:
    out_file = inputs.output_dir / "metrics_report.xlsx"
    try:
        und_file_csv = inputs.output_dir / "und" / "und_file.csv"
        und_func_csv = inputs.output_dir / "und" / "und_func.csv"
        cloc_filtered_csv = inputs.output_dir / "cloc" / "cloc_filtered.csv"
        pmd_clone_ratio_csv = inputs.output_dir / "pmd" / "pmd_clone_ratio.csv"
        git_diff_csv = inputs.output_dir / "git" / "git_diff_file_metrics.csv"
        metrics_merge_csv = inputs.output_dir / "metrics_merge.csv"
        
        if not (und_file_csv.exists() or und_func_csv.exists() or cloc_filtered_csv.exists() or 
                pmd_clone_ratio_csv.exists() or git_diff_csv.exists() or metrics_merge_csv.exists()):
            return TaskResult(
                name="excel_report",
                executed=False,
                success=True,
                message="excel report skipped (no intermediate CSVs found)",
            )

        with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
            summary_rows = []

            # 1. UND (File / Hierarchy)
            if und_file_csv.exists():
                max_level = int(os.getenv("FILE_METRICS_MAX_LEVEL", "8"))
                if max_level < 0:
                    max_level = 8
                
                u = pd.read_csv(und_file_csv, dtype=object, na_filter=False)
                required = {"File", "CountLineCode", "CountLineComment", "CountLine"}
                if required.issubset(u.columns):
                    metrics = pd.DataFrame({
                        "File": u["File"].astype(str),
                        "SourceLines": _safe_num(u["CountLineCode"]),
                        "CommentLines": _safe_num(u["CountLineComment"]),
                        "TotalLines": _safe_num(u["CountLine"]),
                    })
                    metrics = _normalize_paths(metrics, ["File"], inputs.remove_path_prefix)
                    metrics = metrics[metrics["File"].astype(str) != ""].copy()
                    metrics = metrics[
                        ~metrics["File"]
                        .astype(str)
                        .str.split("/")
                        .map(lambda parts: any(part.startswith(".") for part in parts if part))
                    ].copy()
                    
                    if not metrics.empty:
                        metrics = metrics.sort_values(by=["SourceLines", "TotalLines"], ascending=False)
                        metrics["Dir"] = metrics["File"].astype(str).map(lambda p: str(Path(p).parent).replace("\\", "/"))
                        metrics["Dir"] = metrics["Dir"].replace(".", "").str.strip("/")
                        
                        metrics_for_agg = metrics[metrics["Dir"] != ""].copy()
                        if not metrics_for_agg.empty:
                            hierarchy = _build_hierarchy_agg(metrics_for_agg, "Dir", max_level=max_level)
                            hierarchy["Path"] = hierarchy.apply(
                                lambda row: "  " * int(row["Level"]) + str(row["Path"]), axis=1
                            )
                            hierarchy.to_excel(writer, sheet_name="file_hierarchy", index=False)
                            
                            summary_rows.extend([
                                {"Metric": "UND 総ソース行数 (LoC)", "Value": int(metrics["SourceLines"].sum())},
                                {"Metric": "UND 総ファイル数", "Value": len(metrics)}
                            ])
            
            # 2. UND (Function / Detail / Agg / Dist)
            if und_func_csv.exists():
                f = pd.read_csv(und_func_csv, dtype=object, na_filter=False)
                if not f.empty and "File" in f.columns:
                    f = _normalize_paths(f, ["File"], inputs.remove_path_prefix)
                    f = f[f["File"].astype(str) != ""].copy()
                    f = f[
                        ~f["File"].astype(str).str.split("/").map(lambda parts: any(part.startswith(".") for part in parts if part))
                    ].copy()
                    
                    if not f.empty:
                        level_df = _split_path_levels(f["File"], max_level=15)
                        out_df = pd.concat([f.reset_index(drop=True), level_df.reset_index(drop=True)], axis=1)
                        for c in ["MaxNesting", "Cyclomatic", "Essential"]:
                            if c in out_df.columns:
                                 out_df[c] = _safe_num(out_df[c])
                        
                        out_df.to_excel(writer, sheet_name="func_detail", index=False)
                        
                        agg_keys = [f"Level{i}" for i in range(16)]
                        agg_map = {"FunctionCount": ("File", "size")}
                        for metric in ["MaxNesting", "Cyclomatic", "Essential"]:
                            if metric in out_df.columns:
                                agg_map[f"{metric}_Avg"] = (metric, "mean")
                        
                        agg_df = out_df.groupby(agg_keys, dropna=False).agg(**agg_map).reset_index()
                        for c in agg_df.columns:
                            if c.endswith("_Avg"):
                                agg_df[c] = pd.to_numeric(agg_df[c], errors="coerce").round(3)
                        
                        agg_df.to_excel(writer, sheet_name="func_level_agg", index=False)
                        
                        dist_maxnesting = _distribution(out_df, "MaxNesting")
                        dist_cyclomatic = _distribution(out_df, "Cyclomatic")
                        dist_essential = _distribution(out_df, "Essential")
                        
                        dist_maxnesting.to_excel(writer, sheet_name="func_dist_nesting", index=False)
                        dist_cyclomatic.to_excel(writer, sheet_name="func_dist_cyclomatic", index=False)
                        dist_essential.to_excel(writer, sheet_name="func_dist_essential", index=False)
                        
                        summary_rows.append({"Metric": "UND 総関数数", "Value": len(out_df)})
                        if "Cyclomatic" in out_df.columns:
                            summary_rows.append({"Metric": "UND 平均 Cyclomatic 複雑度", "Value": round(float(out_df["Cyclomatic"].mean()), 2)})

            # 3. CLOC
            if cloc_filtered_csv.exists():
                cloc_df = pd.read_csv(cloc_filtered_csv)
                if not cloc_df.empty:
                    cloc_agg = cloc_df.groupby("language").agg(
                        code=("code", "sum"),
                        comment=("comment", "sum"),
                        blank=("blank", "sum"),
                        files=("code", "size")
                    ).reset_index()
                    cloc_agg = cloc_agg.sort_values(by="code", ascending=False)
                    cloc_agg.to_excel(writer, sheet_name="cloc_summary", index=False)
                    
                    summary_rows.append({"Metric": "CLOC 総コード行数", "Value": int(cloc_df["code"].sum())})

            # 4. PMD
            if pmd_clone_ratio_csv.exists():
                pmd_df = pd.read_csv(pmd_clone_ratio_csv)
                if not pmd_df.empty:
                    pmd_df = _normalize_paths(pmd_df, ["File"], inputs.remove_path_prefix)
                    pmd_df = pmd_df.sort_values(by="PmdCloneRatio", ascending=False)
                    pmd_df.to_excel(writer, sheet_name="pmd_clone_ratio", index=False)
                    
                    tot_tok = pmd_df["PmdTotalTokens"].sum()
                    cln_tok = pmd_df["PmdCloneTokensSum"].sum()
                    ratio = float(cln_tok / tot_tok * 100.0) if tot_tok else 0.0
                    summary_rows.append({"Metric": "PMD 重複コード率 (Tokens %)", "Value": round(ratio, 2)})

            # 5. Git Numstat
            if git_diff_csv.exists():
                git_df = pd.read_csv(git_diff_csv)
                if not git_df.empty:
                    git_df = _normalize_paths(git_df, ["File"], inputs.remove_path_prefix)
                    git_df = git_df.sort_values(by="ChangedLines", ascending=False)
                    git_df.to_excel(writer, sheet_name="git_diff", index=False)
                    
                    summary_rows.append({"Metric": "Git 差分変更行数", "Value": int(git_df["ChangedLines"].sum())})

            # 6. Metrics Merge
            if metrics_merge_csv.exists():
                merge_df = pd.read_csv(metrics_merge_csv)
                if not merge_df.empty:
                    merge_df = _normalize_paths(merge_df, ["File"], inputs.remove_path_prefix)
                    merge_df.to_excel(writer, sheet_name="metrics_merge", index=False)

            # 7. Summary シート (シンプルな表形式)
            summary_df = pd.DataFrame(summary_rows if summary_rows else [{"Metric": "-", "Value": "-"}])
            summary_df.to_excel(writer, sheet_name="summary", index=False)

            # summary シートを先頭（左端）に移動
            wb = writer.book
            sheets = wb._sheets
            summary_sheet = sheets.pop()
            sheets.insert(0, summary_sheet)

        # 8. 各シートの最小限の書式設定
        wb = openpyxl.load_workbook(out_file)
        
        for name in wb.sheetnames:
            ws = wb[name]
            
            freeze = None
            if name in ["func_detail", "metrics_merge", "git_diff", "pmd_clone_ratio"]:
                freeze = "B2"
            elif name == "file_hierarchy":
                freeze = "C2"
                
            _apply_common_styles(ws, has_header=True, freeze_panes=freeze, enable_filter=True)
                
        wb.save(out_file)
        
        return TaskResult(
            name="excel_report",
            executed=True,
            success=True,
            outputs=[out_file],
            message=f"unified excel report generated ({out_file.name})",
        )
    except Exception as exc:
        return TaskResult(
            name="excel_report",
            executed=True,
            success=False,
            message=f"excel report failed: {exc}",
        )