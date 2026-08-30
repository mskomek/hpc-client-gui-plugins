"""Confidence-based product/dialect detection.

Extension alone is never sufficient for ambiguous formats (.py, .dat,
.log, .js). Each candidate dialect contributes a base score from the file
extension plus additive boosts from content signatures, header comments,
declared versions and the surrounding launch command. The dispatcher in
``api.py`` decides whether detection is confident enough to lint or
whether the user must choose a dialect explicitly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .dialects import designmodeler as dm_module
from .dialects import spaceclaim as sc_module
from .dialects import sysc as sysc_module
from .dialects import workbench as wb_module
from .dialects.fluent import normalize_set_tui_value

AUTO_THRESHOLD = 0.55
LOW_THRESHOLD = 0.35

_TUI_COMMAND_RE = re.compile(r"^\s*/[a-z][\w/\-]*", re.MULTILINE)
_MAPDL_TOKEN_RE = re.compile(r"^\s*[/A-Z*][A-Z0-9_]{2,}\b", re.MULTILINE)
_ICEM_RE = re.compile(r"\bic_[a-z_]+\s*\(")
_CCL_HEADER_RE = re.compile(r"^\S[^\n:=]{0,60}:", re.MULTILINE)
_AEDT_RE = re.compile(r"\bo(Desktop|Project|Design|Editor)\b")
_MECH_RE = re.compile(r"\bExtAPI\b|\bDataModel\.|\bQuantity\(")


@dataclass(frozen=True)
class Candidate:
    dialect: str
    confidence: float
    evidence: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DetectionOutcome:
    dialect: str = "unknown"
    product: str = "unknown"
    confidence: float = 0.0
    evidence: tuple[str, ...] = ()
    candidates: tuple[Candidate, ...] = ()
    detected_version: str = ""

    @property
    def is_actionable(self) -> bool:
        return self.confidence >= AUTO_THRESHOLD


def _fluent_boost(text: str) -> tuple[float, list[str]]:
    boost = 0.0
    evidence: list[str] = []
    hits = _TUI_COMMAND_RE.findall(text)
    if hits:
        boost += min(0.35, 0.12 * len(hits))
        evidence.append(f"{len(hits)} TUI-style commands")
    if "set-tui-version" in text:
        boost += 0.2
        evidence.append("set-tui-version declaration")
    return boost, evidence


def _mapdl_boost(signature_text: str) -> tuple[float, list[str]]:
    """Boost only when tokens actually appear in the shipped MAPDL catalog.

    Uppercase prose (error logs shout AT / NOT / ERROR ...) must never look
    like an APDL batch file.
    """
    hits = _MAPDL_TOKEN_RE.findall(signature_text)
    if len(hits) < 2:
        return 0.0, []
    try:
        from .dialects.mapdl import load_catalog

        catalog = load_catalog()["commands"]
    except Exception:  # pragma: no cover - catalog always ships
        catalog = None
    if catalog is None:
        boost = min(0.4, 0.1 * max(len(hits), 2))
        return boost, [f"{len(hits)} uppercase command tokens"]
    known = sum(
        1
        for token in hits[:120]
        if token.strip("/*").upper() in catalog or token.upper() in catalog
    )
    if known < 2:
        return 0.03, [f"{len(hits)} uppercase tokens, none in the MAPDL catalog"]
    boost = min(0.5, 0.12 * known)
    return boost, [f"{known} catalogued MAPDL commands"]


def detect(file_name: str, text: str, launch_command: str = "") -> DetectionOutcome:
    lowered_name = (file_name or "").lower()

    # Signature scanning is prefix-capped: huge non-Ansys files (vendored
    # bundles, transcripts) must not dominate scan time, and every real
    # Ansys header/signature lives at the top of a file.
    signature_text = text[:262144]

    # ---- Fluent version hint -------------------------------------------------
    detected_version = ""
    match = re.search(r"set-tui-version\s+([0-9Rr. ]+)", signature_text)
    if match:
        normalized = normalize_set_tui_value(match.group(1))
        if normalized:
            detected_version = normalized

    wb_score, wb_evidence = wb_module.signature_score(lowered_name, signature_text)
    dm_score, dm_evidence = dm_module.signature_score(lowered_name, signature_text)
    sc_score, sc_evidence = sc_module.signature_score(lowered_name, signature_text)

    fluent_base = 0.6 if lowered_name.endswith(".jou") else 0.05
    fluent_boost, fluent_evidence = _fluent_boost(signature_text)

    mapdl_ext = {".dat": 0.25, ".inp": 0.3, ".mac": 0.55, ".log": 0.15}.get(
        _suffix(lowered_name), 0.03
    )
    mapdl_boost, mapdl_evidence = _mapdl_boost(signature_text)

    icem_base = 0.75 if lowered_name.endswith(".rpl") else 0.05
    icem_hits = len(_ICEM_RE.findall(signature_text))
    icem_boost = min(0.25, 0.08 * icem_hits) if icem_hits else 0.0
    icem_evidence = [f"{icem_hits} ic_* commands"] if icem_hits else []

    ccl_ext = {
        ".pre": 0.85,
        ".ccl": 0.62,
        ".cse": 0.9,
        ".cst": 0.85,
        ".tse": 0.9,
        ".tst": 0.85,
    }.get(_suffix(lowered_name), 0.02)
    ccl_headers = len(_CCL_HEADER_RE.findall(text[:4000]))
    ccl_boost = min(0.15, 0.04 * ccl_headers) if ccl_ext < 0.8 else 0.0
    ccl_evidence = [f"{ccl_headers} CCL-style headers"] if ccl_boost else []
    if lowered_name.endswith(".pre"):
        ccl_evidence.insert(0, "extension .pre (CFX-Pre session)")
    elif lowered_name.endswith(".cse"):
        ccl_evidence.insert(0, "extension .cse (CFD-Post session)")
    elif lowered_name.endswith((".tse", ".tst")):
        ccl_evidence.insert(0, "TurboGrid session/state extension")

    motion_base = 0.9 if lowered_name.endswith(".dfjnl") else 0.02
    motion_evidence = ["extension .dfjnl"] if lowered_name.endswith(".dfjnl") else []
    if not motion_evidence and text.lstrip().startswith("<?xml"):
        motion_base = 0.08
        motion_evidence.append("XML content")

    sysc_base = 0.05
    sysc_evidence: list[str] = []
    if sysc_module.is_sysc_script(signature_text):
        sysc_base = 0.55
        sysc_evidence.append("System Coupling datamodel calls")

    mech_base = 0.65 if lowered_name.endswith(".mcr") else 0.05
    mech_evidence: list[str] = []
    if lowered_name.endswith(".mcr"):
        mech_evidence.append("extension .mcr (recorded macro)")
    if _MECH_RE.search(signature_text):
        mech_base += 0.52 if lowered_name.endswith(".py") else 0.3
        mech_evidence.append("ExtAPI/DataModel signatures")

    aedt_base = 0.05
    aedt_evidence: list[str] = []
    aedt_hits = len(_AEDT_RE.findall(signature_text))
    if aedt_hits >= 2:
        aedt_base += 0.5 + 0.04 * min(aedt_hits, 6)
        aedt_evidence.append(f"{aedt_hits} oDesktop-family signatures")

    vbs_base = 0.15 if lowered_name.endswith(".vbs") else 0.01
    vbs_evidence = ["extension .vbs"] if lowered_name.endswith(".vbs") else []

    py_base = 0.18 if lowered_name.endswith(".py") else 0.0
    py_evidence = [".py extension alone is ambiguous"] if lowered_name.endswith(".py") else []

    launch_lower = (launch_command or "").lower()
    launch_evidence: dict[str, str] = {}
    if "fluent" in launch_lower:
        fluent_boost += 0.2
        launch_evidence["fluent"] = "launch command mentions fluent"
    if "runwb2" in launch_lower:
        wb_score = min(0.99, wb_score + 0.3)
        launch_evidence["workbench"] = "launch command mentions runwb2"
    if "systemcoupling" in launch_lower:
        sysc_base += 0.25
        launch_evidence["system-coupling"] = "launch command mentions systemcoupling"
    if "cfxtg" in launch_lower:
        ccl_boost += 0.2
        launch_evidence["turbo-grid"] = "launch command mentions cfxtg"
    if "mapdl" in launch_lower or "ansys" in launch_lower.split() :
        mapdl_boost += 0.2
        launch_evidence["mapdl"] = "launch command mentions MAPDL/ANSYS"

    candidates = [
        Candidate("fluent", min(0.99, fluent_base + fluent_boost), tuple(fluent_evidence + [launch_evidence.get("fluent", "")] if launch_evidence.get("fluent") else fluent_evidence)),
        Candidate("mapdl", min(0.99, mapdl_ext + mapdl_boost), tuple(mapdl_evidence + ([launch_evidence["mapdl"]] if "mapdl" in launch_evidence else []))),
        Candidate("workbench", wb_score, tuple(wb_evidence)),
        Candidate("designmodeler-jscript", dm_score, tuple(dm_evidence)),
        Candidate("spaceclaim-python", sc_score, tuple(sc_evidence)),
        Candidate("icem-replay-tcl", min(0.99, icem_base + icem_boost), tuple(icem_evidence)),
        Candidate("sysc-python", min(0.99, sysc_base + (py_base * 0.5)), tuple(sysc_evidence)),
        Candidate("mechanical-python", min(0.99, mech_base), tuple(mech_evidence)),
        Candidate("aedt-python", min(0.99, aedt_base + py_base * 0.5), tuple(aedt_evidence)),
        Candidate("motion-xml", motion_base, tuple(motion_evidence)),
    ]

    # CCL family: pick the concrete variant by extension.
    ccl_variant = {
        ".pre": ("cfx-pre-session", "cfx"),
        ".ccl": ("ccl", "cfx"),
        ".cse": ("cfd-post-session", "cfd-post"),
        ".cst": ("cfd-post-state", "cfd-post"),
        ".tse": ("turbo-grid-session", "turbo-grid"),
        ".tst": ("turbo-grid-state", "turbo-grid"),
    }.get(_suffix(lowered_name))
    if ccl_variant:
        candidates.append(Candidate(ccl_variant[0], min(0.99, ccl_ext + ccl_boost), tuple(ccl_evidence)))
    elif ccl_boost:
        candidates.append(Candidate("ccl", min(0.99, ccl_ext + ccl_boost), tuple(ccl_evidence)))

    # Legacy mechanical macro variants.
    if lowered_name.endswith(".js") and dm_score < AUTO_THRESHOLD:
        candidates.append(Candidate("mechanical-jscript", vbs_base + 0.05, tuple(vbs_evidence)))
    if lowered_name.endswith(".vbs"):
        candidates.append(Candidate("aedt-vbscript", vbs_base + (_AEDT_RE and 0.1 or 0.0), tuple(vbs_evidence)))
        candidates.append(Candidate("mechanical-vbscript", vbs_base, tuple(vbs_evidence)))

    # Generic python fallback candidate keeps the ambiguity explicit.
    if lowered_name.endswith(".py"):
        best_product = max(candidates, key=lambda c: c.confidence)
        if best_product.confidence < LOW_THRESHOLD + 0.1:
            candidates.append(Candidate("__generic_python__", py_base + 0.05, tuple(py_evidence)))

    # A .log file is almost never executable script source: captured session
    # output can mention product APIs (GetRootPart, oDesktop ...) without
    # being a Discovery/AEDT journal. Only the MAPDL path may cross the
    # auto-lint threshold for logs - replayable Jobname.log inputs carry
    # genuine catalogued APDL commands.
    if _suffix(lowered_name) == ".log":
        candidates = [
            Candidate(
                c.dialect,
                min(c.confidence, 0.50),
                c.evidence + (".log content ceiling",),
            )
            if c.dialect != "mapdl" and c.confidence > 0.50
            else c
            for c in candidates
        ]

    candidates.sort(key=lambda c: c.confidence, reverse=True)
    best = candidates[0] if candidates else Candidate("unknown", 0.0)

    product_for = {
        "fluent": "fluent",
        "mapdl": "mapdl",
        "workbench": "workbench",
        "designmodeler-jscript": "designmodeler",
        "spaceclaim-python": "spaceclaim",
        "icem-replay-tcl": "icem-cfd",
        "sysc-python": "system-coupling",
        "mechanical-python": "mechanical",
        "mechanical-jscript": "mechanical",
        "mechanical-vbscript": "mechanical",
        "aedt-python": "aedt",
        "aedt-vbscript": "aedt",
        "aqwa-jscript": "aqwa",
        "motion-xml": "motion",
        "meshing-sendcommand": "meshing",
        "__generic_python__": "unknown",
    }
    product = product_for.get(best.dialect, best.dialect.split("-")[0] if best.dialect != "unknown" else "unknown")
    if best.dialect.startswith(("cfx", "cfd-post", "turbo-grid", "ccl")):
        product = {"cfx-pre-session": "cfx", "ccl": "cfx", "cfd-post-session": "cfd-post", "cfd-post-state": "cfd-post", "turbo-grid-session": "turbo-grid", "turbo-grid-state": "turbo-grid"}[best.dialect]

    return DetectionOutcome(
        dialect=best.dialect,
        product=product,
        confidence=round(best.confidence, 3),
        evidence=best.evidence,
        candidates=tuple(candidates),
        detected_version=detected_version,
    )


def _suffix(name: str) -> str:
    dot = name.rfind(".")
    return name[dot:] if dot >= 0 else ""
