# Evaluation and Ambiguity Update

## Changes

- Added `error_category` to the ground-truth CSV template.
- Evaluation now reports overall metrics, category-wise classification correctness and false-alert counts, and case-level transitions between B0 -> B1 -> B2 -> PROPOSED.
- CSV reports are written alongside the JSON output: `<stem>_metrics_by_method.csv`, `<stem>_errors_by_category.csv`, and `<stem>_case_transitions.csv`.
- Case-level comparisons treat `RESOLVED_EXTERNAL` and `EXACT_PYPI_MATCH` as compatible successful resolution labels only when the distribution matches if ground truth records one.
- Added missing-ground-truth/category diagnostics and checks for blank or invalid ground-truth labels.
- Added total and average warm-cache runtime. The evaluator first warms the shared PyPI cache through all methods so B0 does not pay network latency while later methods benefit from previously cached queries. These are warm-cache timings, not cold first-run latency.
- Ambiguity policy now distinguishes baselines: only PROPOSED explicitly returns `AMBIGUOUS`; B2 chooses the first verified candidate among equally strong candidates, deterministically, as a limitation of the basic mapping baseline.

## Run

From the repository root:

```bash
python -m src.evaluation_cli
```

To specify files:

```bash
python -m src.evaluation_cli \
  --dataset data/generated_outputs.jsonl \
  --ground-truth data/ground_truth.csv \
  --mapping data/import_distribution_mappings.json \
  --cache-dir data/pypi_cache \
  --output results/evaluation.json
```

## Important ground-truth rule

Fill `error_category` from a written taxonomy based on the import occurrence and its independently verified context—not based on which method predicted incorrectly. Freeze labels/categories before the final comparison. If `error_category` is missing, the evaluation records `UNCATEGORIZED` and emits a warning.

## Tests

The included suite covers classifier ambiguity policy and evaluation category/case-transition output.

```bash
pytest -q
```
