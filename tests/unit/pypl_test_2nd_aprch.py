# full source-analysis test

from src.analysis_runner import analyse_code

result = analyse_code(
    "import requests\nfrom PIL import Image\n",
    sample_id="LIVE_CHECK",
    method="PROPOSED",
    cache_dir="data/pypi_cache",
)

for item in result.results:
    print(
        item.occurrence.import_name,
        item.label,
        item.distribution,
        item.registry_status,
        item.error,
    )