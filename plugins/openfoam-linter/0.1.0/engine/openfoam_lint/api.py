"""Static OpenFOAM.com v2312 lint API exposed to the application host."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

from hpc_gui.openfoam_core import (
    DecodedSource,
    Diagnostic,
    MAX_CASE_BYTES,
    MAX_CASE_FILES,
    MAX_DICTIONARY_BYTES,
    MAX_MESH_BOUNDARY_BYTES,
    ParsedDictionary,
    SOURCE_DOCS,
    discover_case_files,
    discover_mesh_boundaries,
    is_dictionary_name,
    is_mesh_boundary_path,
    read_dictionary_file,
)

from .includes import include_diagnostics
from .rules import LintResult
from .rules_case import lint_case_layout
from .rules_dictionary import RULES as DICTIONARY_RULES, lint_dictionary
from .rules_boundary import RULES as BOUNDARY_RULES, lint_boundary_requirements
from .rules_mesh import lint_mesh_patch_consistency

CASE_RULES = {
    "OF-CASE-001": {"title": "Case root", "severity": "warning", "confidence": "contextual", "verification_level": "contextual"},
    "OF-CASE-002": {"title": "Missing include", "severity": "warning", "confidence": "contextual", "verification_level": "contextual"},
    "OF-CASE-003": {"title": "Unresolved includeEtc", "severity": "info", "confidence": "certain", "verification_level": "contextual"},
    "OF-CASE-004": {"title": "Unparsed include", "severity": "info", "confidence": "heuristic", "verification_level": "contextual"},
    "OF-SEC-004": {"title": "Include depth limit", "severity": "warning", "confidence": "structural", "verification_level": "contextual"},
    "OF-CTRL-001": {"title": "Control time interval", "severity": "warning", "confidence": "structural", "verification_level": "static"},
    "OF-CTRL-002": {"title": "Positive time step", "severity": "warning", "confidence": "structural", "verification_level": "static"},
    "OF-CTRL-003": {"title": "Positive write interval", "severity": "warning", "confidence": "structural", "verification_level": "static"},
    "OF-SOLVER-001": {"title": "Solver context", "severity": "warning", "confidence": "contextual", "verification_level": "contextual"},
    "OF-SOLVER-002": {"title": "Solver dictionaries", "severity": "warning", "confidence": "contextual", "verification_level": "contextual"},
    "OF-BC-001": {"title": "Boundary fields", "severity": "warning", "confidence": "contextual", "verification_level": "contextual"},
    "OF-BC-002": {"title": "Boundary condition type", "severity": "warning", "confidence": "contextual", "verification_level": "contextual"},
    "OF-PAR-001": {"title": "Parallel decomposition", "severity": "warning", "confidence": "contextual", "verification_level": "contextual"},
    "OF-PAR-002": {"title": "Cartesian decomposition dimensions", "severity": "warning", "confidence": "structural", "verification_level": "static"},
    "OF-MESH-001": {"title": "Mesh patch coverage", "severity": "warning", "confidence": "contextual", "verification_level": "contextual"},
    "OF-MESH-002": {"title": "Mesh patch metadata unverified", "severity": "info", "confidence": "contextual", "verification_level": "contextual"},
    "OF-CROSS-001": {"title": "Multi-region context", "severity": "info", "confidence": "contextual", "verification_level": "contextual"},
    "OF-CROSS-002": {"title": "Region declaration", "severity": "warning", "confidence": "contextual", "verification_level": "contextual"},
    "OF-CROSS-003": {"title": "Region initial fields", "severity": "warning", "confidence": "contextual", "verification_level": "contextual"},
    "OF-CROSS-004": {"title": "Shared initial fields", "severity": "info", "confidence": "contextual", "verification_level": "contextual"},
}
SUPPORTED_SUFFIXES = frozenset({".foam", ".dict"})
SUPPORTED_FILENAMES = frozenset({
    "controlDict", "fvSchemes", "fvSolution", "decomposeParDict", "blockMeshDict",
    "snappyHexMeshDict", "regionProperties", "transportProperties", "thermophysicalProperties",
    "turbulenceProperties", "fvOptions", "changeDictionaryDict", "topoSetDict",
    "surfaceFeatureExtractDict",
})


def _decode(data: bytes, path: str) -> tuple[str | None, Diagnostic | None]:
    try:
        return DecodedSource.from_bytes(data).text, None
    except UnicodeError as exc:
        return None, Diagnostic(
            "OF-DICT-005", "warning", "structural", path, 1, 1,
            f"Dictionary bytes are not valid UTF text ({type(exc).__name__}); the source was not modified.",
            "Open as raw source and confirm its encoding before linting.",
        )


def _lint_text_result(text: str, path: str) -> tuple[ParsedDictionary, tuple[Diagnostic, ...]]:
    return lint_dictionary(text, path=path)


def lint_text(text: str, *, file_name: str = "<memory>", options=None) -> LintResult:
    """Lint one in-memory dictionary without expanding includes or running directives."""
    _parsed, findings = _lint_text_result(str(text), str(file_name or "<memory>"))
    return LintResult(findings, (str(file_name or "<memory>"),))


def lint_files(
    files: Mapping[str, bytes | str],
    *,
    root: str | Path | None = None,
    case_context: bool | None = None,
) -> LintResult:
    """Lint a bounded set of case-relative source contents, useful for SFTP adapters."""
    parsed: dict[str, ParsedDictionary] = {}
    findings: list[Diagnostic] = []
    mesh_sources: dict[str, str] = {}
    checked: set[str] = set()
    for name, value in files.items():
        relative = str(name).replace("\\", "/")
        if is_mesh_boundary_path(relative):
            if isinstance(value, bytes):
                if len(value) > MAX_MESH_BOUNDARY_BYTES:
                    findings.append(Diagnostic(
                        "OF-MESH-002", "info", "contextual", relative, 1, 1,
                        "Mesh boundary metadata exceeds the bounded contextual scan limit; field/mesh patch coverage was not checked.",
                        "Select a bounded ASCII boundary file or inspect it with the matching OpenFOAM edition.",
                        SOURCE_DOCS, verification_level="contextual",
                    ))
                    continue
                text, issue = _decode(value, relative)
                if issue:
                    findings.append(issue)
                    continue
            else:
                text = str(value)
                if len(text.encode("utf-8")) > MAX_MESH_BOUNDARY_BYTES:
                    findings.append(Diagnostic(
                        "OF-MESH-002", "info", "contextual", relative, 1, 1,
                        "Mesh boundary metadata exceeds the bounded contextual scan limit; field/mesh patch coverage was not checked.",
                        "Select a bounded ASCII boundary file or inspect it with the matching OpenFOAM edition.",
                        SOURCE_DOCS, verification_level="contextual",
                    ))
                    continue
            mesh_sources[relative] = text
            checked.add(relative)
            continue
        if not is_dictionary_name(relative):
            continue
        if isinstance(value, bytes):
            text, issue = _decode(value, relative)
            if issue:
                findings.append(issue)
                continue
        else:
            text = str(value)
            if len(text.encode("utf-8")) > MAX_DICTIONARY_BYTES:
                findings.append(Diagnostic(
                    "OF-CASE-005", "warning", "heuristic", relative, 1, 1,
                    "Dictionary exceeds the per-file static lint size limit.",
                    "Review the file manually or select a smaller relevant dictionary.",
                ))
                continue
        document, file_findings = _lint_text_result(text, relative)
        parsed[relative] = document
        checked.add(relative)
        findings.extend(file_findings)
    if root is not None:
        findings.extend(include_diagnostics(Path(root), parsed))
    if case_context is None:
        case_context = root is not None or "system/controlDict" in parsed
    if case_context:
        findings.extend(lint_case_layout(parsed))
        findings.extend(lint_boundary_requirements(parsed))
        findings.extend(lint_mesh_patch_consistency(parsed, mesh_sources))
    return LintResult(tuple(findings), tuple(sorted(checked)))


def lint_paths(paths: Iterable[str | Path], options=None) -> LintResult:
    """Lint selected dictionaries or case folders; bounded and read-only."""
    selected = tuple(Path(item).expanduser() for item in paths)
    findings: list[Diagnostic] = []
    files_checked: list[str] = []
    for item in selected:
        try:
            if item.is_dir():
                root = item.resolve(strict=True)
                discovered = discover_case_files(root)
                if not discovered:
                    findings.append(Diagnostic(
                        "OF-CASE-001", "warning", "contextual", str(root), 1, 1,
                        "No supported dictionaries were found under system/, constant/, or 0/.",
                        "Select a case root or an individual OpenFOAM dictionary.",
                        verification_level="contextual",
                    ))
                    continue
                content = {file.relative_path: file.data for file in discovered}
                content.update(discover_mesh_boundaries(
                    root,
                    maximum_case_bytes=max(0, MAX_CASE_BYTES - sum(len(data) for data in content.values())),
                    maximum_files=max(0, MAX_CASE_FILES - len(content)),
                ))
                result = lint_files(content, root=root, case_context=True)
                findings.extend(result.diagnostics)
                files_checked.extend(str(root / file) for file in result.files_checked)
            elif item.is_file():
                file = read_dictionary_file(item)
                text, issue = _decode(file.data, str(file.absolute_path))
                if issue:
                    findings.append(issue)
                elif text is not None:
                    _parsed, file_findings = _lint_text_result(text, str(file.absolute_path))
                    findings.extend(file_findings)
                    files_checked.append(str(file.absolute_path))
            else:
                findings.append(Diagnostic(
                    "OF-CASE-006", "warning", "certain", str(item), 1, 1,
                    "Selected path does not exist.", "Check the selected path and permissions.",
                    verification_level="contextual",
                ))
        except (OSError, ValueError) as exc:
            findings.append(Diagnostic(
                "OF-CASE-006", "warning", "certain", str(item), 1, 1,
                f"Selected path could not be read: {exc}", "Check file permissions and symlink targets.",
                verification_level="contextual",
            ))
    return LintResult(tuple(findings), tuple(files_checked))


def rule_catalog() -> dict[str, dict[str, str]]:
    merged = {key: dict(value) for key, value in DICTIONARY_RULES.items()}
    merged.update({key: dict(value) for key, value in CASE_RULES.items()})
    merged.update({key: dict(value) for key, value in BOUNDARY_RULES.items()})
    merged["OF-DICT-005"] = {"title": "Text encoding", "severity": "warning", "confidence": "structural", "verification_level": "static"}
    merged["OF-CASE-005"] = {"title": "File size bound", "severity": "warning", "confidence": "heuristic", "verification_level": "static"}
    merged["OF-CASE-006"] = {"title": "Selected path", "severity": "warning", "confidence": "certain", "verification_level": "contextual"}
    merged["OF-SEC-003"] = {"title": "Include cycle", "severity": "warning", "confidence": "structural", "verification_level": "contextual"}
    for metadata in merged.values():
        metadata.setdefault("source", SOURCE_DOCS)
        metadata.setdefault("verification_level", "static")
    return merged


def supports_filename(name: str) -> bool:
    leaf = str(name).replace("\\", "/").rsplit("/", 1)[-1]
    return leaf in SUPPORTED_FILENAMES or Path(leaf).suffix.casefold() in SUPPORTED_SUFFIXES
