"""EdgarClient rate limiter & request shape tests (no live network)."""

from __future__ import annotations

import time

import httpx
import pytest

from windvane.edgar.client import EdgarClient, RateLimiter


def test_rate_limiter_enforces_min_interval() -> None:
    rl = RateLimiter(max_per_sec=20.0)  # 50ms min
    t0 = time.monotonic()
    rl.wait()  # first call returns immediately
    rl.wait()
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.045  # allow scheduling jitter


def test_rate_limiter_rejects_nonpositive_rate() -> None:
    with pytest.raises(ValueError):
        RateLimiter(max_per_sec=0.0)


def test_client_requires_contact_user_agent() -> None:
    with pytest.raises(ValueError):
        EdgarClient(user_agent="anonymous-bot")


def test_get_submissions_hits_data_sec_gov() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["user_agent"] = request.headers.get("User-Agent")
        return httpx.Response(200, json={"filings": {"recent": {}}})

    transport = httpx.MockTransport(handler)
    client = EdgarClient(user_agent="Windvane test@example.com", transport=transport)
    try:
        result = client.get_submissions("1234")
    finally:
        client.close()

    assert "data.sec.gov" in captured["url"]
    assert "CIK0000001234.json" in captured["url"]
    assert "test@example.com" in captured["user_agent"]
    assert isinstance(result, dict)


def test_get_filing_html_constructs_archives_url() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, text="<html>10-K body</html>")

    transport = httpx.MockTransport(handler)
    client = EdgarClient(user_agent="Windvane test@example.com", transport=transport)
    try:
        html = client.get_filing_html(
            cik="0001261333",
            accession_no="0001261333-25-000034",
            primary_doc="docu-20250131.htm",
        )
    finally:
        client.close()

    url = captured["url"]
    assert "www.sec.gov" in url
    assert "Archives/edgar/data/1261333/000126133325000034/docu-20250131.htm" in url
    assert "10-K" in html
