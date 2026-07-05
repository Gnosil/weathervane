"""Environment-driven configuration. Read once at startup."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str | None = None, required: bool = False) -> str:
    val = os.environ.get(name, default)
    if required and not val:
        raise RuntimeError(
            f"Required env var {name} is not set. Copy .env.example to .env and fill it in."
        )
    return val or ""


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    # External services
    anthropic_api_key: str
    edgar_user_agent: str
    model: str

    # Paths
    data_dir: Path
    reports_dir: Path

    @property
    def db_path(self) -> Path:
        return self.data_dir / "windvane.sqlite"

    @property
    def filings_cache_dir(self) -> Path:
        return self.data_dir / "filings"

    # Scoring
    rolling_window: int
    cold_start_mu: float
    cold_start_sigma: float
    z_threshold: float



def load_settings(load_dotenv: bool = True) -> Settings:
    """Load settings from environment. Reads .env if present."""
    if load_dotenv:
        _load_dotenv_file()

    project_root = Path(__file__).resolve().parent.parent
    data_dir = Path(_env("WINDVANE_DATA_DIR", str(project_root / "data"))).expanduser()
    reports_dir = Path(_env("WINDVANE_REPORTS_DIR", str(project_root / "reports"))).expanduser()

    return Settings(
        anthropic_api_key=_env("ANTHROPIC_API_KEY", required=False),  # not needed for `init`
        edgar_user_agent=_env(
            "EDGAR_USER_AGENT",
            default="Windvane Research dan@example.com",
        ),
        model=_env("WINDVANE_MODEL", "claude-sonnet-4-5-20250929"),
        data_dir=data_dir,
        reports_dir=reports_dir,
        rolling_window=_env_int("WINDVANE_ROLLING_WINDOW", 200),
        cold_start_mu=_env_float("WINDVANE_COLD_START_MU", 0.30),
        cold_start_sigma=_env_float("WINDVANE_COLD_START_SIGMA", 0.15),
        z_threshold=_env_float("WINDVANE_Z_THRESHOLD", 2.0),
    )


def _load_dotenv_file() -> None:
    """Minimal .env loader (no external dep)."""
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
