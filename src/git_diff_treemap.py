#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import fnmatch
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from plotly_visualize import write_treemap_by_path

DEFAULT_CODE_EXTENSIONS = {
    ".asm",
    ".bat",
    ".c",
    ".cc",
    ".clj",
    ".cljs",
    ".cmake",
    ".cpp",
    ".cs",
    ".css",
    ".cu",
    ".cuh",
    ".dart",
    ".erl",
    ".ex",
    ".exs",
    ".f90",
    ".go",
    ".gradle",
    ".groovy",
    ".h",
    ".hpp",
    ".hs",
    ".html",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".kts",
    ".lua",
    ".m",
    ".mm",
    ".php",
    ".pl",
    ".pm",
    ".ps1",
    ".py",
    ".r",
    ".rb",
    ".rs",
    ".scala",
    ".scss",
    ".sh",
    ".sql",
    ".swift",
    ".ts",
    ".tsx",
    ".vue",
    ".xml",
    ".yaml",
    ".yml",
}

DEFAULT_EXCLUDE_PATTERNS = [
    ".git/**",
    "venv/**",
    ".venv/**",
    "node_modules/**",
    "out/**",
    "dist/**",
    "build/**",
    "__pycache__/**",
    "*.pyc",
]


@dataclass
class GitFileChange:
    file_path: str
    added_lines: int
    deleted_lines: int

    @property
    def changed_lines(self) -> int:
        return self.added_lines + self.deleted_lines


