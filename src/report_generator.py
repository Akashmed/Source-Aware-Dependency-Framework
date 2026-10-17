from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .models import ResolutionResult, SampleAnalysis


def write_json(result: SampleAnalysis, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def write_text_report(result: SampleAnalysis, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "Source-Aware Dependency Verification Report",
        "=" * 45,
        f"Sample: {result.sample_id}",
        f"Method: {result.method}",
        f"Python: {result.python_version}",
        f"Analysed at: {result.analysed_at}",
        f"Parse status: {result.parse_status}",
        f"Source: {result.source_path or '<snippet>'}",
        f"Project context: {result.project_context_path or '<none>'}",
        "",
    ]

    for item in result.results:
        occ = item.occurrence
        lines.extend(
            [
                f"[{occ.file_path}:{occ.line}] {occ.imported_module or occ.import_name}",
                f"  class: {item.label}",
                f"  distribution: {item.distribution or '-'}",
                f"  confidence: {item.confidence}",
                f"  candidates: {', '.join(item.candidates) if item.candidates else '-'}",
            ]
        )
        for evidence in item.evidence:
            reference = f" | {evidence.reference}" if evidence.reference else ""
            lines.append(f"  evidence: {evidence.source} — {evidence.detail}{reference}")
        if item.error:
            lines.append(f"  note: {item.error}")
        lines.append("")

    target.write_text("\n".join(lines), encoding="utf-8")


def results_to_rows(results: Iterable[ResolutionResult]) -> list[dict]:
    rows = []
    for item in results:
        occ = item.occurrence
        rows.append(
            {
                "occurrence_id": occ.occurrence_id,
                "sample_id": occ.sample_id,
                "file_path": occ.file_path,
                "line": occ.line,
                "column": occ.column,
                "import_name": occ.import_name,
                "imported_module": occ.imported_module,
                "import_kind": occ.import_kind,
                "relative_level": occ.relative_level,
                "method_prediction": item.label,
                "distribution": item.distribution or "",
                "candidates": ";".join(item.candidates),
                "confidence": item.confidence,
                "normalized_candidate": item.normalized_candidate or "",
                "registry_status": item.registry_status or "",
                "query_timestamp": item.query_timestamp or "",
                "error": item.error or "",
                "evidence_notes": " || ".join(e.detail for e in item.evidence),
            }
        )
    return rows


def write_csv(results: Iterable[ResolutionResult], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = results_to_rows(results)
    if not rows:
        target.write_text("", encoding="utf-8")
        return
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
