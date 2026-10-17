from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocalMatch:
    matched: bool
    kind: str | None = None
    path: str | None = None


def resolve_local_module(project_root: str | Path | None, top_level_name: str) -> LocalMatch:
    if not project_root or not top_level_name:
        return LocalMatch(False)

    root = Path(project_root).resolve()
    if not root.exists() or not root.is_dir():
        return LocalMatch(False)

    module_file = root / f"{top_level_name}.py"
    if module_file.is_file():
        return LocalMatch(True, "local_py", str(module_file))

    package_dir = root / top_level_name
    if package_dir.is_dir():
        init_file = package_dir / "__init__.py"
        if init_file.is_file():
            return LocalMatch(True, "local_package", str(package_dir))

        # Namespace-like directory: require Python content to avoid treating
        # arbitrary folders as local Python modules.
        try:
            has_python = any(path.is_file() and path.suffix == ".py" for path in package_dir.rglob("*.py"))
        except OSError:
            has_python = False
        if has_python:
            return LocalMatch(True, "namespace_like_directory", str(package_dir))

    return LocalMatch(False)
