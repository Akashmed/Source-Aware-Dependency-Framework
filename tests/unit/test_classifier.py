from dataclasses import dataclass

from src.candidate_resolver import MappingStore
from src.classifier import VerificationContext, verify_occurrence
from src.import_extractor import extract_imports


@dataclass
class FakeResponse:
    status: int
    exists: bool
    timestamp: str = "2026-01-01T00:00:00+00:00"
    from_cache: bool = False


class FakePyPI:
    def __init__(self, existing):
        self.existing = existing

    def get_project(self, project):
        exists = project.lower() in {name.lower() for name in self.existing}
        return FakeResponse(200 if exists else 404, exists)


def occ(code, sample="S1"):
    return extract_imports(code, sample_id=sample)[0]


def context(tmp_path, mapping):
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(mapping, encoding="utf-8")
    return VerificationContext(
        mapping_store=MappingStore(mapping_path),
        installed_resolver=None,
        pypi_client=FakePyPI({"Pillow", "requests"}),
        project_root=None,
    )


def test_b0_mismatch_becomes_not_found(tmp_path):
    item = occ("import PIL")
    result = verify_occurrence(item, "B0", context(tmp_path, "{}"))
    assert result.label == "NOT_FOUND"


def test_b2_mapping_resolves(tmp_path):
    item = occ("import PIL")
    result = verify_occurrence(
        item,
        "B2",
        context(tmp_path, '{"PIL":{"candidates":["Pillow"],"confidence":"high"}}'),
    )
    assert result.label == "RESOLVED_EXTERNAL"
    assert result.distribution == "Pillow"


def test_b1_filters_standard_library(tmp_path):
    item = occ("import os")
    result = verify_occurrence(item, "B1", context(tmp_path, "{}"))
    assert result.label == "STANDARD_LIBRARY"


def test_proposed_filters_local_module(tmp_path):
    (tmp_path / "helpers.py").write_text("x = 1\n", encoding="utf-8")
    item = occ("import helpers")
    ctx = context(tmp_path, "{}")
    ctx.project_root = tmp_path
    result = verify_occurrence(item, "PROPOSED", ctx)
    assert result.label == "LOCAL_MODULE"

def test_b0_exact_match(tmp_path):
    item = occ("import requests")
    result = verify_occurrence(item, "B0", context(tmp_path, "{}"))
    assert result.label == "EXACT_PYPI_MATCH"


def test_parse_error_is_reported(tmp_path):
    from src.analysis_runner import analyse_code
    analysis = analyse_code("if True print('broken')", sample_id="BAD", method="PROPOSED")
    assert analysis.parse_status == "PARSE_ERROR"
    assert analysis.results[0].label == "PARSE_ERROR"


def test_only_proposed_reports_ambiguous_verified_candidates(tmp_path):
    item = occ("import ambiguouslib")
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(
        '{"ambiguouslib":{"candidates":["ProviderOne","ProviderTwo"],"confidence":"high"}}',
        encoding="utf-8",
    )
    ctx = VerificationContext(
        mapping_store=MappingStore(mapping_path),
        installed_resolver=None,
        pypi_client=FakePyPI({"ProviderOne", "ProviderTwo"}),
        project_root=None,
    )

    b2_result = verify_occurrence(item, "B2", ctx)
    proposed_result = verify_occurrence(item, "PROPOSED", ctx)

    # B2 has mapping but no explicit ambiguity handling: it picks the first
    # candidate among equally strong verified candidates deterministically.
    assert b2_result.label == "RESOLVED_EXTERNAL"
    assert b2_result.distribution == "ProviderOne"
    # PROPOSED explicitly exposes the competing candidates to the user.
    assert proposed_result.label == "AMBIGUOUS"
