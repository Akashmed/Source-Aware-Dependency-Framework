import csv
import json

from src.extract_dataset import extract_dataset


def test_extract_dataset_writes_all_imports_without_network_calls(tmp_path):
    dataset = tmp_path / "generated_outputs.jsonl"
    output = tmp_path / "extracted_imports.csv"
    records = [
        {
            "sample_id": "S001",
            "extracted_code": "import os\nfrom dateutil.parser import parse\n",
            "prompt_id": "P001",
            "model_name": "Demo",
        }
    ]
    dataset.write_text("\n".join(json.dumps(item) for item in records), encoding="utf-8")

    summary = extract_dataset(dataset, output)

    with output.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert summary["samples"] == 1
    assert summary["output_rows"] == 2
    assert [row["import_name"] for row in rows] == ["os", "dateutil"]
    assert rows[1]["imported_module"] == "dateutil.parser"
    assert rows[0]["occurrence_id"] == "S001:1"
    assert rows[1]["occurrence_id"] == "S001:2"
    assert rows[1]["parse_status"] == "OK"


def test_extract_dataset_records_parse_errors(tmp_path):
    dataset = tmp_path / "generated_outputs.jsonl"
    output = tmp_path / "extracted_imports.csv"
    dataset.write_text(
        json.dumps({"sample_id": "S_BAD", "extracted_code": "if True print('broken')"}),
        encoding="utf-8",
    )

    summary = extract_dataset(dataset, output)

    with output.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert summary["parse_errors"] == 1
    assert rows[0]["occurrence_id"] == "S_BAD:PARSE_ERROR"
    assert rows[0]["parse_status"] == "PARSE_ERROR"