class ProgressReporter:
    def __init__(self, enabled: bool = True, interval_seconds: float = 2.0) -> None:
        self.enabled = enabled
        self.interval_seconds = max(0.1, interval_seconds)
        self.started_at = time.monotonic()
        self.last_report_at = 0.0

    def log(self, message: str) -> None:
        if self.enabled:
            print(f"[INFO] {message}", file=sys.stderr, flush=True)

    def update(self, label: str, current: int, total: int, *, force: bool = False) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        if not force and current != total and now - self.last_report_at < self.interval_seconds:
            return
        self.last_report_at = now
        elapsed = now - self.started_at
        if total > 0:
            percent = current / total * 100
            print(
                f"[INFO] {label}: {current}/{total} ({percent:.1f}%) elapsed={elapsed:.1f}s",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(f"[INFO] {label}: {current} elapsed={elapsed:.1f}s", file=sys.stderr, flush=True)


def run_git(repo: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git command failed: {' '.join(args)}")
    return proc.stdout


def run_git_bytes(repo: Path, args: list[str]) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        message = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or f"git command failed: {' '.join(args)}")
    return proc.stdout


def resolve_repo(raw_repo: str) -> Path:
    repo = Path(raw_repo).expanduser().resolve()
    top = run_git(repo, ["rev-parse", "--show-toplevel"]).strip()
    return Path(top).resolve()


def verify_ref(repo: Path, ref: str) -> None:
    run_git(repo, ["rev-parse", "--verify", f"{ref}^{{commit}}"])


def parse_extensions(raw: str) -> set[str]:
    if raw.lower() in {"", "default"}:
        return set(DEFAULT_CODE_EXTENSIONS)
    if raw.lower() in {"all", "*"}:
        return set()
    exts: set[str] = set()
    for item in raw.split(","):
        value = item.strip().lower()
        if not value:
            continue
        exts.add(value if value.startswith(".") else f".{value}")
    return exts


def is_excluded(path: str, patterns: list[str]) -> bool:
    clean = path.replace("\\", "/").lstrip("/")
    return any(fnmatch.fnmatch(clean, pattern) for pattern in patterns)


def is_code_file(path: str, extensions: set[str]) -> bool:
    if not extensions:
        return True
    return Path(path).suffix.lower() in extensions


def normalize_rename_path(path: str) -> str:
    if " => " not in path:
        return path
    if "{" in path and "}" in path:
        chars: list[str] = []
        i = 0
        while i < len(path):
            if path[i] == "{":
                end = path.find("}", i)
                if end != -1:
                    segment = path[i + 1 : end]
                    if " => " in segment:
                        chars.append(segment.split(" => ", 1)[1])
                        i = end + 1
                        continue
            chars.append(path[i])
            i += 1
        path = "".join(chars)
    if " => " in path:
        path = path.rsplit(" => ", 1)[1]
    return path.strip()


def list_target_file_blobs(repo: Path, target_ref: str | None, use_worktree: bool) -> dict[str, str | None]:
    if use_worktree:
        output = run_git_bytes(repo, ["ls-files", "-z"])
        return {raw.decode("utf-8", errors="replace").replace("\\", "/"): None for raw in output.split(b"\0") if raw}

    output = run_git_bytes(repo, ["ls-tree", "-r", "-z", target_ref or "HEAD"])
    files: dict[str, str | None] = {}
    for record in output.split(b"\0"):
        if not record or b"\t" not in record:
            continue
        meta, raw_path = record.split(b"\t", 1)
        meta_parts = meta.split()
        if len(meta_parts) < 3 or meta_parts[1] != b"blob":
            continue
        file_path = raw_path.decode("utf-8", errors="replace").replace("\\", "/")
        files[file_path] = meta_parts[2].decode("ascii", errors="replace")
    return files


def get_file_metrics(path: Path) -> tuple[int, int]:
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return 0, 0

    total_lines = 0
    has_data = False
    last_byte = b""
    try:
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                if b"\0" in chunk:
                    return 0, size
                has_data = True
                total_lines += chunk.count(b"\n")
                last_byte = chunk[-1:]
    except FileNotFoundError:
        return 0, 0
    if not has_data:
        return 0, size
    return total_lines + (0 if last_byte == b"\n" else 1), size


def count_blob_lines_from_stdout(stdout, size: int) -> int:
    remaining = size
    total_lines = 0
    has_data = False
    last_byte = b""
    is_binary = False
    while remaining > 0:
        chunk = stdout.read(min(1024 * 1024, remaining))
        if not chunk:
            break
        remaining -= len(chunk)
        if b"\0" in chunk:
            is_binary = True
        if not is_binary:
            has_data = True
            total_lines += chunk.count(b"\n")
            last_byte = chunk[-1:]
    if is_binary or not has_data:
        return 0
    return total_lines + (0 if last_byte == b"\n" else 1)


def get_worktree_metrics(repo: Path, paths: list[str], progress: ProgressReporter) -> dict[str, tuple[int, int]]:
    totals: dict[str, tuple[int, int]] = {}
    total = len(paths)
    if total == 0:
        progress.update("counting worktree metrics", 0, 0, force=True)
        return totals
    for index, file_path in enumerate(paths, start=1):
        totals[file_path] = get_file_metrics(repo / file_path)
        progress.update("counting worktree metrics", index, total)
    return totals


def get_git_blob_metrics(
    repo: Path, blob_by_path: dict[str, str], progress: ProgressReporter
) -> dict[str, tuple[int, int]]:
    totals: dict[str, tuple[int, int]] = {}
    paths = list(blob_by_path.keys())
    total = len(paths)
    if total == 0:
        progress.update("counting git blob metrics", 0, 0, force=True)
        return totals
    proc = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.stdin is None or proc.stdout is None:
        raise RuntimeError("failed to start git cat-file --batch")

    for index, file_path in enumerate(paths, start=1):
        object_id = blob_by_path[file_path]
        proc.stdin.write(f"{object_id}\n".encode("ascii"))
        proc.stdin.flush()
        header = proc.stdout.readline()
        parts = header.strip().split()
        if len(parts) < 3 or parts[1] != b"blob":
            totals[file_path] = (0, 0)
        else:
            size = int(parts[2])
            totals[file_path] = (count_blob_lines_from_stdout(proc.stdout, size), size)
            proc.stdout.read(1)
        progress.update("counting git blob metrics", index, total)

    proc.stdin.close()
    stderr = proc.stderr.read().decode("utf-8", errors="replace").strip() if proc.stderr is not None else ""
    return_code = proc.wait()
    if return_code != 0:
        raise RuntimeError(stderr or "git cat-file --batch failed")
    return totals


def get_target_metrics(
    repo: Path,
    file_blobs: dict[str, str | None],
    target_paths: list[str],
    use_worktree: bool,
    progress: ProgressReporter,
) -> dict[str, tuple[int, int]]:
    existing_paths = [path for path in target_paths if path in file_blobs]
    if use_worktree:
        return get_worktree_metrics(repo, existing_paths, progress)
    blob_by_path = {path: object_id for path in existing_paths if (object_id := file_blobs.get(path)) is not None}
    return get_git_blob_metrics(repo, blob_by_path, progress)


def read_diff_changes(
    repo: Path, base_ref: str, target_ref: str | None, use_worktree: bool
) -> dict[str, GitFileChange]:
    args = ["diff", "--numstat", "--find-renames", base_ref]
    if not use_worktree:
        args.append(target_ref or "HEAD")
    output = run_git(repo, args)
    changes: dict[str, GitFileChange] = {}
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_raw, deleted_raw, file_raw = parts[0], parts[1], parts[2]
        if added_raw == "-" or deleted_raw == "-":
            continue
        file_path = normalize_rename_path(file_raw).replace("\\", "/")
        try:
            added = int(added_raw)
            deleted = int(deleted_raw)
        except ValueError:
            continue
        previous = changes.get(file_path)
        if previous is None:
            changes[file_path] = GitFileChange(file_path, added, deleted)
        else:
            changes[file_path] = GitFileChange(
                file_path,
                previous.added_lines + added,
                previous.deleted_lines + deleted,
            )
    return changes


def collect_rows(
    repo: Path,
    base_ref: str,
    target_ref: str | None,
    use_worktree: bool,
    extensions: set[str],
    exclude_patterns: list[str],
    progress: ProgressReporter,
    algo: str = "add+delete",
) -> pd.DataFrame:
    progress.log("listing target files")
    file_blobs = list_target_file_blobs(repo, target_ref, use_worktree)
    progress.log(f"target files listed: {len(file_blobs)}")
    progress.log("reading git diff --numstat")
    changes = read_diff_changes(repo, base_ref, target_ref, use_worktree)
    progress.log(f"changed files listed: {len(changes)}")
    candidate_paths = sorted(set(file_blobs.keys()) | set(changes.keys()))
    filtered_paths = [
        file_path.replace("\\", "/").lstrip("/")
        for file_path in candidate_paths
        if not is_excluded(file_path.replace("\\", "/").lstrip("/"), exclude_patterns)
        and is_code_file(file_path.replace("\\", "/").lstrip("/"), extensions)
    ]
    progress.log(f"matched files after filters: {len(filtered_paths)}")
    total_metrics_by_path = get_target_metrics(repo, file_blobs, filtered_paths, use_worktree, progress)
    rows: list[dict[str, object]] = []
    total = len(filtered_paths)
    if total == 0:
        progress.update("building file metrics rows", 0, 0, force=True)
        return pd.DataFrame(rows)
    for index, clean_path in enumerate(filtered_paths, start=1):
        change = changes.get(clean_path, GitFileChange(clean_path, 0, 0))
        total_lines, file_size = total_metrics_by_path.get(clean_path, (0, 0))
        if algo == "add":
            changed_lines = change.added_lines
        elif algo == "delete":
            changed_lines = change.deleted_lines
        else:
            changed_lines = change.added_lines + change.deleted_lines

        rows.append(
            {
                "File": clean_path,
                "TotalLines": int(total_lines),
                "FileSize": int(file_size),
                "AddedLines": int(change.added_lines),
                "DeletedLines": int(change.deleted_lines),
                "ChangedLines": int(changed_lines),
                "ChangeRatio": round(changed_lines / total_lines, 6) if total_lines else 0.0,
            }
        )
        progress.update("building file metrics rows", index, total)
    return pd.DataFrame(rows)


def write_summary(df: pd.DataFrame, output_path: Path, base_ref: str, target_label: str) -> None:
    changed = df[df["ChangedLines"] > 0]
    summary = pd.DataFrame(
        [
            {
                "BaseRef": base_ref,
                "Target": target_label,
                "Files": int(len(df.index)),
                "ChangedFiles": int(len(changed.index)),
                "TotalLines": int(df["TotalLines"].sum()) if not df.empty else 0,
                "TotalSize": int(df["FileSize"].sum()) if not df.empty else 0,
                "AddedLines": int(df["AddedLines"].sum()) if not df.empty else 0,
                "DeletedLines": int(df["DeletedLines"].sum()) if not df.empty else 0,
                "ChangedLines": int(df["ChangedLines"].sum()) if not df.empty else 0,
            }
        ]
    )
    summary.to_csv(output_path, index=False)


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
                '<li><a href="git_diff_file_metrics.csv">ファイル別 CSV</a></li>',
                '<li><a href="git_diff_summary.csv">サマリ CSV</a></li>',
                "</ul>",
                "</body></html>",
                "",
            ]
        ),
        encoding="utf-8",
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate Git diff lines from a base ref to HEAD or the working tree and render treemaps."
    )
    parser.add_argument("base_ref", help="比較元のタグ名またはコミットID")
    parser.add_argument("output_dir", help="成果物の出力ディレクトリ")
    parser.add_argument("--git-dir", default=".", help="集計対象の Git ディレクトリパス")
    parser.add_argument("--target-ref", default="HEAD", help="比較先のタグ/コミット/ブランチ (default: HEAD)")
    parser.add_argument("--worktree", action="store_true", help="比較先を現在の作業ツリーにする")
    parser.add_argument(
        "--extensions",
        default="default",
        help="対象拡張子のカンマ区切り。default は主要コード拡張子、all は全ファイル",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="除外 glob。複数指定可。既定除外に追加される",
    )
    parser.add_argument(
        "--treemap-max-depth",
        type=int,
        default=8,
        help="Treemap の最大階層深さ。大規模リポジトリでは小さいほど高速・軽量 (default: 8)",
    )
    parser.add_argument("--no-progress", action="store_true", help="進捗表示を無効化する")
    parser.add_argument(
        "--progress-interval",
        type=float,
        default=2.0,
        help="進捗表示間隔秒 (default: 2.0)",
    )
    parser.add_argument(
        "--algo",
        choices=["add", "delete", "add+delete"],
        default="add+delete",
        help="修正量の集計アルゴリズム (choices: add, delete, add+delete) (default: add+delete)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        progress = ProgressReporter(enabled=not args.no_progress, interval_seconds=args.progress_interval)
        repo = resolve_repo(args.git_dir)
        verify_ref(repo, args.base_ref)
        if not args.worktree:
            verify_ref(repo, args.target_ref)
        output_dir = Path(args.output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        extensions = parse_extensions(args.extensions)
        excludes = [*DEFAULT_EXCLUDE_PATTERNS, *args.exclude]
        target_label = "worktree" if args.worktree else args.target_ref

        df = collect_rows(
            repo,
            args.base_ref,
            args.target_ref,
            args.worktree,
            extensions,
            excludes,
            progress,
            algo=args.algo,
        )
        if df.empty:
            print("[WARN] no files matched filters")
            df = pd.DataFrame(
                columns=["File", "TotalLines", "FileSize", "AddedLines", "DeletedLines", "ChangedLines", "ChangeRatio"]
            )
        else:
            df = df.sort_values(
                by=["ChangedLines", "TotalLines", "FileSize", "File"], ascending=[False, False, False, True]
            )

        files_csv = output_dir / "git_diff_file_metrics.csv"
        summary_csv = output_dir / "git_diff_summary.csv"
        progress.log("writing csv outputs")
        df.to_csv(files_csv, index=False, quoting=csv.QUOTE_MINIMAL)
        write_summary(df, summary_csv, args.base_ref, target_label)
        treemap_max_depth = max(1, args.treemap_max_depth)
        progress.log(f"writing code total lines treemap (max_depth={treemap_max_depth})")
        write_treemap_by_path(
            df,
            file_col="File",
            size_col="TotalLines",
            color_col="ChangeRatio",
            output_html=output_dir / "code_total_lines_treemap.html",
            title="Count Line(Area) - Diff ratio(Color) Treemap",
            vmin=0,
            vmax=1,
            max_depth=treemap_max_depth,
            empty_label="NO_DATA",
            aggregate=True,
            color_agg="weighted_mean",
            color_continuous_scale="Blues",
        )
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
        progress.log(f"writing changed lines count treemap (max_depth={treemap_max_depth})")
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
        write_index(output_dir / "index.html", args.base_ref, target_label)

        print(f"[INFO] repo={repo}")
        print(f"[INFO] git_dir={args.git_dir}")
        print(f"[INFO] base={args.base_ref} target={target_label}")
        print(f"[INFO] files={files_csv}")
        print(f"[INFO] summary={summary_csv}")
        print(f"[INFO] treemap={output_dir / 'index.html'}")
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
