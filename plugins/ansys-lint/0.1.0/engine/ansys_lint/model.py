"""Common diagnostic model for the ANSYS Script & Journal Linter.

The model is intentionally dependency-free so the engine runs offline on
CPython >= 3.10 with nothing but the standard library.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

ENGINE_VERSION = "0.1.0"

DEFAULT_TARGET_VERSION = "25.2"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {"info": 0, "warning": 1, "error": 2}[self.value]


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExecMode(str, Enum):
    BATCH = "batch"
    HEADLESS = "headless"
    INTERACTIVE = "interactive"

    @property
    def is_unattended(self) -> bool:
        return self in (ExecMode.BATCH, ExecMode.HEADLESS)


class TargetOS(str, Enum):
    LINUX = "linux"
    WINDOWS = "windows"


class Strictness(str, Enum):
    LENIENT = "lenient"
    STRICT = "strict"


@dataclass(frozen=True)
class CoordMapper:
    """Maps inner (line, column) coordinates of embedded content back to the
    outer file. ``note`` is appended to explanations of mapped diagnostics."""

    map_line_col: Any  # Callable[[int, int], tuple[int, int]]
    note: str = ""


@dataclass(frozen=True)
class DetectionInfo:
    """Outcome of product/dialect/version detection for one input."""

    product: str = "unknown"
    dialect: str = "unknown"
    detected_version: str = ""
    supported_versions: tuple[str, ...] = ()
    confidence: float = 0.0
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["supported_versions"] = list(self.supported_versions)
        data["evidence"] = list(self.evidence)
        return data


@dataclass(frozen=True)
class LintOptions:
    """User-selectable lint settings shared by the CLI and the GUI page."""

    target_version: str = DEFAULT_TARGET_VERSION
    exec_mode: ExecMode = ExecMode.BATCH
    target_os: TargetOS = TargetOS.LINUX
    strictness: Strictness = Strictness.LENIENT
    dialect_override: str | None = None
    launch_command: str = ""
    force: bool = False


@dataclass
class Diagnostic:
    """One linter finding.

    ``is_heuristic`` separates exact/structural/catalog-backed findings from
    recommendations that may require manual verification. Catalog-backed and
    documentation-backed findings carry a ``source_id`` resolved through the
    provenance registry.
    """

    code: str
    severity: Severity
    message: str
    line: int | None = None
    column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    confidence: Confidence = Confidence.MEDIUM
    product: str = ""
    dialect: str = ""
    detected_version: str = ""
    supported_versions: tuple[str, ...] = ()
    file_path: str = ""
    explanation: str = ""
    suggested_fix: str = ""
    source_id: str = ""
    source_url: str = ""
    source_title: str = ""
    is_heuristic: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["severity"] = self.severity.value
        data["confidence"] = self.confidence.value
        data["supported_versions"] = list(self.supported_versions)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Diagnostic":
        payload = dict(data)
        payload["severity"] = Severity(payload.get("severity", "warning"))
        payload["confidence"] = Confidence(payload.get("confidence", "medium"))
        payload["supported_versions"] = tuple(payload.get("supported_versions", ()))
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{key: value for key, value in payload.items() if key in known})

    def sort_key(self) -> tuple[int, int, int, int, str]:
        return (
            self.line if self.line is not None else 10**9,
            self.column if self.column is not None else 10**9,
            self.severity.rank,
            0 if not self.is_heuristic else 1,
            self.code,
        )


@dataclass
class FileResult:
    """Diagnostics plus detection metadata for one analyzed file."""

    file_path: str = ""
    detection: DetectionInfo = field(default_factory=DetectionInfo)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        counts = {"error": 0, "warning": 0, "info": 0}
        for diagnostic in self.diagnostics:
            counts[diagnostic.severity.value] += 1
        return counts

    def sorted_diagnostics(self) -> list[Diagnostic]:
        return sorted(self.diagnostics, key=lambda d: d.sort_key())


@dataclass
class LintRunResult:
    """Aggregated result over one or many inputs."""

    files: list[FileResult] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        totals = {"error": 0, "warning": 0, "info": 0}
        for result in self.files:
            for key, value in result.summary.items():
                totals[key] += value
        return totals

    def max_severity(self) -> Severity | None:
        worst: Severity | None = None
        for result in self.files:
            for diagnostic in result.diagnostics:
                if worst is None or diagnostic.severity.rank > worst.rank:
                    worst = diagnostic.severity
        return worst
