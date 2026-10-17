import csv
import json
from types import SimpleNamespace

from src.evaluation import prediction_matches_ground_truth, run_evaluation, write_evaluation
from src.import_extractor import extract_imports
from src.models import ResolutionResult


def test_evaluation_builds_category_and_transition_tables(tmp_path, monkeypatch):
    dataset = tmp_path / "generated_outputs.jsonl"
    dataset.write_text(
        json.dumps({
            "sample_id": "S1",
            "extracted_code": "import os\nimport PIL\n",
            "file_path": "<snippet>",
            "project_context_path": None,
        }) + "\n",
        encoding="utf-8",
    )

    truth_path = tmp_path / "ground_truth.csv"
    truth_rows = [
        {
            "occurrence_id": "S1:1",
            "sample_id": "S1",
            "file_path": "<snippet>",
            "line": "1",
            "column": "0",
            "import_name": "os",
            "imported_module": "os",
            "ground_truth_label": "STANDARD_LIBRARY",
            "ground_truth_distribution": "",
            "error_category": "STDLIB_AS_DEPENDENCY",
        },
        {
            "occurrence_id": "S1:2",
            "sample_id": "S1",
            "file_path": "<snippet>",
            "line": "2",
            "column": "0",
            "import_name": "PIL",
            "imported_module": "PIL",
            "ground_truth_label": "RESOLVED_EXTERNAL",
            "ground_truth_distribution": "Pillow",
            "error_category": "IMPORT_DISTRIBUTION_MISMATCH",
        },
    ]
    with truth_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(truth_rows[0]))
        writer.writeheader()
        writer.writerows(truth_rows)

    labels = {
        "B0": {"os": ("NOT_FOUND", None), "PIL": ("NOT_FOUND", None)},
        "B1": {"os": ("STANDARD_LIBRARY", None), "PIL": ("NOT_FOUND", None)},
        "B2": {"os": ("STANDARD_LIBRARY", None), "PIL": ("RESOLVED_EXTERNAL", "Pillow")},
        "PROPOSED": {"os": ("STANDARD_LIBRARY", None), "PIL": ("RESOLVED_EXTERNAL", "Pillow")},
    }

    def fake_analyse_code(code, *, sample_id, method, file_path, **kwargs):
        occurrences = extract_imports(code, sample_id=sample_id, file_path=file_path)
        results = []
        for occurrence in occurrences:
            label, distribution = labels[method][occurrence.import_name]
            results.append(
                ResolutionResult(
                    occurrence=occurrence,
                    label=label,
                    distribution=distribution,
                    candidates=[distribution] if distribution else [],
                )
            )
        return SimpleNamespace(results=results)

    monkeypatch.setattr("src.evaluation.analyse_code", fake_analyse_code)

    result = run_evaluation(dataset, truth_path, mapping_path=tmp_path / "mapping.json", cache_dir=tmp_path / "cache")

    by_category = {row["error_category"]: row for row in result["errors_by_category"]}
    stdlib = by_category["STDLIB_AS_DEPENDENCY"]
    mismatch = by_category["IMPORT_DISTRIBUTION_MISMATCH"]
    assert stdlib["B0_false_alerts"] == 1
    assert stdlib["B1_correct"] == 1
    assert stdlib["B0_to_B1_incorrect_to_correct"] == 1
    assert mismatch["B1_incorrect"] == 1
    assert mismatch["B2_correct"] == 1
    assert mismatch["B1_to_B2_incorrect_to_correct"] == 1

    transitions = {row["occurrence_id"]: row for row in result["case_transitions"]}
    assert transitions["S1:1"]["B0_to_B1_transition"] == "INCORRECT_TO_CORRECT"
    assert transitions["S1:2"]["B1_to_B2_transition"] == "INCORRECT_TO_CORRECT"
    assert result["evaluation_summary"]["runtime_mode"] == "warm_cache"
    assert "runtime_seconds" in result["metrics"]["B0"]
    assert "average_runtime_seconds" in result["metrics"]["B0"]

    output = write_evaluation(result, tmp_path / "evaluation.json")
    assert (tmp_path / "evaluation_metrics_by_method.csv").exists()
    assert (tmp_path / "evaluation_errors_by_category.csv").exists()
    assert (tmp_path / "evaluation_case_transitions.csv").exists()
    assert output["json"].endswith("evaluation.json")


def test_external_resolution_requires_correct_distribution_when_labelled():
    base = {
        "prediction": "RESOLVED_EXTERNAL",
        "ground_truth_label": "RESOLVED_EXTERNAL",
        "ground_truth_distribution": "Pillow",
        "predicted_distribution": "Pillow",
    }
    assert prediction_matches_ground_truth(base)
    assert not prediction_matches_ground_truth(base | {"predicted_distribution": "OtherPackage"})
    assert not prediction_matches_ground_truth(base | {"predicted_distribution": ""})
