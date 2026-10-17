from dataclasses import dataclass

from src.analysis_runner import analyse_code


@dataclass
class FakeResponse:
    status: int
    exists: bool
    timestamp: str = "2026-01-01T00:00:00+00:00"
    from_cache: bool = False


class FakePyPI:
    def get_project(self, project):
        return FakeResponse(200, project.lower() == "pillow") if project.lower() == "pillow" else FakeResponse(404, False)


def test_end_to_end_without_network(tmp_path):
    mapping = tmp_path / "mapping.json"
    mapping.write_text(
        '{"PIL":{"candidates":["Pillow"],"confidence":"high","reference":"https://pypi.org/project/Pillow/"}}',
        encoding="utf-8",
    )
    analysis = analyse_code(
        "from PIL import Image\nimport os\n",
        sample_id="S1",
        method="B2",
        mapping_path=mapping,
        pypi_client=FakePyPI(),
    )
    assert analysis.parse_status == "OK"
    assert [r.label for r in analysis.results] == ["RESOLVED_EXTERNAL", "STANDARD_LIBRARY"]
