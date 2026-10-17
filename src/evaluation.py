from __future__ import annotations

import csv
import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packaging.utils import canonicalize_name

from .analysis_runner import analyse_code
from .models import OUTPUT_CLASSES


# These are the outcomes interpreted as dependency alerts for the roadmap's
# TP/FP/TN/FN definitions. Keep this separate from full-classification scoring.
ALERT_CLASSES = {"NOT_FOUND"}
PROBLEM_TRUTH_CLASSES = {"NOT_FOUND"}

METHOD_ORDER = ("B0", "B1", "B2", "PROPOSED")
RESOLVED_EXTERNAL_CLASSES = {"RESOLVED_EXTERNAL", "EXACT_PYPI_MATCH"}
NON_DEFINITE_CLASSES = {"AMBIGUOUS", "PRIVATE_OR_UNKNOWN", "PARSE_ERROR", "NETWORK_ERROR"}


@dataclass
class MetricSummary:
    method: str
    tp: int
    fp: int
    tn: int
    fn: int
    precision: float
    recall: float
    f1: float
    false_positive_rate: float
    false_alert_reduction_vs_b0: float | None
    coverage: float
    ambiguity_rate: float
    total: int
    runtime_seconds: float
    average_runtime_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _is_alert(label: str) -> bool:
    return label in ALERT_CLASSES


def _is_problem_truth(label: str) -> bool:
    return label in PROBLEM_TRUTH_CLASSES


def _divide(a: int | float, b: int | float) -> float:
    return a / b if b else 0.0


def _normalized_distribution(name: str | None) -> str:
    return str(canonicalize_name(name or "")) if name else ""


def prediction_matches_ground_truth(row: dict[str, Any]) -> bool:
    """Return whether a method's classification agrees with the labelled truth.

    RESOLVED_EXTERNAL and EXACT_PYPI_MATCH are treated as compatible labels,
    but if ground truth records a distribution, the predicted distribution
    must match it. This is deliberately separate from the alert-only metrics.
    """
    predicted = str(row.get("prediction") or "")
    truth = str(row.get("ground_truth_label") or "")

    if predicted in RESOLVED_EXTERNAL_CLASSES and truth in RESOLVED_EXTERNAL_CLASSES:
        expected_distribution = _normalized_distribution(row.get("ground_truth_distribution"))
        predicted_distribution = _normalized_distribution(row.get("predicted_distribution"))
        if expected_distribution:
            # If the correct distribution is known, a prediction without a
            # distribution is not enough to count as a correct resolution.
            return bool(predicted_distribution) and expected_distribution == predicted_distribution
        # If ground truth has no distribution annotation, the compatible
        # external-resolution class is sufficient for this row.
        return True

    return bool(predicted) and predicted == truth


def calculate_metrics(
    method: str,
    predictions: list[dict],
    baseline_fp: int | None = None,
    *,
    runtime_seconds: float = 0.0,
    analysed_occurrences: int | None = None,
) -> MetricSummary:
    tp = fp = tn = fn = 0
    for row in predictions:
        predicted_alert = _is_alert(row["prediction"])
        truth_alert = _is_problem_truth(row["ground_truth_label"])
        if predicted_alert and truth_alert:
            tp += 1
        elif predicted_alert and not truth_alert:
            fp += 1
        elif not predicted_alert and truth_alert:
            fn += 1
        else:
            tn += 1

    precision = _divide(tp, tp + fp)
    recall = _divide(tp, tp + fn)
    f1 = _divide(2 * precision * recall, precision + recall)
    fpr = _divide(fp, fp + tn)
    reduction = None
    if method != "B0" and baseline_fp is not None:
        reduction = _divide(baseline_fp - fp, baseline_fp) * 100 if baseline_fp else 0.0

    definite = sum(1 for row in predictions if row["prediction"] not in NON_DEFINITE_CLASSES)
    ambiguity = sum(1 for row in predictions if row["prediction"] == "AMBIGUOUS")
    total = len(predictions)

    return MetricSummary(
        method=method,
        tp=tp,
        fp=fp,
        tn=tn,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        false_positive_rate=fpr,
        false_alert_reduction_vs_b0=reduction,
        coverage=_divide(definite, total),
        ambiguity_rate=_divide(ambiguity, total),
        total=total,
        runtime_seconds=round(runtime_seconds, 6),
        average_runtime_seconds=round(
            _divide(runtime_seconds, analysed_occurrences if analysed_occurrences is not None else total),
            6,
        ),
    )


