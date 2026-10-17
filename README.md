# Source-Aware Dependency Verifier

A lightweight Python command-line prototype for the undergraduate thesis:

**Design and Evaluation of a Source-Aware Dependency Verification Framework for Reducing False Alerts in LLM-Generated Python Code**

## Mandatory scope

- Python only
- PyPI only
- ordinary `import` and `from ... import ...`
- Python AST parsing
- standard-library filtering
- relative-import filtering
- local module/package detection for project context
- curated import-to-distribution mappings
- installed package metadata as supporting evidence
- PyPI verification with caching and network-error distinction
- ambiguity and uncertainty reporting
- CLI + JSON/CSV/text reports
- baseline B0/B1/B2 + proposed method
- reproducible evaluation metrics

The project intentionally excludes package installation/execution, malicious-behaviour analysis, multi-language support, complete transitive dependency resolution, automatic remediation, OSV, GitHub Actions, and other optional extensions from the roadmap.

## Setup

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate
python -m pip install -e .
python -m pip install -e ".[dev]"
```

## Run one snippet

```bash
python -m src.cli --code "import os\nfrom PIL import Image\n" --method PROPOSED
```

Outputs are written to `results/report.json`, `results/report.csv`, and `results/report.txt` by default.

## Run a project

```bash
python -m src.cli --project tests/fixtures/local_project --method PROPOSED --sample-id DEMO_PROJECT
```

## Run tests

```bash
pytest -q
```

## Run evaluation

Populate `data/generated_outputs.jsonl` and `data/ground_truth.csv` using `docs/DATA_PROTOCOL.md`. Keep only the two runtime-required sample fields (`sample_id`, `extracted_code`) plus available thesis provenance; record one ground-truth row per import occurrence with its exact `occurrence_id`. Then run:

```bash
python -m src.evaluation_cli
```

The evaluation command runs B0, B1, B2, and PROPOSED and writes:

- `results/evaluation.json` — metrics, per-method predictions, category summary, case-level comparisons, warnings, and match counts.
- `results/evaluation_metrics_by_method.csv` — alert metrics and total/average warm-cache runtime by method.
- `results/evaluation_errors_by_category.csv` — incorrect classifications and false alerts grouped by ground-truth error category, including stage-to-stage improvement/regression counts.
- `results/evaluation_case_transitions.csv` — one row per occurrence, with all four predictions, correctness flags, false-alert flags, and B0→B1→B2→PROPOSED transitions.

Runtime is measured after all methods' PyPI queries have been warmed into the shared disk cache; it is a warm-cache analysis-time measurement, not cold first-run latency. The category and transition tables assess **full classification correctness** as well as the alert-only metrics. `RESOLVED_EXTERNAL` and `EXACT_PYPI_MATCH` are treated as equivalent successful resolution labels only when the predicted distribution agrees with the ground-truth distribution, when one is recorded. A missing `error_category` is reported as `UNCATEGORIZED`; the evaluation does not invent a category.

## Evidence order

1. Parse source
2. Relative import filter
3. Standard-library filter
4. Local-context filter (proposed method)
5. PEP-compliant normalized candidate
6. Curated mapping
7. Installed metadata (proposed method)
8. PyPI verification
9. Ambiguity/uncertainty classification
10. Evidence report

This order mirrors the thesis roadmap and is intentionally transparent rather than model-based.
