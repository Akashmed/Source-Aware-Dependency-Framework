from __future__ import annotations

import argparse
from pathlib import Path

from .analysis_runner import analyse_code, analyse_file, analyse_project
from .report_generator import write_csv, write_json, write_text_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Source-aware dependency verification for LLM-generated Python code."
    )
    source = parser.add_mutually_exclusive_group(required=False)
    source.add_argument("--file", help="Path to a Python source file")
    source.add_argument("--code", help="Python code snippet")
    source.add_argument("--project", help="Project directory containing Python files")
    parser.add_argument("--sample-id", default="CLI_SAMPLE")
    parser.add_argument("--method", choices=["B0", "B1", "B2", "PROPOSED"], default="PROPOSED")
    parser.add_argument("--mapping", default="data/import_distribution_mappings.json")
    parser.add_argument("--cache-dir", default="data/pypi_cache")
    parser.add_argument("--json", dest="json_path", default="results/report.json")
    parser.add_argument("--csv", dest="csv_path", default="results/report.csv")
    parser.add_argument("--text", dest="text_path", default="results/report.txt")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.project:
        analyses = analyse_project(
            args.project,
            sample_id=args.sample_id,
            method=args.method,
            mapping_path=args.mapping,
            cache_dir=args.cache_dir,
        )
        results = [item for analysis in analyses for item in analysis.results]
        if analyses:
            combined = analyses[0]
            combined.results = results
            combined.project_context_path = str(Path(args.project).resolve())
            write_json(combined, args.json_path)
            write_text_report(combined, args.text_path)
            write_csv(results, args.csv_path)
        return 0

    if args.file:
        analysis = analyse_file(
            args.file,
            sample_id=args.sample_id,
            method=args.method,
            mapping_path=args.mapping,
            cache_dir=args.cache_dir,
        )
    else:
        code = args.code if args.code is not None else ""
        analysis = analyse_code(
            code,
            sample_id=args.sample_id,
            method=args.method,
            mapping_path=args.mapping,
            cache_dir=args.cache_dir,
        )

    write_json(analysis, args.json_path)
    write_text_report(analysis, args.text_path)
    write_csv(analysis.results, args.csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
