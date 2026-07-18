#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from io_models import clean_path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge multiple metrics CSV files with safe prefix-based path normalization and column prefixing."
    )
    parser.add_argument("output_csv", help="出力するマージ後CSVファイルのパス")
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="マージ対象のCSVファイルのパス一覧（スペース区切り）",
    )
    parser.add_argument(
        "--join-col",
        default="File",
        help="結合に使用するファイルパスのカラム名 (default: File)",
    )
    parser.add_argument(
        "--prefixes",
        nargs="+",
        help="各CSVのカラム名に付与するプレフィックス（順番に指定、指定なしの場合はファイル名）",
    )
    parser.add_argument(
        "--strip-prefix",
        action="append",
        default=[],
        help="ファイルパスの先頭から削除するプレフィックス（複数指定可能、安全削除用）",
    )
    parser.add_argument(
        "--how",
        choices=["left", "right", "outer", "inner"],
        default="left",
        help="Pandasマージの結合方式 (default: left)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        output_csv = Path(args.output_csv).expanduser().resolve()
        output_csv.parent.mkdir(parents=True, exist_ok=True)

        inputs = [Path(p).expanduser().resolve() for p in args.inputs]
        prefixes = args.prefixes or []
        strip_prefixes = args.strip_prefix

        # Validate inputs
        for p in inputs:
            if not p.exists():
                print(f"[ERROR] input CSV not found: {p}", file=sys.stderr)
                return 1

        print(f"[INFO] Merging {len(inputs)} CSV files...")

        # 1. Load baseline (1st CSV)
        baseline_path = inputs[0]
        print(f"[INFO] Base CSV: {baseline_path.name}")
        df = pd.read_csv(baseline_path, na_filter=False)

        # Check if join column exists
        # Note: CLOC uses 'filename', Understand uses 'File', Git Diff uses 'File'.
        # We can dynamically find the join column if the exact name isn't found by looking at standard names
        def find_and_rename_join_col(local_df: pd.DataFrame, join_col: str, csv_name: str) -> str:
            if join_col in local_df.columns:
                return join_col
            # Check standard alternatives
            for alt in ["File", "filename", "filepath", "path"]:
                for col in local_df.columns:
                    if col.lower() == alt.lower():
                        print(f"[INFO] [{csv_name}] mapped column '{col}' to '{join_col}'")
                        local_df.rename(columns={col: join_col}, inplace=True)
                        return join_col
            raise ValueError(f"[{csv_name}] join column '{join_col}' not found in columns: {list(local_df.columns)}")

        def filter_kind_file_if_exists(local_df: pd.DataFrame, csv_name: str) -> pd.DataFrame:
            kind_col = None
            for col in local_df.columns:
                if col.lower() == "kind":
                    kind_col = col
                    break
            if kind_col is not None:
                orig_len = len(local_df)
                local_df = local_df[local_df[kind_col].astype(str) == "File"]
                filtered_len = len(local_df)
                print(f"[INFO] [{csv_name}] Filtered by {kind_col} == 'File': {orig_len} -> {filtered_len} rows")
            return local_df

        join_col = args.join_col
        find_and_rename_join_col(df, join_col, baseline_path.name)
        df = filter_kind_file_if_exists(df, baseline_path.name)

        # Normalize baseline paths
        df[join_col] = df[join_col].map(lambda p: clean_path(p, strip_prefixes))

        # Rename baseline columns if a prefix is provided
        base_prefix = prefixes[0] if len(prefixes) > 0 else ""
        if base_prefix:
            df.rename(
                columns={c: f"{base_prefix}_{c}" for c in df.columns if c != join_col},
                inplace=True,
            )

        # 2. Merge subsequent CSVs
        for idx, csv_path in enumerate(inputs[1:], start=1):
            csv_name = csv_path.name
            print(f"[INFO] Merging CSV: {csv_name}")

            sub_df = pd.read_csv(csv_path, na_filter=False)
            sub_df = filter_kind_file_if_exists(sub_df, csv_name)
            find_and_rename_join_col(sub_df, join_col, csv_name)

            # Normalize paths in sub_df
            sub_df[join_col] = sub_df[join_col].map(lambda p: clean_path(p, strip_prefixes))

            # Determine prefix to use
            if idx < len(prefixes):
                prefix = prefixes[idx]
            else:
                prefix = csv_path.stem

            # Prepend prefix to sub_df columns to prevent collision
            sub_df.rename(
                columns={c: f"{prefix}_{c}" for c in sub_df.columns if c != join_col},
                inplace=True,
            )

            # Merge
            df = pd.merge(df, sub_df, on=join_col, how=args.how)

        # Save merged CSV
        df.to_csv(output_csv, index=False)
        print(f"[INFO] Merged metrics written to: {output_csv}")
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
