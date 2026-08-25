"""Cross-cutting HPC, portability and security rules.

These helpers are dialect-independent: parsers feed them extracted string
literals together with their original coordinates, and receive fully formed
finding dictionaries back. All findings produced here are explicitly marked
as heuristic unless noted otherwise - they highlight risk, never prove
runtime failure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .model import Confidence, Severity, TargetOS

DRIVE_LETTER_RE = re.compile(r"\b[A-Za-z]:[\\/]")
UNC_PATH_RE = re.compile(r"\\\\[A-Za-z0-9_.\-]+\\")
BACKSLASH_PATH_RE = re.compile(r"(?:[A-Za-z0-9_.\-]+\\)+[A-Za-z0-9_.\-]+")
WINDOWS_ENV_RE = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)%")
POSIX_ABS_RE = re.compile(r"(?<![\w])/[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)+")
HOME_TILDE_RE = re.compile(r"(?:^|[\s\"'=])~/[\S]+")
INSTALL_PATH_HINTS = (
    "program files",
    "/usr/ansys_inc",
    "/ansys_inc",
    "c:/program files",
    "%programfiles%",
    "%appdata%",
    "%userprofile%",
    "%localappdata%",
)
DESKTOP_ONLY_ENV_VARS = frozenset(
    {"APPDATA", "USERPROFILE", "LOCALAPPDATA", "PROGRAMFILES", "HOMEDRIVE", "HOMEPATH"}
)
PATH_CHARS_RE = re.compile(r"[\w./\\:%~\-]+")


@dataclass(frozen=True)
class Finding:
    """A ready-to-convert diagnostic payload produced by a shared rule."""

    code: str
    severity: Severity
    message: str = ""
    explanation: str = ""
    suggested_fix: str = ""
    confidence: Confidence = Confidence.MEDIUM
    is_heuristic: bool = True

    def as_dict(self, line: int | None, column: int | None) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "line": line,
            "column": column,
            "explanation": self.explanation,
            "suggested_fix": self.suggested_fix,
            "confidence": self.confidence,
            "is_heuristic": self.is_heuristic,
        }


def looks_like_path(value: str) -> bool:
    if len(value) < 2 or value.isdigit():
        return False
    if DRIVE_LETTER_RE.search(value) or UNC_PATH_RE.search(value):
        return True
    if "/" in value and any(ch.isalpha() for ch in value):
        return True
    if "\\" in value:
        return True
    if value.startswith(("./", "../", "~/")):
        return True
    if WINDOWS_ENV_RE.search(value):
        return True
    lowered = value.lower()
    return any(hint in lowered for hint in INSTALL_PATH_HINTS)


def scan_path_literal(
    value: str,
    *,
    target_os: TargetOS,
    line: int,
    column: int,
    label: str = "path",
) -> list[Finding]:
    """Check one extracted path-like literal against portability rules."""
    findings: list[Finding] = []
    stripped = value.strip().strip("\"'")
    if not stripped or not looks_like_path(stripped):
        return findings

    if target_os is TargetOS.LINUX:
        if DRIVE_LETTER_RE.search(stripped):
            findings.append(
                Finding(
                    code="PORTABILITY_WINDOWS_PATH",
                    severity=Severity.WARNING,
                    message=f"{label} '{stripped}' uses a Windows drive letter.",
                    explanation=(
                        "The lint target is Linux. Windows-style absolute paths "
                        "(for example C:\\...) do not exist on compute nodes and "
                        "will fail at runtime or silently resolve to nonsense."
                    ),
                    suggested_fix=(
                        "Use a relative path inside the job directory or a cluster "
                        "scratch/home path such as $SCRATCH/example."
                    ),
                    confidence=Confidence.HIGH,
                    is_heuristic=False,
                )
            )
        elif BACKSLASH_PATH_RE.search(stripped) and "/" not in stripped:
            findings.append(
                Finding(
                    code="PORTABILITY_BACKSLASH_PATH",
                    severity=Severity.WARNING,
                    message=f"{label} '{stripped}' separates directories with backslashes.",
                    explanation=(
                        "Backslash-separated paths are Windows conventions; Linux "
                        "treats the backslash as part of the file name."
                    ),
                    suggested_fix="Replace backslashes with forward slashes ('/').",
                    confidence=Confidence.HIGH,
                    is_heuristic=False,
                )
            )
        if WINDOWS_ENV_RE.search(stripped):
            var_match = WINDOWS_ENV_RE.search(stripped)
            env_name = (var_match.group(1).upper() if var_match else "").upper()
            extra = ""
            if env_name in DESKTOP_ONLY_ENV_VARS:
                extra = (
                    f" {env_name} is a Windows desktop variable and is normally "
                    "absent on compute nodes."
                )
            findings.append(
                Finding(
                    code="PORTABILITY_WINDOWS_ENV_VAR",
                    severity=Severity.WARNING,
                    message=f"{label} '{stripped}' uses %VAR% style environment variables.{extra}",
                    explanation=(
                        "%VAR% expansion is a Windows shell feature; Slurm/Linux jobs "
                        "use $VAR syntax and the named desktop variables usually do "
                        "not exist on compute nodes." + extra
                    ),
                    suggested_fix="Use $VAR syntax and verify the variable exists on the compute nodes.",
                    confidence=Confidence.HIGH,
                    is_heuristic=False,
                )
            )
        lowered = stripped.lower()
        if any(lowered.startswith(hint) or f" {hint}" in lowered for hint in INSTALL_PATH_HINTS):
            findings.append(
                Finding(
                    code="PORTABILITY_INSTALL_PATH",
                    severity=Severity.WARNING,
                    message=f"{label} '{stripped}' points into a local installation directory.",
                    explanation=(
                        "Hard-coded local installation locations rarely exist on HPC "
                        "login or compute nodes; module systems provide the software "
                        "instead."
                    ),
                    suggested_fix="Reference the software through the cluster module/environment setup.",
                )
            )
        if POSIX_ABS_RE.fullmatch(stripped) or stripped.startswith("/"):
            findings.append(
                Finding(
                    code="PORTABILITY_ABSOLUTE_PATH",
                    severity=Severity.INFO,
                    message=f"{label} '{stripped}' is an absolute path.",
                    explanation=(
                        "Absolute paths break reproducibility when the job runs from a "
                        "different directory, user, or cluster."
                    ),
                    suggested_fix="Prefer paths relative to the submitted job directory.",
                )
            )
    if " " in stripped and "=" not in stripped.split(" ")[0]:
        findings.append(
            Finding(
                code="PORTABILITY_UNQUOTED_SPACES",
                severity=Severity.INFO,
                message=f"{label} '{stripped}' contains spaces.",
                explanation=(
                    "Paths with spaces must be quoted everywhere they are used; "
                    "unquoted occurrences split into multiple arguments."
                ),
                suggested_fix="Quote the path or remove spaces from names used in batch scripts.",
            )
        )
    return findings


def dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str]] = set()
    unique: list[Finding] = []
    for finding in findings:
        key = (finding.code, finding.message)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def case_insensitive_duplicates(names: list[tuple[str, int]]) -> list[tuple[str, str, int, int]]:
    """Return pairs of referenced file names differing only by case.

    Linux filesystems are case-sensitive; two references that differ only by
    case point at two different files even though they look identical.
    """
    lowered: dict[str, tuple[str, int]] = {}
    pairs: list[tuple[str, str, int, int]] = []
    for name, line in names:
        key = name.lower()
        if key in lowered and lowered[key][0] != name:
            first_name, first_line = lowered[key]
            pairs.append((first_name, name, first_line, line))
        elif key not in lowered:
            lowered[key] = (name, line)
    return pairs
