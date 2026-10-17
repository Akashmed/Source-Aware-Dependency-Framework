# Minimal Data and Ground-Truth Protocol

The goal is to keep manual data entry small while preserving the provenance and evidence needed for the thesis. Fields the framework derives automatically should not be manually maintained in the input JSONL or ground-truth CSV.

## 1. `data/generated_outputs.jsonl`

One JSON object per line, representing one sample/code output.

### Required for the current evaluation code

- `sample_id`: unique ID for this code sample.
- `extracted_code`: Python code to analyse.

### Optional fields used by the framework

- `file_path`: source path for analysis; defaults to `<snippet>` when omitted.
- `project_context_path`: root directory of the sample's multi-file project; omit or use `null` for isolated snippets.

### Keep for thesis provenance when available

- `prompt_id`
- `prompt_category`
- `prompt_text`
- `model_name`
- `model_version_or_interface`
- `generation_date`
- `generation_settings` (write `not exposed by interface` when unknown)
- `raw_response` (preserve the full model response)
- `python_version` (record the target version used for the sample; can be the same across all samples)

These provenance fields are not needed to execute the evaluator, but help document how the LLM dataset was collected. For public datasets, some model/prompt metadata may be unavailable; do not invent it. Instead add available provenance such as `source_dataset`, `source_record_id`, `source_url`, and `license`.

### Fields not to fill manually in JSONL

Do not add or manually maintain `parse_status`, `detected_imports`, `baseline_prediction`, `proposed_prediction`, `ground_truth_label`, or `ground_truth_distribution` in `generated_outputs.jsonl`. The extractor and evaluation derive predictions; ground truth belongs in the separate CSV.

### Example for LLM-generated data

This is illustrative only; replace all example details with the actual prompt, actual output, model/interface, and settings from your experiment:

```jsonl
{"sample_id":"S001","extracted_code":"import os\\nfrom PIL import Image\\n","file_path":"<snippet>","project_context_path":null,"prompt_id":"P001","prompt_category":"file_document_processing","prompt_text":"Write Python code that imports an image and prints its size.","model_name":"ACTUAL_MODEL_NAME","model_version_or_interface":"ACTUAL_INTERFACE_OR_VERSION","generation_date":"2026-10-14","generation_settings":"not exposed by interface","raw_response":"ACTUAL_FULL_MODEL_RESPONSE","python_version":"3.11"}
```

## 2. `data/ground_truth.csv`

One row per extracted import occurrence, not one row per code sample.

### Minimal columns

- `occurrence_id`: copy exactly from the extractor/analysis report. The current extractor makes IDs in the form `sample_id:number`, for example `S001:1`.
- `ground_truth_label`: manually verified correct output class; required by the evaluator.
- `ground_truth_distribution`: fill when the correct answer is a resolved external distribution, such as `Pillow`; otherwise leave blank when not applicable.
- `error_category`: manually assign the pre-defined category used for category-wise evaluation.
- `evidence_type`: e.g. official project documentation, PyPI metadata, Python documentation, or project-context inspection.
- `evidence_reference`: official project documentation, PyPI project URL, or other suitable source supporting the label/mapping.
- `certainty`: `High`, `Medium`, or `Low`, based on the strength of the evidence.
- `review_status`: e.g. `Verified`, `Needs_review`, or `Ambiguous`.
- `evidence_notes`: briefly explain why the source/context supports the label and record the evidence access date if it is not captured elsewhere.
- `reviewer`: reviewer identifier/initials, where applicable.
- `review_date`: date the ground-truth label was reviewed.

The evaluator technically requires `occurrence_id` (or enough fallback location fields to reconstruct a matching key) and `ground_truth_label`. `error_category` is needed for category tables; `ground_truth_distribution` is important for checking whether an external distribution was resolved correctly. The remaining evidence/review fields preserve the roadmap’s manual verification protocol. To avoid duplicate entry, do not manually copy `sample_id`, `line`, `column`, `import_name`, or `imported_module` into this CSV: they are available in the analysis report and `occurrence_id` joins the labels to predictions.

### Example

```csv
occurrence_id,ground_truth_label,ground_truth_distribution,error_category,evidence_type,evidence_reference,certainty,review_status,evidence_notes,reviewer,review_date
S001:1,STANDARD_LIBRARY,,STDLIB_AS_DEPENDENCY,Python documentation,https://docs.python.org/3.11/library/os.html,High,Verified,"os is part of the Python standard library; checked 2026-10-14",R1,2026-10-14
S001:2,RESOLVED_EXTERNAL,Pillow,IMPORT_DISTRIBUTION_MISMATCH,Packaging documentation,https://packaging.python.org/en/latest/discussions/distribution-package-vs-import-package/,High,Verified,"Pillow provides PIL; project context reviewed; checked 2026-10-14",R1,2026-10-14
```

These rows are examples of the format, not pre-verified labels for your actual dataset. Ground truth must be established from each sample's actual code and context.

## 3. Workflow

1. Save each LLM output or public-code sample in `generated_outputs.jsonl` with a unique `sample_id` and its `extracted_code`.
2. Run the analyzer or evaluation extractor and inspect the import occurrences and IDs.
3. Investigate each occurrence and enter one ground-truth row per occurrence.
4. Maintain curated mappings separately in `import_distribution_mappings.json`; do not automatically assume mapping presence proves ground truth.
5. Finish labels and categories, independently re-check at least 20% when a second reviewer is available, and freeze the dataset before final evaluation.
6. Run `python -m src.evaluation_cli` to execute B0, B1, B2, and PROPOSED and generate metrics, category summaries, and case-transition tables.

## 4. Error taxonomy

Use one primary `error_category` per occurrence, according to its verified context and independently of method results. Suggested values:

- `STDLIB_AS_DEPENDENCY`
- `LOCAL_AS_DEPENDENCY`
- `RELATIVE_AS_DEPENDENCY`
- `IMPORT_DISTRIBUTION_MISMATCH`
- `AMBIGUOUS_PROVIDER`
- `PRIVATE_OR_UNKNOWN`
- `GENUINELY_NOT_FOUND`
- `SYNTAX_FAILURE`
- `REGISTRY_ERROR`
- `NO_KNOWN_ERROR`

Finalize category definitions before the final evaluation. Do not change labels just to improve a method's results.
