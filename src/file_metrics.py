#!/usr/bin/env python3
"""file_metrics.py – ディレクトリを再帰走査してファイルメトリクスを CSV に出力する。

Usage:
    python3 src/file_metrics.py SCAN_DIR OUTPUT_CSV \
        [--remove-prefix PREFIX] \
        [--exclude GLOB ...]

Metrics collected per file:
    file                 – 正規化済みファイルパス
    file_size_bytes      – ファイルサイズ (bytes)
    is_binary            – バイナリ判定 (True/False)
    encoding             – 文字コード推定 (テキストのみ、バイナリは "")
    encoding_confidence  – エンコーディング信頼度 (0.0–1.0)
    line_ending          – 改行コード (CRLF / LF / CR / mixed / N/A)
    line_count           – 総行数 (バイナリは 0)
    extension            – 拡張子 (例: .py)
    mime_type            – MIME タイプ推定
    has_bom              – BOM の有無 (True/False)
    last_modified        – 最終更新日時 (ISO 8601)
"""
from __future__ import annotations

import argparse
import csv
import datetime
import fnmatch
import mimetypes
import os
import sys
from pathlib import Path

try:
    import chardet
    _CHARDET_AVAILABLE = True
except ImportError:
    _CHARDET_AVAILABLE = False

# ── 定数 ──────────────────────────────────────────────────────────────────────

# バイナリ判定に使う先頭読み取りバイト数
_BINARY_CHECK_BYTES = 8192

# エンコーディング検出に使う先頭読み取りバイト数
_ENCODING_DETECT_BYTES = 65536

# デフォルト除外パターン（fnmatch 形式、ディレクトリ名マッチはパスセグメントで判定）
_DEFAULT_EXCLUDES: list[str] = [
    ".git",
    "__pycache__",
    "*.pyc",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".venv",
    "venv",
]

# BOM シーケンス（長い順に並べておく）
_BOM_MAP: list[tuple[bytes, str]] = [
    (b"\xef\xbb\xbf", "UTF-8-BOM"),
    (b"\xff\xfe\x00\x00", "UTF-32-LE-BOM"),
    (b"\x00\x00\xfe\xff", "UTF-32-BE-BOM"),
    (b"\xff\xfe", "UTF-16-LE-BOM"),
    (b"\xfe\xff", "UTF-16-BE-BOM"),
]

# ── ユーティリティ関数 ────────────────────────────────────────────────────────


def _clean_path(path_str: str, remove_prefix: str | None) -> str:
    """パスを正規化し、プレフィックスを除去して返す。"""
    val = path_str.replace("\\", "/").strip("/")
    if remove_prefix:
        norm_prefix = remove_prefix.replace("\\", "/").strip("/")
        if norm_prefix:
            if val.startswith(norm_prefix + "/"):
                val = val[len(norm_prefix) + 1:]
            elif val == norm_prefix:
                val = ""
    if val.startswith("./"):
        val = val[2:]
    return val


def _is_excluded(path: Path, exclude_patterns: list[str]) -> bool:
    """パスのいずれかのセグメントが除外パターンにマッチする場合 True を返す。"""
    for part in path.parts:
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False


def _detect_binary(data: bytes) -> bool:
    """先頭バイト列に NUL バイトが含まれる場合 True（バイナリ）とみなす。"""
    return b"\x00" in data


def _detect_bom(head: bytes) -> bool:
    """先頭バイト列に既知の BOM シーケンスが含まれる場合 True を返す。"""
    for bom, _ in _BOM_MAP:
        if head.startswith(bom):
            return True
    return False


def _detect_encoding_fast(data: bytes, head: bytes) -> tuple[str, float] | None:
    """
    BOMや高速デコード試行を用いて、chardetを使用せずにエンコーディングを決定する。
    判定できない場合は None を返す。
    """
    if not data:
        return "unknown", 0.0

    # 1. BOM判定からの確定
    if head.startswith(b"\xef\xbb\xbf"):
        return "utf-8", 1.0
    if head.startswith(b"\xff\xfe\x00\x00"):
        return "utf-32", 1.0
    if head.startswith(b"\x00\x00\xfe\xff"):
        return "utf-32", 1.0
    if head.startswith(b"\xff\xfe"):
        return "utf-16", 1.0
    if head.startswith(b"\xfe\xff"):
        return "utf-16", 1.0

    # 2. ASCII デコード試行
    try:
        data.decode("ascii")
        return "ascii", 1.0
    except UnicodeDecodeError:
        pass

    return None