def load_ground_truth(path: str | Path) -> dict[str, dict]:
    with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "ground_truth_label" not in reader.fieldnames:
            raise ValueError("ground_truth.csv must contain a 'ground_truth_label' column.")
        data: dict[str, dict] = {}
        for line_number, row in enumerate(reader, start=2):
            label = str(row.get("ground_truth_label") or "").strip()
            if not label:
                raise ValueError(f"ground_truth.csv line {line_number} has an empty ground_truth_label.")
            if label not in OUTPUT_CLASSES:
                raise ValueError(
                    f"ground_truth.csv line {line_number} has unsupported ground_truth_label {label!r}. "
                    f"Expected one of: {', '.join(sorted(OUTPUT_CLASSES))}."
                )
            key = (row.get("occurrence_id") or "").strip() or _occurrence_key(row)
            if key in data:
                raise ValueError(f"Duplicate ground-truth occurrence key: {key}")
            data[key] = row
        return data


def _occurrence_key(row: dict) -> str:
    return "|".join(
        [
            str(row.get("sample_id", "") or ""),
            str(row.get("file_path", "<snippet>") or "<snippet>"),
            str(row.get("line", "") or ""),
            str(row.get("column", "") or ""),
            str(row.get("import_name", "") or ""),
            str(row.get("imported_module", "") or ""),
        ]
    )


def _prediction_key(result) -> str:
    return result.occurrence.occurrence_id


def _ground_truth_for_result(result, truth: dict[str, dict]) -> tuple[dict | None, str | None]:
    key = _prediction_key(result)
    gt = truth.get(key)
    if gt is not None:
        return gt, key

    # Backward-compatible fallback for ground-truth files prepared without
    # occurrence IDs. The fields must match the extractor's actual output.
    occurrence = result.occurrence
    fallback = _occurrence_key(
        {
            "sample_id": occurrence.sample_id,
            "file_path": occurrence.file_path,
            "line": str(occurrence.line),
            "column": str(occurrence.column),
            "import_name": occurrence.import_name,
            "imported_module": occurrence.imported_module,
        }
    )
    return (truth.get(fallback), fallback if fallback in truth else None)


def _transition(before: bool | None, after: bool | None) -> str:
    if before is None or after is None:
        return "MISSING_RESULT"
    if not before and after:
        return "INCORRECT_TO_CORRECT"
    if before and not after:
        return "CORRECT_TO_INCORRECT"
    if before and after:
        return "CORRECT_RETAINED"
    return "INCORRECT_RETAINED"


def _label_change(before: str | None, after: str | None) -> str:
    if before is None or after is None:
        return "MISSING_RESULT"
    if before == after:
        return f"NO_CHANGE: {before}"
    return f"{before} -> {after}"


def _build_case_transitions(
    predictions_by_method: dict[str, dict[str, dict]],
    methods: tuple[str, ...],
) -> list[dict[str, Any]]:
    occurrence_ids = sorted({key for per_method in predictions_by_method.values() for key in per_method})
    rows: list[dict[str, Any]] = []

    for occurrence_id in occurrence_ids:
        available = [predictions_by_method.get(method, {}).get(occurrence_id) for method in methods]
        source = next((row for row in available if row is not None), {})
        row: dict[str, Any] = {
            "occurrence_id": occurrence_id,
            "sample_id": source.get("sample_id", ""),
            "file_path": source.get("file_path", ""),
            "line": source.get("line", ""),
            "column": source.get("column", ""),
            "import_name": source.get("import_name", ""),
            "imported_module": source.get("imported_module", ""),
            "error_category": source.get("error_category") or "UNCATEGORIZED",
            "ground_truth_label": source.get("ground_truth_label", ""),
            "ground_truth_distribution": source.get("ground_truth_distribution", ""),
        }

        correctness: dict[str, bool | None] = {}
        for method in methods:
            prediction = predictions_by_method.get(method, {}).get(occurrence_id)
            if prediction is None:
                row[f"{method}_prediction"] = ""
                row[f"{method}_distribution"] = ""
                row[f"{method}_correct"] = ""
                row[f"{method}_false_alert"] = ""
                correctness[method] = None
                continue

            correct = prediction_matches_ground_truth(prediction)
            correctness[method] = correct
            row[f"{method}_prediction"] = prediction.get("prediction", "")
            row[f"{method}_distribution"] = prediction.get("predicted_distribution", "")
            row[f"{method}_correct"] = correct
            row[f"{method}_false_alert"] = bool(
                prediction.get("prediction") == "NOT_FOUND"
                and prediction.get("ground_truth_label") not in PROBLEM_TRUTH_CLASSES
            )

        for before_method, after_method in zip(methods, methods[1:]):
            before_row = predictions_by_method.get(before_method, {}).get(occurrence_id)
            after_row = predictions_by_method.get(after_method, {}).get(occurrence_id)
            row[f"{before_method}_to_{after_method}_transition"] = _transition(
                correctness[before_method], correctness[after_method]
            )
            row[f"{before_method}_to_{after_method}_label_change"] = _label_change(
                before_row.get("prediction") if before_row else None,
                after_row.get("prediction") if after_row else None,
            )

        rows.append(row)
    return rows


