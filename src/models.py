from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


OUTPUT_CLASSES = {
    "STANDARD_LIBRARY",
    "LOCAL_MODULE",
    "RELATIVE_IMPORT",
    "RESOLVED_EXTERNAL",
    "EXACT_PYPI_MATCH",
    "AMBIGUOUS",
    "NOT_FOUND",
    "PRIVATE_OR_UNKNOWN",
    "PARSE_ERROR",
    "NETWORK_ERROR",
}


@dataclass(frozen=True)
class ImportOccurrence:
    occurrence_id: str
    sample_id: str
    file_path: str
    line: int
    column: int
    import_name: str
    imported_module: str
    imported_names: tuple[str, ...]
    alias: str | None
    import_kind: str
    relative_level: int = 0

    @property
    def top_level_name(self) -> str:
        return self.import_name.split(".", 1)[0] if self.import_name else ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"imported_names": list(self.imported_names)}


@dataclass
class Evidence:
    source: str
    detail: str
    strength: str = "medium"
    reference: str | None = None
    timestamp: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResolutionResult:
    occurrence: ImportOccurrence
    label: str
    distribution: str | None = None
    candidates: list[str] = field(default_factory=list)
    confidence: str = "None"
    normalized_candidate: str | None = None
    evidence: list[Evidence] = field(default_factory=list)
    registry_status: int | None = None
    query_timestamp: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["occurrence"] = self.occurrence.to_dict()
        result["evidence"] = [item.to_dict() for item in self.evidence]
        return result


@dataclass
class SampleAnalysis:
    sample_id: str
    method: str
    source_type: str
    python_version: str
    analysed_at: str
    parse_status: str
    results: list[ResolutionResult] = field(default_factory=list)
    source_path: str | None = None
    project_context_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "method": self.method,
            "source_type": self.source_type,
            "python_version": self.python_version,
            "analysed_at": self.analysed_at,
            "parse_status": self.parse_status,
            "source_path": self.source_path,
            "project_context_path": self.project_context_path,
            "results": [result.to_dict() for result in self.results],
        }
