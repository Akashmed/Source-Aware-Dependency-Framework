import pytest

from src.import_extractor import ImportExtractionError, extract_imports


def test_extracts_import_and_from_import():
    code = "import requests as req\nfrom pandas.io import parsers\n"
    items = extract_imports(code, sample_id="S1", file_path="x.py")
    assert len(items) == 2
    assert items[0].import_name == "requests"
    assert items[0].alias == "req"
    assert items[1].import_name == "pandas"
    assert items[1].imported_module == "pandas.io"


def test_relative_import_is_marked():
    item = extract_imports("from .utils import clean\n", sample_id="S2")[0]
    assert item.relative_level == 1
    assert item.imported_module == "utils"


def test_syntax_error():
    with pytest.raises(ImportExtractionError):
        extract_imports("if True print('broken')", sample_id="S3")
