#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

from analyzers import (
    run_cloc,
    run_file_metrics_excel,
    run_func_metrics_excel,
    run_pmd,
    run_understand,
    write_global_summary,
    run_git_numstat,
    run_comprehensive_merge,
)
from advanced_visualizations import run_advanced_visualizations
from io_models import resolve_inputs

USAGE = (
    "usage: report_analysis.py [--config CONFIG_YAML] "
    "{UND_CSV|none} {CLOC_CSV|none} {PMD_XML_GLOB_OR_LIST|none} {GIT_NUMSTAT|none} {OUTPUT_DIR} {REMOVE_PATH_PREFIX}"
)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(usage=USAGE, add_help=False)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("positionals", nargs="*")

    args = parser.parse_args(argv)
    if len(args.positionals) != 6:
        print(USAGE, file=sys.stderr)
        return 1

    und_raw, cloc_raw, pmd_raw, git_raw, output_dir_raw, remove_prefix = args.positionals

    try:
        inputs = resolve_inputs(
            und_raw, cloc_raw, pmd_raw, git_raw, output_dir_raw, remove_prefix,
            config_path_raw=args.config
        )
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    inputs.output_dir.mkdir(parents=True, exist_ok=True)

    for w in inputs.warnings:
        print(f"[WARN] {w}")

    if (
        inputs.und_csv is None
        and inputs.cloc_csv is None
        and not inputs.pmd_xmls
        and inputs.git_numstat is None
    ):
        print("[ERROR] no valid inputs found", file=sys.stderr)
        return 1

    print("[INFO] report analysis started")
    print(f"[INFO] output_dir={inputs.output_dir}")

    results = [
        run_understand(inputs),
        run_cloc(inputs),
        run_pmd(inputs),
        run_git_numstat(inputs),
        run_file_metrics_excel(inputs),
        run_func_metrics_excel(inputs),
        run_comprehensive_merge(inputs),
        run_advanced_visualizations(inputs),
    ]

    summary_path = write_global_summary(inputs, results)
    print(f"[INFO] summary={summary_path}")

    executed = [r for r in results if r.executed]
    failed = [r for r in executed if not r.success]
    for r in results:
        level = "ERROR" if (r.executed and not r.success) else "INFO"
        print(f"[{level}] task={r.name} executed={r.executed} success={r.success} message={r.message}")

    if failed:
        print("[ERROR] one or more executed tasks failed", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

