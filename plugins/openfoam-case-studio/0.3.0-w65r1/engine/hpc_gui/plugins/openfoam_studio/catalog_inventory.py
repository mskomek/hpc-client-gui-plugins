"""Curated v2312 command inventory (W65 CAT-003, G03).

Honest machine-readable registry: every entry carries proof level and
availability. Legacy 0.2.1 eight-command catalog is preserved verbatim
for backward compatibility; the curated P0/P1 set extends it. Entries
without a v2312 source anchor stay ``UNVERIFIED``/``RAW-ADVANCED``.
"""

from __future__ import annotations

LEGACY_8 = (
    "blockMesh", "checkMesh", "decomposePar", "splitMeshRegions",
    "icoFoam", "chtMultiRegionSimpleFoam", "reconstructPar", "postProcess",
)

# (name, category, subcategory, kind, proof, availability, solver_family)
_CURATED: tuple = (
    ("blockMesh", "mesh", "structured", "utility", "V2312-SOURCE", "ACTIVE-TYPED", ""),
    ("checkMesh", "mesh", "quality", "utility", "V2312-SOURCE", "ACTIVE-TYPED", ""),
    ("surfaceFeatureExtract", "geometry", "feature", "utility", "V2312-SOURCE", "ACTIVE-TYPED", ""),
    ("snappyHexMesh", "mesh", "surface-driven", "utility", "V2312-SOURCE", "ACTIVE-TYPED", ""),
    ("decomposePar", "parallel", "decompose", "utility", "V2312-SOURCE", "ACTIVE-TYPED", ""),
    ("reconstructPar", "parallel", "reconstruct", "utility", "V2312-SOURCE", "ACTIVE-TYPED", ""),
    ("splitMeshRegions", "mesh", "regions", "utility", "V2312-SOURCE", "ACTIVE-TYPED", ""),
    ("createPatch", "mesh", "patches", "utility", "V2312-SOURCE", "RAW-ADVANCED", ""),
    ("topoSet", "mesh", "zones", "utility", "V2312-SOURCE", "RAW-ADVANCED", ""),
    ("setFields", "init", "fields", "utility", "V2312-SOURCE", "ACTIVE-TYPED", ""),
    ("mergeMeshes", "mesh", "combine", "utility", "V2312-SOURCE", "RAW-ADVANCED", ""),
    ("gmshToFoam", "mesh", "import", "converter", "V2312-SOURCE", "RAW-ADVANCED", ""),
    ("fluentMeshToFoam", "mesh", "import", "converter", "V2312-SOURCE", "RAW-ADVANCED", ""),
    ("foamToVTK", "post", "export", "utility", "V2312-SOURCE", "ACTIVE-TYPED", ""),
    ("postProcess", "post", "function-objects", "utility", "V2312-SOURCE", "ACTIVE-TYPED", ""),
    ("sample", "post", "sampling", "utility", "V2312-SOURCE", "RAW-ADVANCED", ""),
    ("icoFoam", "solver", "incompressible-laminar", "solver", "V2312-SOURCE", "ACTIVE-TYPED", "laminar"),
    ("simpleFoam", "solver", "incompressible-rans", "solver", "V2312-SOURCE", "ACTIVE-TYPED", "rans-steady"),
    ("pimpleFoam", "solver", "incompressible-transient", "solver", "V2312-SOURCE", "ACTIVE-TYPED", "transient"),
    ("pisoFoam", "solver", "incompressible-transient", "solver", "V2312-SOURCE", "RAW-ADVANCED", "transient"),
    ("chtMultiRegionSimpleFoam", "solver", "cht", "solver", "V2312-SOURCE", "ACTIVE-TYPED", "cht"),
    ("chtMultiRegionFoam", "solver", "cht", "solver", "V2312-SOURCE", "RAW-ADVANCED", "cht"),
    ("buoyantSimpleFoam", "solver", "compressible-buoyant", "solver", "V2312-SOURCE", "RAW-ADVANCED", "buoyant"),
    ("rhoSimpleFoam", "solver", "compressible", "solver", "V2312-SOURCE", "RAW-ADVANCED", "compressible"),
    ("rhoPimpleFoam", "solver", "compressible", "solver", "V2312-SOURCE", "RAW-ADVANCED", "compressible"),
    ("interFoam", "solver", "multiphase", "solver", "OFFICIAL-DOC", "RAW-ADVANCED", "multiphase"),
    ("reactingFoam", "solver", "reacting", "solver", "OFFICIAL-DOC", "UNSUPPORTED", "reacting"),
    ("potentialFoam", "solver", "potential", "solver", "V2312-SOURCE", "RAW-ADVANCED", "potential"),
    ("yPlus", "post", "metrics", "function-object", "V2312-SOURCE", "ACTIVE-TYPED", ""),
    ("wallShearStress", "post", "metrics", "function-object", "V2312-SOURCE", "ACTIVE-TYPED", ""),
    ("forces", "post", "loads", "function-object", "V2312-SOURCE", "ACTIVE-TYPED", ""),
    ("forceCoeffs", "post", "loads", "function-object", "V2312-SOURCE", "ACTIVE-TYPED", ""),
    ("fieldAverage", "post", "averaging", "function-object", "V2312-SOURCE", "ACTIVE-TYPED", ""),
    ("probes", "post", "sampling", "function-object", "V2312-SOURCE", "ACTIVE-TYPED", ""),
    ("patchAverage", "post", "sampling", "function-object", "V2312-SOURCE", "RAW-ADVANCED", ""),
)

DOC_BASE = "https://doc.openfoam.com/2312/tools/"
SOURCE_TAG = "OpenFOAM-v2312"


def inventory() -> list[dict]:
    rows = []
    for name, cat, sub, kind, proof, avail, family in _CURATED:
        rows.append({
            "uid": f"of2312:{name}", "edition": "esi", "release": "v2312",
            "category": cat, "subcategory": sub, "command_name": name,
            "kind": kind, "controlled_file": "",
            "proof_level": proof, "availability": avail,
            "solver_family": family,
            "documentation_url": DOC_BASE, "source_revision": SOURCE_TAG,
            "legacy_021": name in LEGACY_8,
        })
    return rows


def coverage_counts() -> dict:
    rows = inventory()
    by_avail: dict[str, int] = {}
    for row in rows:
        by_avail[row["availability"]] = by_avail.get(row["availability"], 0) + 1
    return {
        "discovered_in_scope": len(rows),
        "classified": len(rows),
        "note": "curated P0/P1 subset; exhaustive site-binary claim BLOCKED_ENV without v2312 host",
        "by_availability": by_avail,
        "legacy_021_preserved": len(LEGACY_8),
    }