def _detect_encoding(data: bytes, head: bytes = b"") -> tuple[str, float]:
    """
    chardet でエンコーディングと信頼度を推定する。
    chardet が利用不可の場合は ('unknown', 0.0) を返す。
    """
    fast_res = _detect_encoding_fast(data, head)
    if fast_res is not None:
        return fast_res

    if not _CHARDET_AVAILABLE or not data:
        return ("unknown", 0.0)
    result = chardet.detect(data)
    enc = result.get("encoding") or "unknown"
    conf = float(result.get("confidence") or 0.0)
    return (enc, conf)


def _detect_line_ending(data: bytes) -> tuple[str, int]:
    """
    バイト列から改行コードと行数を判定する。
    Returns:
        (line_ending_label, line_count)
        line_ending_label: "CRLF" | "LF" | "CR" | "mixed" | "N/A"
    """
    if not data:
        return ("LF", 0)

    has_crlf = b"\r\n" in data
    # CRLF を除いた残りで CR/LF を判定
    data_no_crlf = data.replace(b"\r\n", b"")
    has_cr_only = b"\r" in data_no_crlf
    has_lf_only = b"\n" in data_no_crlf

    # 行数は splitlines() で算出（Python の splitlines は \r\n, \r, \n すべて対応）
    line_count = len(data.splitlines())

    # 改行コード判定
    if has_crlf and not has_cr_only and not has_lf_only:
        le = "CRLF"
    elif has_lf_only and not has_crlf and not has_cr_only:
        le = "LF"
    elif has_cr_only and not has_crlf and not has_lf_only:
        le = "CR"
    elif not has_crlf and not has_cr_only and not has_lf_only:
        # 改行なし（1行のみ）
        le = "LF"
    else:
        le = "mixed"

    return le, line_count


def _detect_mime(path: Path) -> str:
    """mimetypes で MIME タイプを推定する。不明時は空文字を返す。"""
    mime, _ = mimetypes.guess_type(str(path))
    return mime or ""


# ── コアロジック ──────────────────────────────────────────────────────────────


def collect_metrics(path: Path, remove_prefix: str | None) -> dict:
    """1 ファイルのメトリクスを収集して辞書で返す。"""
    stat = path.stat()
    size = stat.st_size
    last_modified = datetime.datetime.fromtimestamp(
        stat.st_mtime, tz=datetime.timezone.utc
    ).isoformat()
    extension = path.suffix  # 拡張子（例: ".py"、なければ ""）
    mime_type = _detect_mime(path)
    file_path = _clean_path(str(path), remove_prefix)

    # 先頭バイトを読み込む（バイナリ判定・BOM 検出・エンコーディング/改行用データ収集を1回で実施）
    try:
        with open(path, "rb") as fp:
            full_data = fp.read(_ENCODING_DETECT_BYTES)
    except (OSError, PermissionError) as e:
        return {
            "file": file_path,
            "file_size_bytes": size,
            "is_binary": True,
            "encoding": "",
            "encoding_confidence": 0.0,
            "line_ending": "N/A",
            "line_count": 0,
            "extension": extension,
            "mime_type": mime_type,
            "has_bom": False,
            "last_modified": last_modified,
        }

    head = full_data[:_BINARY_CHECK_BYTES]
    is_binary = _detect_binary(head)
    has_bom = _detect_bom(head)

    if is_binary:
        return {
            "file": file_path,
            "file_size_bytes": size,
            "is_binary": True,
            "encoding": "",
            "encoding_confidence": 0.0,
            "line_ending": "N/A",
            "line_count": 0,
            "extension": extension,
            "mime_type": mime_type,
            "has_bom": has_bom,
            "last_modified": last_modified,
        }

    encoding, enc_conf = _detect_encoding(full_data, head)
    line_ending, line_count = _detect_line_ending(full_data)

    return {
        "file": file_path,
        "file_size_bytes": size,
        "is_binary": False,
        "encoding": encoding,
        "encoding_confidence": round(enc_conf, 4),
        "line_ending": line_ending,
        "line_count": line_count,
        "extension": extension,
        "mime_type": mime_type,
        "has_bom": has_bom,
        "last_modified": last_modified,
    }


