from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .candidate_resolver import InstalledMetadataResolver, MappingStore
from .classifier import VerificationContext, verify_occurrence
from .import_extractor import ImportExtractionError, extract_imports, read_python_file
from .models import ImportOccurrence, ResolutionResult, SampleAnalysis
from .pypi_client import PyPIClient


def analyse_code(
    code: str,
    *,
    sample_id: str,
    method: str = "PROPOSED",
    file_path: str = "<snippet>",
    project_root: str | Path | None = None,
    mapping_path: str | Path = "data/import_distribution_mappings.json",
    cache_dir: str | Path = "data/pypi_cache",
    pypi_client=None,
    installed_resolver=None,
    mapping_store=None,
) -> SampleAnalysis:
    analysed_at = datetime.now(timezone.utc).isoformat()
    try:
        occurrences = extract_imports(code, sample_id=sample_id, file_path=file_path)
    except ImportExtractionError as exc:
        from .models import ImportOccurrence, ResolutionResult
        import re

        line = 0
        match = re.search(r"line (\d+)", str(exc))
        if match:
            line = int(match.group(1))
        occurrence = ImportOccurrence(
            occurrence_id=f"{sample_id}:PARSE_ERROR",
            sample_id=sample_id,
            file_path=file_path,
            line=line,
            column=0,
            import_name="",
            imported_module="",
            imported_names=(),
            alias=None,
            import_kind="parse_error",
            relative_level=0,
        )
        parse_result = ResolutionResult(
            occurrence=occurrence,
            label="PARSE_ERROR",
            confidence="None",
            error=str(exc),
        )
        return SampleAnalysis(
            sample_id=sample_id,
            method=method,
            source_type="snippet" if file_path == "<snippet>" else "file",
            python_version=_python_version(),
            analysed_at=analysed_at,
            parse_status="PARSE_ERROR",
            results=[parse_result],
            source_path=None if file_path == "<snippet>" else file_path,
            project_context_path=str(project_root) if project_root else None,
        )

    context = VerificationContext(
        mapping_store=mapping_store or MappingStore(mapping_path),
        installed_resolver=installed_resolver if installed_resolver is not None else InstalledMetadataResolver(),
        pypi_client=pypi_client if pypi_client is not None else PyPIClient(cache_dir=cache_dir),
        project_root=project_root,
    )

    results = [verify_occurrence(item, method, context) for item in occurrences]
    return SampleAnalysis(
        sample_id=sample_id,
        method=method,
        source_type="snippet" if file_path == "<snippet>" else "file",
        python_version=_python_version(),
        analysed_at=analysed_at,
        parse_status="OK",
        results=results,
        source_path=None if file_path == "<snippet>" else file_path,
        project_context_path=str(project_root) if project_root else None,
    )


def analyse_file(path: str | Path, **kwargs) -> SampleAnalysis:
    file = Path(path).resolve()
    return analyse_code(
        read_python_file(file),
        file_path=str(file),
        project_root=kwargs.pop("project_root", file.parent),
        **kwargs,
    )


def analyse_project(root: str | Path, *, sample_id: str, **kwargs) -> list[SampleAnalysis]:
    project = Path(root).resolve()
    analyses = []
    for file in sorted(project.rglob("*.py")):
        try:
            code = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = str(file.relative_to(project))
        analyses.append(
            analyse_code(
                code,
                sample_id=f"{sample_id}:{relative}",
                file_path=relative,
                project_root=project,
                **kwargs,
            )
        )
    return analyses


def _python_version() -> str:
    import platform

    return platform.python_version()
