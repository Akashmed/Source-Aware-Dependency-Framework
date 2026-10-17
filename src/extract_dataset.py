"""Extract import occurrences from generated_outputs.jsonl without querying PyPI.

This utility is for dataset preparation and ground-truth investigation. It only
parses the supplied code with Python's AST; it does not run B0/B1/B2/PROPOSED,
inspect installed distribution metadata, or make network requests.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from .import_extractor import ImportExtractionError, extract_imports

OUTPUT_FIELDS = [
    "sample_id",
    "occurrence_id",
    "file_path",
    "project_context_path",
    "line",
    "column",
    "import_name",
    "imported_module",
    "imported_names",
    "alias",
    "import_kind",
    "relative_level",
    "parse_status",
    "prompt_id",
    "prompt_category",
    "model_name",
    "generation_date",
]


def _parse_error_line(message: str) -> int:
    match = re.search(r"line (\d+)", message)
    return int(match.group(1)) if match else 0


def extract_dataset(dataset_path: str | Path, output_path: str | Path) -> dict[str, int]:
    """Write one CSV row per import occurrence, with no registry/API calls."""
    dataset_path = Path(dataset_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    sample_count = 0
    parse_error_count = 0
    no_import_count = 0

    with dataset_path.open("r", encoding="utf-8") as handle:
        for jsonl_line, raw_line in enumerate(handle, start=1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                sample = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSONL at {dataset_path}:{jsonl_line}: {exc}"
                ) from exc
            if not isinstance(sample, dict):
                raise ValueError(
                    f"JSONL record at {dataset_path}:{jsonl_line} must be a JSON object."
                )

            sample_id = str(sample.get("sample_id") or "").strip()
            if not sample_id:
                raise ValueError(
                    f"JSONL record at {dataset_path}:{jsonl_line} has no sample_id."
                )

            sample_count += 1
            code = str(sample.get("extracted_code") or "")
            file_path = str(sample.get("file_path") or "<snippet>")
            common = {
                "sample_id": sample_id,
                "file_path": file_path,
                "project_context_path": str(sample.get("project_context_path") or ""),
                "prompt_id": str(sample.get("prompt_id") or ""),
                "prompt_category": str(sample.get("prompt_category") or ""),
                "model_name": str(sample.get("model_name") or ""),
                "generation_date": str(sample.get("generation_date") or ""),
            }

            try:
                occurrences = extract_imports(
                    code,
                    sample_id=sample_id,
                    file_path=file_path,
                )
            except ImportExtractionError as exc:
                parse_error_count += 1
                rows.append(
                    {
                        **common,
                        "occurrence_id": f"{sample_id}:PARSE_ERROR",
                        "line": _parse_error_line(str(exc)),
                        "column": 0,
                        "import_name": "",
                        "imported_module": "",
                        "imported_names": "[]",
                        "alias": "",
                        "import_kind": "parse_error",
                        "relative_level": 0,
                        "parse_status": "PARSE_ERROR",
                    }
                )
                continue

            if not occurrences:
                no_import_count += 1
            for occurrence in occurrences:
                rows.append(
                    {
                        **common,
                        "occurrence_id": occurrence.occurrence_id,
                        "line": occurrence.line,
                        "column": occurrence.column,
                        "import_name": occurrence.import_name,
                        "imported_module": occurrence.imported_module,
                        "imported_names": json.dumps(list(occurrence.imported_names), ensure_ascii=False),
                        "alias": occurrence.alias or "",
                        "import_kind": occurrence.import_kind,
                        "relative_level": occurrence.relative_level,
                        "parse_status": "OK",
                    }
                )

    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    return {
        "samples": sample_count,
        "import_occurrences_and_parse_errors": len(rows),
        "parse_errors": parse_error_count,
        "samples_without_imports": no_import_count,
        "output_rows": len(rows),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract imports from generated_outputs.jsonl into one CSV for manual review. "
            "No classifier or PyPI requests are run."
        )
    )
    parser.add_argument("--dataset", default="data/generated_outputs.jsonl")
    parser.add_argument("--output", default="results/extracted_imports.csv")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = extract_dataset(args.dataset, args.output)
    print(f"Dataset samples: {summary['samples']}")
    print(f"Import occurrences / parse-error rows: {summary['output_rows']}")
    print(f"Parse errors: {summary['parse_errors']}")
    print(f"Samples without imports: {summary['samples_without_imports']}")
    print(f"Saved extraction CSV: {Path(args.output)}")
    print("No PyPI queries or dependency classifications were performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())