def _collect_metrics_worker(args: tuple[Path, str | None]) -> tuple[Path, dict | Exception]:
    """ProcessPoolExecutorで実行する並列処理ワーカー"""
    path, remove_prefix = args
    try:
        return path, collect_metrics(path, remove_prefix)
    except Exception as e:
        return path, e


_COLUMNS = [
    "file",
    "file_size_bytes",
    "is_binary",
    "encoding",
    "encoding_confidence",
    "line_ending",
    "line_count",
    "extension",
    "mime_type",
    "has_bom",
    "last_modified",
]


def scan_directory(
    scan_dir: Path,
    output_csv: Path,
    remove_prefix: str | None = None,
    extra_excludes: list[str] | None = None,
) -> int:
    """
    scan_dir を再帰走査してファイルメトリクスを output_csv に書き出す。
    Returns:
        処理したファイル数
    """
    exclude_patterns = _DEFAULT_EXCLUDES + (extra_excludes or [])
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    files_to_process = []
    for root, dirs, files in os.walk(scan_dir, followlinks=False):
        root_path = Path(root)

        # 除外ディレクトリをフィルタ（in-place 変更で os.walk の枝刈り）
        dirs[:] = sorted([
            d for d in dirs
            if not _is_excluded(root_path / d, exclude_patterns)
        ])

        for filename in sorted(files):
            file_path = root_path / filename
            if _is_excluded(file_path, exclude_patterns):
                continue
            files_to_process.append(file_path)

    processed = 0
    import concurrent.futures
    tasks = [(f, remove_prefix) for f in files_to_process]

    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=_COLUMNS, extrasaction="ignore")
        writer.writeheader()

        with concurrent.futures.ProcessPoolExecutor() as executor:
            # Map retains the original sorting order
            results = executor.map(_collect_metrics_worker, tasks)
            for path, res in results:
                if isinstance(res, Exception):
                    print(f"[WARN] skipped {path}: {res}", file=sys.stderr)
                else:
                    writer.writerow(res)
                    processed += 1

    return processed


# ── CLI ───────────────────────────────────────────────────────────────────────


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="ディレクトリを再帰走査してファイルメトリクスを CSV に出力する。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("scan_dir", type=str, help="走査するルートディレクトリ")
    parser.add_argument("output_csv", type=str, help="出力 CSV ファイルパス")
    parser.add_argument(
        "--remove-prefix",
        type=str,
        default=None,
        metavar="PREFIX",
        help="ファイルパスから除去するプレフィックス",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="*",
        default=[],
        metavar="GLOB",
        help="追加の除外パターン（fnmatch 形式、複数指定可）",
    )

    args = parser.parse_args(argv)

    scan_dir = Path(args.scan_dir).expanduser().resolve()
    if not scan_dir.is_dir():
        print(f"[ERROR] scan_dir が見つかりません: {scan_dir}", file=sys.stderr)
        return 1

    output_csv = Path(args.output_csv).expanduser().resolve()

    if not _CHARDET_AVAILABLE:
        print(
            "[WARN] chardet がインストールされていません。エンコーディング検出は 'unknown' になります。",
            file=sys.stderr,
        )

    print(f"[INFO] scan_dir={scan_dir}")
    print(f"[INFO] output_csv={output_csv}")
    print(f"[INFO] remove_prefix={args.remove_prefix!r}")
    print(f"[INFO] extra_excludes={args.exclude}")

    count = scan_directory(
        scan_dir=scan_dir,
        output_csv=output_csv,
        remove_prefix=args.remove_prefix,
        extra_excludes=args.exclude or [],
    )

    print(f"[INFO] 処理完了: {count} ファイル → {output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
