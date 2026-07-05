"""Rate-limited SEC EDGAR HTTP client.

SEC requires a User-Agent header with contact info and limits to 10 req/s.
See https://www.sec.gov/os/accessing-edgar-data
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any

import httpx


class RateLimiter:
    """Token-bucket-ish rate limiter for sync code.

    Default 10 req/s matches SEC EDGAR's published policy.
    """

    def __init__(self, max_per_sec: float = 10.0):
        if max_per_sec <= 0:
            raise ValueError("max_per_sec must be positive")
        self.min_interval = 1.0 / max_per_sec
        self._last_call = 0.0
        self._lock = Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            sleep_for = self.min_interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._last_call = time.monotonic()


class EdgarClient:
    """HTTP client for SEC EDGAR APIs."""

    SUBMISSIONS_BASE = "https://data.sec.gov"
    ARCHIVES_BASE = "https://www.sec.gov"

    def __init__(
        self,
        user_agent: str,
        max_per_sec: float = 10.0,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        if not user_agent or "@" not in user_agent:
            raise ValueError(
                "SEC requires a User-Agent with contact info "
                "(e.g. 'Windvane Research dan@example.com')"
            )
        self.user_agent = user_agent
        self._limiter = RateLimiter(max_per_sec)
        self._client = httpx.Client(
            headers={
                "User-Agent": user_agent,
                "Accept-Encoding": "gzip, deflate",
            },
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> EdgarClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get(self, url: str) -> httpx.Response:
        """Rate-limited GET with raise-for-status."""
        self._limiter.wait()
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp

    def get_submissions(self, cik: str) -> dict[str, Any]:
        """Fetch the submissions index for a company.

        cik: 10-digit zero-padded or shorter (will be padded).
        Returns the parsed JSON document from data.sec.gov.
        """
        cik_padded = str(cik).lstrip("0").zfill(10)
        url = f"{self.SUBMISSIONS_BASE}/submissions/CIK{cik_padded}.json"
        return self.get(url).json()

    def get_filing_html(self, cik: str, accession_no: str, primary_doc: str) -> str:
        """Fetch a filing's primary HTML document."""
        cik_int = str(int(cik))  # un-pad to integer form
        acc_nodash = accession_no.replace("-", "")
        url = f"{self.ARCHIVES_BASE}/Archives/edgar/data/{cik_int}/{acc_nodash}/{primary_doc}"
        return self.get(url).text
