from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.metadata import packages_distributions
from pathlib import Path

from packaging.utils import canonicalize_name


@dataclass(frozen=True)
class Candidate:
    name: str
    sources: tuple[str, ...]
    references: tuple[str, ...] = ()
    strengths: tuple[str, ...] = ()
    mapping_detail: str | None = None

    @property
    def canonical(self) -> str:
        return str(canonicalize_name(self.name))


@dataclass
class CandidateSet:
    candidates: list[Candidate] = field(default_factory=list)

    def names(self) -> list[str]:
        return [candidate.name for candidate in self.candidates]


class MappingStore:
    def __init__(self, mapping_path: str | Path):
        self.mapping_path = Path(mapping_path)
        self.data = json.loads(self.mapping_path.read_text(encoding="utf-8")) if self.mapping_path.exists() else {}

    def lookup(self, import_name: str) -> dict | None:
        return self.data.get(import_name)


class InstalledMetadataResolver:
    def __init__(self):
        try:
            self.mapping = packages_distributions()
        except Exception:
            self.mapping = {}

    def lookup(self, import_name: str) -> list[str]:
        return list(self.mapping.get(import_name, []))


def _merge_candidate(store: dict[str, dict], name: str, source: str, reference: str | None, strength: str, detail: str | None = None):
    canonical = str(canonicalize_name(name))
    if not canonical:
        return
    item = store.setdefault(
        canonical,
        {
            "name": name,
            "sources": [],
            "references": [],
            "strengths": [],
            "mapping_detail": None,
        },
    )
    if source not in item["sources"]:
        item["sources"].append(source)
    if reference and reference not in item["references"]:
        item["references"].append(reference)
    if strength not in item["strengths"]:
        item["strengths"].append(strength)
    if detail:
        item["mapping_detail"] = detail


def generate_candidates(
    import_name: str,
    *,
    mapping_store: MappingStore | None = None,
    installed_resolver: InstalledMetadataResolver | None = None,
    include_mapping: bool = True,
    include_installed: bool = True,
) -> CandidateSet:
    merged: dict[str, dict] = {}
    exact = str(canonicalize_name(import_name))
    if exact:
        _merge_candidate(merged, exact, "exact_normalized_name", None, "medium")

    if include_mapping and mapping_store:
        mapping = mapping_store.lookup(import_name)
        if mapping:
            detail = mapping.get("comment")
            for candidate in mapping.get("candidates", []):
                _merge_candidate(
                    merged,
                    candidate,
                    "curated_mapping",
                    mapping.get("reference"),
                    mapping.get("confidence", "high"),
                    detail,
                )

    if include_installed and installed_resolver:
        for candidate in installed_resolver.lookup(import_name):
            _merge_candidate(merged, candidate, "installed_metadata", None, "high")

    candidates = [
        Candidate(
            name=item["name"],
            sources=tuple(item["sources"]),
            references=tuple(item["references"]),
            strengths=tuple(item["strengths"]),
            mapping_detail=item["mapping_detail"],
        )
        for item in merged.values()
    ]
    return CandidateSet(candidates)
