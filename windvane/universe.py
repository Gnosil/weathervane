"""S&P 500 ticker → CIK universe + v0.1 fixture set.

The 12 fixtures (acceptance set) are hard-wired below. The full S&P 500
universe (~503 names) is loaded from the datahub constituents CSV, cached
locally under the data dir, and parsed into the same Ticker shape.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

import httpx

SP500_CSV_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
)

# Packaged snapshot — used when no cached copy exists and we're offline.
SEED_CSV_PATH = Path(__file__).parent / "data" / "sp500_seed.csv"


@dataclass(frozen=True)
class Ticker:
    symbol: str
    cik: str  # 10-digit zero-padded
    name: str
    fixture_role: str = ""  # "positive" | "shell" | "negative" | "" (plain universe)
    sector: str = ""  # GICS sector (universe rows only)


# 12 fixtures (v0.1 acceptance set). CIK from SEC EDGAR company_tickers.json.
FIXTURES: list[Ticker] = [
    # Positive samples (z ≥ 2 expected)
    Ticker("DOCU", "0001261333", "DocuSign Inc", "positive"),
    Ticker("TWLO", "0001447669", "Twilio Inc", "positive"),
    Ticker("HON", "0000773840", "Honeywell Intl Inc", "positive"),
    Ticker("SNAP", "0001564408", "Snap Inc", "positive"),
    Ticker("NET", "0001477333", "Cloudflare Inc", "positive"),
    # Shell pivot samples (critique must set is_shell=true + quality grade)
    Ticker("BIRD", "0001653909", "Allbirds Inc", "shell"),
    Ticker("CAPS", "0001237746", "Capstone Holding Corp", "shell"),
    # Negative samples (z < 1 expected)
    Ticker("KO", "0000021344", "Coca-Cola Co", "negative"),
    Ticker("PG", "0000080424", "Procter & Gamble Co", "negative"),
    Ticker("JNJ", "0000200406", "Johnson & Johnson", "negative"),
    Ticker("WMT", "0000104169", "Walmart Inc", "negative"),
    Ticker("JPM", "0000019617", "JPMorgan Chase & Co", "negative"),
]


def fixtures_by_role(role: str) -> list[Ticker]:
    return [t for t in FIXTURES if t.fixture_role == role]


def find_fixture(symbol: str) -> Ticker | None:
    sym = symbol.upper()
    for t in FIXTURES:
        if t.symbol == sym:
            return t
    return None


# ---------------------------------------------------------------------------
# Full S&P 500 universe
# ---------------------------------------------------------------------------
_FIXTURE_ROLES = {t.symbol: t.fixture_role for t in FIXTURES}


def _normalize_symbol(raw: str) -> str:
    """SEC EDGAR uses '-' where some indices use '.' for share classes
    (e.g. BRK.B → BRK-B). yfinance also prefers '-'."""
    return raw.strip().upper().replace(".", "-")


def _parse_constituents_csv(text: str) -> list[Ticker]:
    """Parse the datahub constituents.csv into Ticker rows.

    Columns: Symbol, Security, GICS Sector, GICS Sub-Industry,
             Headquarters Location, Date added, CIK, Founded
    """
    out: list[Ticker] = []
    reader = csv.DictReader(io.StringIO(text))
    seen: set[str] = set()
    for row in reader:
        sym = _normalize_symbol(row.get("Symbol", ""))
        cik_raw = (row.get("CIK", "") or "").strip()
        if not sym or not cik_raw.isdigit():
            continue
        if sym in seen:
            continue
        seen.add(sym)
        out.append(
            Ticker(
                symbol=sym,
                cik=cik_raw.zfill(10),
                name=(row.get("Security", "") or "").strip(),
                fixture_role=_FIXTURE_ROLES.get(sym, ""),
                sector=(row.get("GICS Sector", "") or "").strip(),
            )
        )
    return out


def load_sp500_universe(
    cache_path: Path,
    *,
    refresh: bool = False,
    timeout: float = 30.0,
) -> list[Ticker]:
    """Load the S&P 500 constituents, caching the CSV under `cache_path`.

    Resolution order:
    1. `--refresh` → fetch fresh from datahub, write to cache.
    2. cache_path exists → read it.
    3. otherwise → fall back to the packaged seed snapshot (offline-safe).
    """
    if refresh:
        resp = httpx.get(SP500_CSV_URL, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(resp.text, encoding="utf-8")
        return _parse_constituents_csv(resp.text)

    if cache_path.exists():
        return _parse_constituents_csv(cache_path.read_text(encoding="utf-8"))

    if SEED_CSV_PATH.exists():
        return _parse_constituents_csv(SEED_CSV_PATH.read_text(encoding="utf-8"))

    raise RuntimeError(
        f"No S&P 500 CSV available: cache {cache_path} missing, "
        f"seed {SEED_CSV_PATH} missing, and --refresh not set."
    )
