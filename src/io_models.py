from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import glob


def clean_path(path_str: object, remove_prefix: str | list[str] | None) -> str:
    if path_str is None or (isinstance(path_str, float) and path_str != path_str):
        return ""
    val = str(path_str).strip()
    if val.lower() in {"nan", "none", ""}:
        return ""
    val = val.replace("\\", "/").strip("/")
    
    prefixes: list[str] = []
    if isinstance(remove_prefix, str):
        if remove_prefix:
            prefixes.append(remove_prefix)
    elif isinstance(remove_prefix, list):
        prefixes = remove_prefix
        
    for prefix in prefixes:
        norm_prefix = prefix.replace("\\", "/").strip("/")
        if not norm_prefix:
            continue
        if val.startswith(norm_prefix + "/"):
            val = val[len(norm_prefix) + 1 :]
        elif val.startswith(norm_prefix):
            val = val[len(norm_prefix) :]
            
    if val.startswith("./"):
        val = val[2:]
    return val



@dataclass
class AnalysisInputs:
    und_csv: Path | None
    cloc_csv: Path | None
    pmd_xmls: list[Path]
    git_numstat: Path | None
    output_dir: Path
    remove_path_prefix: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class TaskResult:
    name: str
    executed: bool
    success: bool
    outputs: list[Path] = field(default_factory=list)
    summary_rows: list[dict] = field(default_factory=list)
    message: str = ""


SKIP_VALUES = {"false", "none", "-", ""}


def _is_skip(value: str) -> bool:
    return value.strip().lower() in SKIP_VALUES


def _resolve_optional_file(raw: str, label: str, warnings: list[str]) -> Path | None:
    if _is_skip(raw):
        warnings.append(f"{label}: skipped (not specified)")
        return None
    p = Path(raw).expanduser().resolve()
    if p.is_file():
        return p
    warnings.append(f"{label}: skipped (not found): {p}")
    return None


def _resolve_pmd_files(raw: str, warnings: list[str]) -> list[Path]:
    if _is_skip(raw):
        warnings.append("PMD: skipped (not specified)")
        return []

    candidates: list[str] = []
    if "," in raw:
        candidates = [s.strip() for s in raw.split(",") if s.strip()]
    elif ":" in raw:
        candidates = [s.strip() for s in raw.split(":") if s.strip()]
    else:
        candidates = [raw.strip()]

    files: list[Path] = []
    for candidate in candidates:
        matched = [Path(p).resolve() for p in glob.glob(candidate, recursive=True)]
        if matched:
            files.extend([p for p in matched if p.is_file()])
            continue

        p = Path(candidate).expanduser().resolve()
        if p.is_file():
            files.append(p)
        else:
            warnings.append(f"PMD: candidate not found: {candidate}")

    deduped = sorted(set(files))
    if not deduped:
        warnings.append("PMD: skipped (no xml files resolved)")
    return deduped


def resolve_inputs(
    und_csv_raw: str,
    cloc_csv_raw: str,
    pmd_xml_raw: str,
    git_numstat_raw: str,
    output_dir_raw: str,
    remove_path_prefix: str,
) -> AnalysisInputs:
    warnings: list[str] = []
    output_dir = Path(output_dir_raw).expanduser().resolve()

    und_csv = _resolve_optional_file(und_csv_raw, "Understand", warnings)
    cloc_csv = _resolve_optional_file(cloc_csv_raw, "CLOC", warnings)
    pmd_xmls = _resolve_pmd_files(pmd_xml_raw, warnings)
    git_numstat = _resolve_optional_file(git_numstat_raw, "GitNumstat", warnings)

    return AnalysisInputs(
        und_csv=und_csv,
        cloc_csv=cloc_csv,
        pmd_xmls=pmd_xmls,
        git_numstat=git_numstat,
        output_dir=output_dir,
        remove_path_prefix=remove_path_prefix,
        warnings=warnings,
    )
