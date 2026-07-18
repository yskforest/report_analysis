#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

from plotly_visualize import write_treemap_by_path


class ProgressReporter:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.started_at = time.monotonic()

    def log(self, message: str) -> None:
        if self.enabled:
            elapsed = time.monotonic() - self.started_at
            print(f"[INFO] {message} elapsed={elapsed:.1f}s", file=sys.stderr, flush=True)


def write_index(output_path: Path, base_ref: str, target_label: str) -> None:
    output_path.write_text(
        "\n".join(
            [
                "<!doctype html>",
                '<html lang="ja">',
                '<head><meta charset="utf-8"><title>Git Diff Treemap</title></head>',
                "<body>",
                "<h1>Git Diff Treemap</h1>",
                f"<p>Base: <code>{base_ref}</code> / Target: <code>{target_label}</code></p>",
                "<ul>",
                '<li><a href="code_total_lines_treemap.html">コード総行数 Treemap（色: 変更率）</a></li>',
                '<li><a href="file_size_treemap.html">ファイルサイズ Treemap（面積: サイズ、色: 変更率）</a></li>',
                '<li><a href="changed_lines_count_treemap.html">変更行数カラーマップ Treemap（色: 変更行数）</a></li>',
                '<li><a href="changed_lines_treemap.html">変更行数 Treemap（面積: 変更行数）</a></li>',
                '<li><a href="git_diff_file_metrics.csv">ファイル別 CSV (merged)</a></li>',
                '<li><a href="git_diff_summary.csv">サマリ CSV</a></li>',
                "</ul>",
                "</body></html>",
                "",
            ]
        ),
        encoding="utf-8",
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Plotly HTML treemaps from the aggregated metrics CSV.")
    parser.add_argument("input_csv", help="メトリクス収集済みのCSVファイルのパス")
    parser.add_argument("output_dir", help="ツリーマップHTMLの出力先ディレクトリ")
    parser.add_argument(
        "--treemap-max-depth",
        type=int,
        default=8,
        help="Treemap の最大階層深さ (default: 8)",
    )
    parser.add_argument("--no-progress", action="store_true", help="進捗表示を無効化する")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        progress = ProgressReporter(enabled=not args.no_progress)
        input_csv = Path(args.input_csv).expanduser().resolve()
        output_dir = Path(args.output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        if not input_csv.exists():
            print(f"[ERROR] input CSV file not found: {input_csv}", file=sys.stderr)
            return 1

        progress.log("reading input CSV")
        df = pd.read_csv(input_csv)

        if df.empty:
            print("[WARN] input CSV is empty, creating empty data structures", file=sys.stderr)
        else:
            # Smart CLOC line count integration
            cloc_code_col = next((c for c in df.columns if c.endswith("_code")), None)
            cloc_comment_col = next((c for c in df.columns if c.endswith("_comment")), None)
            cloc_blank_col = next((c for c in df.columns if c.endswith("_blank")), None)

            if cloc_code_col and cloc_comment_col and cloc_blank_col:
                progress.log("integrating CLOC line counts into TotalLines")
                cloc_code = pd.to_numeric(df[cloc_code_col], errors="coerce").fillna(0)
                cloc_comment = pd.to_numeric(df[cloc_comment_col], errors="coerce").fillna(0)
                cloc_blank = pd.to_numeric(df[cloc_blank_col], errors="coerce").fillna(0)
                df["cloc_Total"] = cloc_code + cloc_comment + cloc_blank

                # Update TotalLines only for files that actually have matching CLOC metrics
                df["TotalLines"] = df.apply(
                    lambda r: (
                        int(r["cloc_Total"])
                        if pd.notna(r[cloc_code_col]) and r[cloc_code_col] > 0
                        else int(r.get("TotalLines", 0))
                    ),
                    axis=1,
                )
                # Re-calculate ChangeRatio if TotalLines was updated
                if "ChangedLines" in df.columns:
                    df["ChangeRatio"] = df.apply(
                        lambda r: round(r["ChangedLines"] / r["TotalLines"], 6) if r["TotalLines"] > 0 else 0.0, axis=1
                    )

        treemap_max_depth = max(1, args.treemap_max_depth)

        # Write code_total_lines_treemap.html
        progress.log(f"writing total lines change ratio treemap (max_depth={treemap_max_depth})")
        write_treemap_by_path(
            df,
            file_col="File",
            size_col="TotalLines",
            color_col="ChangeRatio",
            output_html=output_dir / "code_total_lines_treemap.html",
            title="Count Line(Area) - Change Ratio(Color) Treemap",
            vmin=0,
            vmax=1,
            max_depth=treemap_max_depth,
            empty_label="NO_DATA",
            aggregate=True,
            color_agg="weighted_mean",
            color_continuous_scale="Blues",
        )

        # Write file_size_treemap.html
        progress.log(f"writing file size treemap (max_depth={treemap_max_depth})")
        write_treemap_by_path(
            df,
            file_col="File",
            size_col="FileSize",
            color_col=None,
            output_html=output_dir / "file_size_treemap.html",
            title="File Size(Area) Treemap",
            vmin=0,
            vmax=1,
            max_depth=treemap_max_depth,
            empty_label="NO_DATA",
            aggregate=True,
            color_agg="sum",
            color_continuous_scale="Blues",
        )

        # Write changed_lines_count_treemap.html
        progress.log(f"writing count lines changed lines treemap (max_depth={treemap_max_depth})")
        write_treemap_by_path(
            df,
            file_col="File",
            size_col="TotalLines",
            color_col="ChangedLines",
            output_html=output_dir / "changed_lines_count_treemap.html",
            title="Count Line(Area) - Changed Line(Color) Treemap",
            vmin=0,
            vmax=100,
            max_depth=treemap_max_depth,
            empty_label="NO_CHANGED_LINES",
            aggregate=True,
            color_agg="sum",
            color_continuous_scale="Blues",
        )

        # Write changed_lines_treemap.html
        progress.log(f"writing changed lines treemap (max_depth={treemap_max_depth})")
        write_treemap_by_path(
            df,
            file_col="File",
            size_col="ChangedLines",
            color_col=None,
            output_html=output_dir / "changed_lines_treemap.html",
            title="Changed Line(Area) Treemap",
            vmin=0,
            vmax=1,
            max_depth=treemap_max_depth,
            empty_label="NO_CHANGED_LINES",
            aggregate=True,
            color_agg="sum",
            color_continuous_scale="Blues",
        )

        # Try to resolve BaseRef and Target from summary CSV to populate index.html
        base_ref = "N/A"
        target_label = "N/A"
        summary_csv = input_csv.parent / "git_diff_summary.csv"
        if summary_csv.exists():
            try:
                sum_df = pd.read_csv(summary_csv)
                if not sum_df.empty:
                    base_ref = str(sum_df.iloc[0].get("BaseRef", "N/A"))
                    target_label = str(sum_df.iloc[0].get("Target", "N/A"))
            except Exception:
                pass

        progress.log("writing index.html")
        write_index(output_dir / "index.html", base_ref, target_label)

        print(f"[INFO] treemaps generated in output_dir={output_dir}")
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
