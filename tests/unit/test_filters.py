from src.local_resolver import resolve_local_module
from src.stdlib_checker import is_standard_library


def test_stdlib_names():
    assert is_standard_library("os")
    assert is_standard_library("json")
    assert not is_standard_library("requests")


def test_local_module_and_package(tmp_path):
    (tmp_path / "helpers.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "utils").mkdir()
    (tmp_path / "utils" / "__init__.py").write_text("", encoding="utf-8")
    assert resolve_local_module(tmp_path, "helpers").matched
    assert resolve_local_module(tmp_path, "utils").matched
