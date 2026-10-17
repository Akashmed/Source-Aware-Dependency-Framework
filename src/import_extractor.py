from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from .models import ImportOccurrence


class ImportExtractionError(SyntaxError):
    """Raised when source code cannot be parsed as Python."""


def extract_imports(
    code: str,
    *,
    sample_id: str,
    file_path: str = "<snippet>",
) -> list[ImportOccurrence]:
    try:
        tree = ast.parse(code, filename=file_path)
    except SyntaxError as exc:
        raise ImportExtractionError(str(exc)) from exc

    occurrences: list[ImportOccurrence] = []
    counter = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                counter += 1
                full_name = alias.name
                top_level = full_name.split(".", 1)[0]
                occurrences.append(
                    ImportOccurrence(
                        occurrence_id=f"{sample_id}:{counter}",
                        sample_id=sample_id,
                        file_path=file_path,
                        line=node.lineno,
                        column=node.col_offset,
                        import_name=top_level,
                        imported_module=full_name,
                        imported_names=(full_name,),
                        alias=alias.asname,
                        import_kind="import",
                        relative_level=0,
                    )
                )

        elif isinstance(node, ast.ImportFrom):
            counter += 1
            module = node.module or ""
            top_level = module.split(".", 1)[0] if module else ""
            imported_names = tuple(alias.name for alias in node.names)
            first_alias = node.names[0].asname if node.names else None
            occurrences.append(
                ImportOccurrence(
                    occurrence_id=f"{sample_id}:{counter}",
                    sample_id=sample_id,
                    file_path=file_path,
                    line=node.lineno,
                    column=node.col_offset,
                    import_name=top_level,
                    imported_module=module,
                    imported_names=imported_names,
                    alias=first_alias,
                    import_kind="from_import",
                    relative_level=node.level,
                )
            )

    return occurrences


def read_python_file(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")
