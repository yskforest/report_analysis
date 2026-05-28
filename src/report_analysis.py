#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from analyzers import run_cloc, run_pmd, run_understand, write_global_summary
from advanced_visualizations import run_advanced_visualizations
from io_models import resolve_inputs

USAGE = (
    "usage: report_analysis.py "
    "{UND_CSV|none} {CLOC_CSV|none} {PMD_XML_GLOB_OR_LIST|none} {OUTPUT_DIR} {REMOVE_PATH_PREFIX}"
)


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(USAGE, file=sys.stderr)
        return 1

    und_raw, cloc_raw, pmd_raw, output_dir_raw, remove_prefix = argv
    inputs = resolve_inputs(und_raw, cloc_raw, pmd_raw, output_dir_raw, remove_prefix)
    inputs.output_dir.mkdir(parents=True, exist_ok=True)

    for w in inputs.warnings:
        print(f"[WARN] {w}")

    if inputs.und_csv is None and inputs.cloc_csv is None and not inputs.pmd_xmls:
        print("[ERROR] no valid inputs found", file=sys.stderr)
        return 1

    print("[INFO] report analysis started")
    print(f"[INFO] output_dir={inputs.output_dir}")

    results = [
        run_understand(inputs),
        run_cloc(inputs),
        run_pmd(inputs),
        run_advanced_visualizations(inputs),
    ]

    summary_path = write_global_summary(inputs, results)
    print(f"[INFO] summary={summary_path}")

    executed = [r for r in results if r.executed]
    failed = [r for r in executed if not r.success]
    for r in results:
        level = "ERROR" if (r.executed and not r.success) else "INFO"
        print(f"[{level}] task={r.name} executed={r.executed} success={r.success} message={r.message}")

    if executed and len(failed) == len(executed):
        print("[ERROR] all executed tasks failed", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