def _build_category_summary(
    case_rows: list[dict[str, Any]],
    methods: tuple[str, ...],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in case_rows:
        grouped[str(row.get("error_category") or "UNCATEGORIZED")].append(row)

    summaries: list[dict[str, Any]] = []
    for category in sorted(grouped):
        cases = grouped[category]
        summary: dict[str, Any] = {
            "error_category": category,
            "total_occurrences": len(cases),
            "ground_truth_classes": json.dumps(dict(Counter(str(c.get("ground_truth_label") or "") for c in cases)), sort_keys=True),
        }
        for method in methods:
            observed = [case for case in cases if case.get(f"{method}_prediction", "") != ""]
            correct = sum(case.get(f"{method}_correct") is True for case in observed)
            false_alerts = sum(case.get(f"{method}_false_alert") is True for case in observed)
            ambiguous = sum(case.get(f"{method}_prediction") == "AMBIGUOUS" for case in observed)
            summary[f"{method}_evaluated"] = len(observed)
            summary[f"{method}_correct"] = correct
            summary[f"{method}_incorrect"] = len(observed) - correct
            summary[f"{method}_classification_accuracy"] = _divide(correct, len(observed))
            summary[f"{method}_false_alerts"] = false_alerts
            summary[f"{method}_ambiguous"] = ambiguous

        for before_method, after_method in zip(methods, methods[1:]):
            transition_values = [case.get(f"{before_method}_to_{after_method}_transition") for case in cases]
            for transition_name in (
                "INCORRECT_TO_CORRECT",
                "CORRECT_TO_INCORRECT",
                "CORRECT_RETAINED",
                "INCORRECT_RETAINED",
                "MISSING_RESULT",
            ):
                summary[f"{before_method}_to_{after_method}_{transition_name.lower()}"] = sum(
                    value == transition_name for value in transition_values
                )
        summaries.append(summary)

    return summaries


def run_evaluation(
    dataset_path: str | Path,
    ground_truth_path: str | Path,
    *,
    mapping_path: str | Path = "data/import_distribution_mappings.json",
    cache_dir: str | Path = "data/pypi_cache",
    methods: tuple[str, ...] = METHOD_ORDER,
) -> dict:
    samples: list[dict[str, Any]] = []
    with Path(dataset_path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if line:
                try:
                    samples.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at {dataset_path}:{line_number}: {exc}") from exc

    truth = load_ground_truth(ground_truth_path)
    predictions_by_method: dict[str, dict[str, dict]] = {method: {} for method in methods}
    all_prediction_rows: list[dict[str, Any]] = []
    unmatched_by_method: dict[str, int] = {}
    matched_truth_keys: set[str] = set()
    warnings: list[str] = []
    runtime_by_method: dict[str, float] = {}
    analysed_occurrences_by_method: dict[str, int] = {}

    for sample in samples:
        if not sample.get("sample_id"):
            raise ValueError("Every generated_outputs.jsonl record must have a non-empty sample_id.")

    def analyse_sample(sample: dict[str, Any], method: str):
        return analyse_code(
            sample.get("extracted_code", ""),
            sample_id=sample["sample_id"],
            method=method,
            file_path=sample.get("file_path") or "<snippet>",
            project_root=sample.get("project_context_path") or None,
            mapping_path=mapping_path,
            cache_dir=cache_dir,
        )

    # Warm the shared PyPI cache using the same frozen samples and all methods
    # before timing. This prevents B0 from paying cold-network latency while
    # later methods benefit from responses B0 already cached. The measured
    # runtime is explicitly a warm-cache runtime, not first-run end-to-end time.
    for method in methods:
        for sample in samples:
            analyse_sample(sample, method)

    for method in methods:
        method_started = time.perf_counter()
        unmatched = 0
        analysed_occurrences = 0
        for sample in samples:
            analysis = analyse_sample(sample, method)
            analysed_occurrences += len(analysis.results)
            for result in analysis.results:
                key = _prediction_key(result)
                gt, truth_key = _ground_truth_for_result(result, truth)
                if gt is None or truth_key is None:
                    unmatched += 1
                    continue
                matched_truth_keys.add(truth_key)

                ground_truth_label = str(gt.get("ground_truth_label") or "").strip()
                if not str(gt.get("error_category") or "").strip():
                    warnings.append(
                        f"Ground-truth error_category is blank for occurrence {key}; category output will use UNCATEGORIZED."
                    )

                row = {
                    "occurrence_id": key,
                    "sample_id": result.occurrence.sample_id,
                    "file_path": result.occurrence.file_path,
                    "line": result.occurrence.line,
                    "column": result.occurrence.column,
                    "import_name": result.occurrence.import_name,
                    "imported_module": result.occurrence.imported_module,
                    "method": method,
                    "prediction": result.label,
                    "predicted_distribution": result.distribution or "",
                    "candidates": list(result.candidates),
                    "confidence": result.confidence,
                    "ground_truth_label": ground_truth_label,
                    "ground_truth_distribution": str(gt.get("ground_truth_distribution") or "").strip(),
                    "error_category": str(gt.get("error_category") or "UNCATEGORIZED").strip() or "UNCATEGORIZED",
                    "evidence_notes": str(gt.get("evidence_notes") or "").strip(),
                    "error": result.error or "",
                }
                predictions_by_method[method][key] = row
                all_prediction_rows.append(row)

        runtime_by_method[method] = time.perf_counter() - method_started
        analysed_occurrences_by_method[method] = analysed_occurrences
        unmatched_by_method[method] = unmatched
        if unmatched:
            warnings.append(
                f"{method}: {unmatched} prediction occurrence(s) had no matching ground-truth row and were excluded."
            )

    # Report unused ground-truth rows as well: silently unmatched cases make
    # evaluation coverage look better than it is.
    matched_ids = {key for per_method in predictions_by_method.values() for key in per_method}
    unmatched_truth_count = len(set(truth) - matched_truth_keys)
    if unmatched_truth_count:
        warnings.append(
            f"{unmatched_truth_count} ground-truth row(s) did not match any extracted occurrence. Check occurrence_id, file_path, line, column, and sample_id."
        )

    baseline_rows = list(predictions_by_method.get("B0", {}).values())
    baseline_fp = calculate_metrics("B0", baseline_rows).fp if baseline_rows else 0
    all_metrics: dict[str, dict] = {}
    for method in methods:
        rows = list(predictions_by_method[method].values())
        all_metrics[method] = calculate_metrics(
            method,
            rows,
            baseline_fp if method != "B0" else None,
            runtime_seconds=runtime_by_method.get(method, 0.0),
            analysed_occurrences=analysed_occurrences_by_method.get(method, len(rows)),
        ).to_dict()

    case_rows = _build_case_transitions(predictions_by_method, methods)
    category_rows = _build_category_summary(case_rows, methods)

    return {
        "metrics": all_metrics,
        "predictions": all_prediction_rows,
        "errors_by_category": category_rows,
        "case_transitions": case_rows,
        "evaluation_summary": {
            "sample_count": len(samples),
            "ground_truth_row_count": len(truth),
            "matched_occurrences": len(matched_ids),
            "unmatched_predictions_by_method": unmatched_by_method,
            "unmatched_ground_truth_rows": unmatched_truth_count,
            "methods": list(methods),
            "runtime_mode": "warm_cache",
            "warnings": sorted(set(warnings)),
            "note": "False-alert metrics count NOT_FOUND predictions; category tables also report full classification correctness. Runtime is measured after all methods' PyPI queries have been warmed into the shared disk cache; it does not represent cold first-run latency.",
        },
    }


def _csv_safe(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    # Preserve first-seen column order across rows.
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_safe(row.get(key, "")) for key in fieldnames})


def write_evaluation(result: dict, output_path: str | Path) -> dict[str, str]:
    """Write the JSON evaluation plus reproducible CSV summary tables.

    CSV names are derived from the JSON output stem so separate runs can coexist.
    """
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    stem = target.stem
    outputs = {
        "json": target,
        "metrics_csv": target.with_name(f"{stem}_metrics_by_method.csv"),
        "category_csv": target.with_name(f"{stem}_errors_by_category.csv"),
        "transitions_csv": target.with_name(f"{stem}_case_transitions.csv"),
    }
    _write_csv(outputs["metrics_csv"], [dict(metrics) for metrics in result.get("metrics", {}).values()])
    _write_csv(outputs["category_csv"], result.get("errors_by_category", []))
    _write_csv(outputs["transitions_csv"], result.get("case_transitions", []))
    return {name: str(path) for name, path in outputs.items()}
