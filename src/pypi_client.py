from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from packaging.utils import canonicalize_name


@dataclass
class PyPIResponse:
    project: str
    status: int | None
    exists: bool | None
    data: dict | None
    timestamp: str
    from_cache: bool = False
    error: str | None = None


class PyPIClient:
    def __init__(self, cache_dir: str | Path = "data/pypi_cache", timeout: float = 10.0, retries: int = 2):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "source-aware-dependency-verifier/0.1"})

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _cache_path(self, project: str) -> Path:
        return self.cache_dir / f"{canonicalize_name(project)}.json"

    def get_project(self, project: str) -> PyPIResponse:
        normalized = str(canonicalize_name(project))
        cache_path = self._cache_path(normalized)
        if cache_path.exists():
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                return PyPIResponse(
                    project=normalized,
                    status=payload.get("status"),
                    exists=payload.get("exists"),
                    data=payload.get("data"),
                    timestamp=payload.get("timestamp") or self._now(),
                    from_cache=True,
                    error=payload.get("error"),
                )
            except (OSError, json.JSONDecodeError):
                pass

        url = f"https://pypi.org/pypi/{quote(normalized, safe='-.~')}/json"
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                timestamp = self._now()
                if response.status_code == 200:
                    data = response.json()
                    result = PyPIResponse(normalized, 200, True, data, timestamp)
                elif response.status_code == 404:
                    result = PyPIResponse(normalized, 404, False, None, timestamp)
                else:
                    result = PyPIResponse(
                        normalized,
                        response.status_code,
                        None,
                        None,
                        timestamp,
                        error=f"Unexpected HTTP status {response.status_code}",
                    )
                cache_path.write_text(
                    json.dumps(result.__dict__, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return result
            except (requests.RequestException, ValueError) as exc:
                last_error = str(exc)
                if attempt < self.retries:
                    time.sleep(0.5 * (attempt + 1))

        return PyPIResponse(
            project=normalized,
            status=None,
            exists=None,
            data=None,
            timestamp=self._now(),
            error=last_error or "Unknown network error",
        )
