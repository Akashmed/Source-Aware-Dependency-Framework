# direct pypl client test

from tempfile import TemporaryDirectory

from src.pypi_client import PyPIClient


packages_to_test = (
    "requests",
    "Pillow",
    "PIL",
    "your-package-name",
)

with TemporaryDirectory() as cache_dir:
    client = PyPIClient(
        cache_dir=cache_dir,
        timeout=10,
        retries=2,
    )

    for package_name in packages_to_test:
        result = client.get_project(package_name)

        print(f"Package: {package_name}")
        print(f"Normalized name: {result.project}")
        print(f"HTTP status: {result.status}")
        print(f"Exists: {result.exists}")
        print(f"From cache: {result.from_cache}")
        print(f"Error: {result.error}")
        print("-" * 40)