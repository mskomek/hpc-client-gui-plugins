"""Source-provenance registry.

Every catalog-backed or documentation-backed diagnostic must reference a
provenance entry stored in ``data/sources.json``. The registry enforces the
project's honesty rules:

- only minimal metadata is stored (identifier, URL, title, Ansys release and
  a one-line original-language summary written by this project);
- no manual content is ever copied from the Ansys documentation;
- links are opened only on explicit user request; linting never touches the
  network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


class ProvenanceError(KeyError):
    """Raised when a rule references an unknown source id."""


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    url: str
    title: str
    product: str
    release: str
    note: str = ""


@lru_cache(maxsize=1)
def _load() -> dict[str, SourceRef]:
    path = DATA_DIR / "sources.json"
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    refs: dict[str, SourceRef] = {}
    for entry in raw.get("sources", []):
        ref = SourceRef(
            source_id=str(entry["id"]),
            url=str(entry["url"]),
            title=str(entry["title"]),
            product=str(entry.get("product", "")),
            release=str(entry.get("release", "")),
            note=str(entry.get("note", "")),
        )
        refs[ref.source_id] = ref
    return refs


def get_source(source_id: str) -> SourceRef:
    try:
        return _load()[source_id]
    except KeyError as exc:
        raise ProvenanceError(
            f"unknown provenance id {source_id!r}; every catalog-backed rule "
            "must reference a registered official source"
        ) from exc


def all_sources() -> list[SourceRef]:
    return sorted(_load().values(), key=lambda ref: (ref.product, ref.source_id))


def resolve(source_id: str) -> dict[str, str]:
    """Return the flattened provenance fields for a Diagnostic."""
    ref = get_source(source_id)
    return {
        "source_id": ref.source_id,
        "source_url": ref.url,
        "source_title": ref.title,
    }
