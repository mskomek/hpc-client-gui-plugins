"""Cluster-profile schema -> first compatible application release.

The plugin repository validates independently and never imports application
code, so this small table mirrors the application's canonical
``hpc_gui.plugins.schema_compat`` contract. The application-side
consumer-contract suite cross-checks the two tables to prevent drift.

Rules enforced before publication/installation:
- a payload may declare a ``requires_app`` floor at or above the first app
  release that implements its schema version;
- a floor below that release would advertise an install that must fail
  validation (the exact TRUBA 1.4.0 / released 1.5.8 regression).
"""

from __future__ import annotations

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

# First released application version that validates each schema version.
MIN_APP_VERSION_FOR_SCHEMA: dict[int, str] = {
    1: "1.4.0",
    2: "1.5.5",
    3: "1.5.9",
    4: "1.5.9",
}

# First release with the plugin registry/installer at all. Floors below this
# baseline cannot affect any released installer and are not false claims.
PLUGIN_INFRASTRUCTURE_VERSION = "1.4.0"


def minimum_app_version_for_schema(schema_version: object) -> str | None:
    try:
        key = int(schema_version)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return MIN_APP_VERSION_FOR_SCHEMA.get(key)


def _successor(version: Version) -> Version:
    release = list(version.release)
    release[-1] += 1
    return Version(".".join(str(part) for part in release))


def _minimum_admitted(requires_app: str) -> Version | None:
    """Lowest version admitted by the supported ``requires_app`` subset."""
    try:
        specifier = SpecifierSet(requires_app)
    except InvalidSpecifier:
        return None
    floor: Version | None = None
    for clause in specifier:
        operator = clause.operator
        raw = clause.version
        if operator in ("<", "<="):
            continue
        try:
            if raw.endswith(".*"):
                prefix = raw[: -len(".*")]
                candidate = Version(prefix if prefix.count(".") == 1 else prefix + ".0")
            else:
                candidate = Version(raw)
        except InvalidVersion:
            return None
        if operator == ">":
            candidate = _successor(candidate)
        if floor is None or candidate > floor:
            floor = candidate
    return floor if floor is not None else Version("0")


def schema_floor_error(schema_version: object, requires_app: str) -> str | None:
    """Return a problem string when the declared floor predates schema support."""
    minimum_app = minimum_app_version_for_schema(schema_version)
    if minimum_app is None:
        return None
    minimum = Version(minimum_app)
    if minimum <= Version(PLUGIN_INFRASTRUCTURE_VERSION):
        return None
    floor = _minimum_admitted(requires_app)
    if floor is None:
        return None
    if floor < minimum:
        return (
            f"cluster-profile schema {int(schema_version)} first requires app "
            f"{minimum_app}, but requires_app {requires_app!r} would also admit "
            f"older releases"
        )
    return None
