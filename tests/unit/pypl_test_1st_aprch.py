# direct pypl client test

import sys
from tempfile import TemporaryDirectory
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.analysis_runner import analyse_code


with TemporaryDirectory() as cache_dir:
    analysis = analyse_code(
        "import requests\n"
        "import PIL\n"
        "import dateutil\n",
        sample_id="DIRECT_PYPI_CHECK",
        method="PROPOSED",
        cache_dir=cache_dir,
    )

    for result in analysis.results:
        print(f"Import: {result.occurrence.import_name}")
        print(f"Distribution: {result.distribution}")
        print(f"Candidates: {result.candidates}")
        print(f"Label: {result.label}")
        print(f"HTTP status: {result.registry_status}")
        print(f"Error: {result.error}")
        print("-" * 40)