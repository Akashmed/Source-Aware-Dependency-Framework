from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .candidate_resolver import Candidate, CandidateSet
from .local_resolver import resolve_local_module
from .models import Evidence, ImportOccurrence, ResolutionResult
from .pypi_client import PyPIClient, PyPIResponse
from .stdlib_checker import is_standard_library


METHODS = ("B0", "B1", "B2", "PROPOSED")


@dataclass
class VerificationContext:
    mapping_store: object | None = None
    installed_resolver: object | None = None
    pypi_client: PyPIClient | None = None
    project_root: str | Path | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_result(occurrence: ImportOccurrence, label: str, *, confidence: str = "None") -> ResolutionResult:
    return ResolutionResult(occurrence=occurrence, label=label, confidence=confidence)


def _candidate_strength(candidate: Candidate) -> int:
    strengths = set(candidate.strengths)
    if "high" in strengths:
        return 3
    if "medium" in strengths:
        return 2
    return 1


def _choose_verified_candidate(
    verified: list[tuple[Candidate, PyPIResponse]],
    *,
    handle_ambiguity: bool,
) -> tuple[str, Candidate | None]:
    """Choose a verified candidate deterministically.

    Only PROPOSED explicitly reports AMBIGUOUS. Earlier methods do not have
    ambiguity handling as a feature, so they choose the first candidate among
    equally strong verified candidates. Candidate order is stable because
    candidate generation preserves insertion order.
    """
    if not verified:
        return "none", None

    max_strength = max(_candidate_strength(candidate) for candidate, _ in verified)
    top = [(candidate, response) for candidate, response in verified if _candidate_strength(candidate) == max_strength]
    unique = {candidate.canonical for candidate, _ in top}
    if len(unique) > 1 and handle_ambiguity:
        return "ambiguous", None
    return "resolved", top[0][0]


def verify_occurrence(occurrence: ImportOccurrence, method: str, context: VerificationContext) -> ResolutionResult:
    method = method.upper()
    if method not in METHODS:
        raise ValueError(f"Unknown method: {method}")

    if occurrence.relative_level > 0:
        if method in {"B0"}:
            # B0 intentionally ignores source-aware import context.
            pass
        elif method in {"B1", "B2", "PROPOSED"}:
            result = _base_result(occurrence, "RELATIVE_IMPORT", confidence="High")
            result.evidence.append(Evidence("relative_import", "ImportFrom has a relative level greater than zero.", "high"))
            return result

    top_level = occurrence.top_level_name
    if method in {"B1", "B2", "PROPOSED"} and is_standard_library(top_level):
        result = _base_result(occurrence, "STANDARD_LIBRARY", confidence="High")
        result.evidence.append(Evidence("standard_library", f"{top_level} is listed in sys.stdlib_module_names.", "high"))
        return result

    if method == "PROPOSED":
        local = resolve_local_module(context.project_root, top_level)
        if local.matched:
            result = _base_result(occurrence, "LOCAL_MODULE", confidence="High")
            result.evidence.append(
                Evidence("local_context", f"Matched local {local.kind}: {local.path}", "high")
            )
            return result

    mapping_allowed = method in {"B2", "PROPOSED"}
    installed_allowed = method == "PROPOSED"
    candidates = _generate_candidates(occurrence, context, mapping_allowed, installed_allowed)
    return _verify_candidates(occurrence, candidates, context.pypi_client, method)


def _generate_candidates(occurrence, context, mapping_allowed, installed_allowed):
    from .candidate_resolver import generate_candidates

    return generate_candidates(
        occurrence.import_name,
        mapping_store=context.mapping_store if mapping_allowed else None,
        installed_resolver=context.installed_resolver if installed_allowed else None,
        include_mapping=mapping_allowed,
        include_installed=installed_allowed,
    )


def _verify_candidates(
    occurrence: ImportOccurrence,
    candidates: CandidateSet,
    pypi_client: PyPIClient | None,
    method: str,
) -> ResolutionResult:
    if not pypi_client:
        raise ValueError("PyPI client is required for registry verification")

    result = _base_result(occurrence, "NOT_FOUND", confidence="None")
    result.candidates = candidates.names()

    if not candidates.candidates:
        result.error = "No distribution candidate could be generated."
        return result

    verified: list[tuple[Candidate, PyPIResponse]] = []
    network_failures = 0
    responses: list[PyPIResponse] = []

    for candidate in candidates.candidates:
        response = pypi_client.get_project(candidate.name)
        responses.append(response)
        result.evidence.extend(
            [
                Evidence(
                    "candidate_generation",
                    f"Candidate {candidate.name} from {', '.join(candidate.sources)}.",
                    "high" if "curated_mapping" in candidate.sources or "installed_metadata" in candidate.sources else "medium",
                    reference=(candidate.references[0] if candidate.references else None),
                    metadata={"candidate": candidate.name, "sources": list(candidate.sources), "mapping_detail": candidate.mapping_detail},
                ),
                Evidence(
                    "pypi",
                    f"PyPI lookup for {candidate.name}: HTTP {response.status if response.status is not None else 'network error'}.",
                    "high" if response.status == 200 else "medium",
                    timestamp=response.timestamp,
                    metadata={"from_cache": response.from_cache},
                ),
            ]
        )
        if response.exists is True:
            verified.append((candidate, response))
        elif response.exists is None:
            network_failures += 1

    if verified:
        decision, chosen = _choose_verified_candidate(verified, handle_ambiguity=(method == "PROPOSED"))
        if decision == "ambiguous":
            result.label = "AMBIGUOUS"
            result.confidence = "Low"
            result.error = "Multiple plausible candidates were verified on PyPI."
            result.query_timestamp = max((response.timestamp for _, response in verified), default=None)
            return result

        assert chosen is not None
        chosen_response = next(response for candidate, response in verified if candidate.canonical == chosen.canonical)
        result.distribution = chosen.name
        result.normalized_candidate = chosen.canonical
        result.query_timestamp = chosen_response.timestamp
        result.registry_status = chosen_response.status
        result.confidence = "High" if "high" in chosen.strengths else "Medium"
        exact = chosen.canonical == str(occurrence.import_name).replace("_", "-").replace(".", "-").lower()
        result.label = "EXACT_PYPI_MATCH" if exact else "RESOLVED_EXTERNAL"
        return result

    if network_failures and network_failures == len(responses):
        result.label = "NETWORK_ERROR"
        result.confidence = "None"
        result.error = "All PyPI candidate lookups failed because of a registry/network error."
        result.query_timestamp = max((response.timestamp for response in responses), default=None)
        return result

    # Private/unknown is supported through an explicit mapping hint. This keeps
    # the decision evidence-based instead of guessing from package-name patterns.
    if any(c.mapping_detail and "private" in c.mapping_detail.lower() for c in candidates.candidates):
        result.label = "PRIVATE_OR_UNKNOWN"
        result.confidence = "Low"
        result.error = "Candidate context indicates a possible private dependency."
        return result

    result.label = "NOT_FOUND"
    result.confidence = "None"
    result.query_timestamp = max((response.timestamp for response in responses), default=None)
    return result
