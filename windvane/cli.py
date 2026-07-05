"""Windvane CLI (typer).

Top-level commands:
    init       Initialize SQLite + seed fixture universe.
    scan       Run L1 screening pass.
    report     Render a per-day report.
    backtest   Run backtest harness.
    daemon     Start scheduled daemon (every day 17:30 ET).
"""

from __future__ import annotations

from datetime import date

import typer
from rich.console import Console
from rich.table import Table

from windvane import __version__
from windvane.config import load_settings
from windvane.db import connect, init_schema
from windvane.db.connection import seed_universe
from windvane.universe import FIXTURES

app = typer.Typer(
    name="windvane",
    help="风向标 — US equity industry-pivot detection.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.command()
def version() -> None:
    """Print version."""
    console.print(f"windvane {__version__}")


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="Drop existing DB first."),
) -> None:
    """Initialize SQLite schema and seed fixture universe."""
    settings = load_settings()
    if force and settings.db_path.exists():
        settings.db_path.unlink()
        console.print(f"[yellow]Dropped existing DB at {settings.db_path}[/yellow]")

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    settings.filings_cache_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"Initializing schema at [cyan]{settings.db_path}[/cyan] ...")
    init_schema(settings.db_path)

    n = seed_universe(settings.db_path, FIXTURES)
    console.print(f"Seeded [green]{n}[/green] fixture tickers.")

    # Verify
    with connect(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT fixture_role, COUNT(*) AS n FROM tickers "
            "WHERE fixture_role IS NOT NULL GROUP BY fixture_role"
        ).fetchall()

    table = Table(title="Fixture universe")
    table.add_column("Role")
    table.add_column("Count", justify="right")
    for r in rows:
        table.add_row(r["fixture_role"], str(r["n"]))
    console.print(table)
    console.print("[green]✓ Init complete.[/green]")


@app.command(name="load-universe")
def load_universe(
    refresh: bool = typer.Option(False, "--refresh", help="Re-fetch the constituents CSV."),
) -> None:
    """Load the full S&P 500 universe (~503 names) into SQLite."""
    from windvane.universe import load_sp500_universe

    settings = load_settings()
    if not settings.db_path.exists():
        console.print("[yellow]DB not initialized. Run `windvane init` first.[/yellow]")
        raise typer.Exit(code=2)

    cache_path = settings.data_dir / "sp500_constituents.csv"
    console.print(f"Loading S&P 500 universe (cache: {cache_path}) ...")
    tickers = load_sp500_universe(cache_path, refresh=refresh)
    n = seed_universe(settings.db_path, tickers)

    with connect(settings.db_path) as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM tickers WHERE in_sp500=1").fetchone()["c"]
        by_sector = conn.execute(
            "SELECT sector, COUNT(*) AS c FROM tickers "
            "WHERE sector IS NOT NULL AND sector != '' GROUP BY sector ORDER BY c DESC"
        ).fetchall()

    console.print(
        f"Seeded [green]{n}[/green] constituents. Universe total: [green]{total}[/green]."
    )
    table = Table(title="By GICS sector")
    table.add_column("Sector")
    table.add_column("Count", justify="right")
    for r in by_sector:
        table.add_row(r["sector"], str(r["c"]))
    console.print(table)


@app.command()
def scan(
    ticker: str | None = typer.Option(
        None, "--ticker", "-t", help="Single ticker; default = full universe."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Don't call LLM; report what would be done."
    ),
) -> None:
    """Run L1 screening pass (TODO v0.1 #3-#6)."""
    console.print(f"[yellow]TODO[/yellow] scan ticker={ticker or 'ALL'} dry_run={dry_run}")
    console.print("[dim]Implementation lands in tasks #3-#6.[/dim]")
    raise typer.Exit(code=0)


@app.command()
def report(
    report_date: str | None = typer.Option(
        None, "--date", help="ISO date (YYYY-MM-DD). Default = today."
    ),
) -> None:
    """Render a per-day report (TODO v0.1 #7)."""
    d = date.fromisoformat(report_date) if report_date else date.today()
    console.print(f"[yellow]TODO[/yellow] report for {d}")
    raise typer.Exit(code=0)


@app.command()
def backtest(
    fixtures: bool = typer.Option(False, "--fixtures", help="Run the 12-fixture suite."),
    ticker: str | None = typer.Option(None, "--ticker", "-t"),
    entry: str | None = typer.Option(None, "--entry", help="ISO entry date for single ticker."),
    all_pool: bool = typer.Option(False, "--all", help="All historical pool entries."),
    save: bool = typer.Option(
        True, "--save/--no-save", help="Persist results to SQLite + Markdown."
    ),
) -> None:
    """Backtest pool entries: T+5/20/60/120 returns + α vs SPY."""
    from datetime import date as _date

    from windvane.backtest import (
        backtest_fixtures,
        backtest_single,
        persist_results,
        render_summary_markdown,
    )

    settings = load_settings()
    cache_dir = settings.data_dir / "prices"

    if fixtures:
        console.print("[cyan]Running 12-fixture backtest suite ...[/cyan]")
        rows = backtest_fixtures(cache_dir=cache_dir)
        title = "Windvane Fixture Backtest"
    elif ticker:
        if not entry:
            console.print("[red]--ticker requires --entry YYYY-MM-DD[/red]")
            raise typer.Exit(code=2)
        entry_d = _date.fromisoformat(entry)
        console.print(f"[cyan]Backtesting {ticker.upper()} from {entry_d} ...[/cyan]")
        rows = [
            backtest_single(
                ticker.upper(),
                entry_d,
                cache_dir=cache_dir,
            )
        ]
        title = f"Windvane Backtest — {ticker.upper()} @ {entry_d}"
    elif all_pool:
        console.print("[yellow]--all wiring lands in v0.1 #9 (fixtures task).[/yellow]")
        raise typer.Exit(code=0)
    else:
        console.print("[red]Provide --fixtures, --ticker, or --all[/red]")
        raise typer.Exit(code=2)

    # Render to console
    table = Table(title=title)
    table.add_column("Symbol")
    table.add_column("Role")
    table.add_column("Entry")
    table.add_column("T+5 α", justify="right")
    table.add_column("T+20 α", justify="right")
    table.add_column("T+60 α", justify="right")
    table.add_column("T+120 α", justify="right")
    for r in rows:

        def fmt(v: float | None) -> str:
            return "N/A" if v is None else f"{v * 100:+.2f}%"

        table.add_row(
            r.point.symbol,
            r.fixture_role or "-",
            r.point.entry_date.isoformat(),
            fmt(r.point.alpha_pct.get(5)),
            fmt(r.point.alpha_pct.get(20)),
            fmt(r.point.alpha_pct.get(60)),
            fmt(r.point.alpha_pct.get(120)),
        )
    console.print(table)

    if save:
        # Write markdown
        out_dir = settings.reports_dir / "backtest" / _date.today().isoformat()
        out_dir.mkdir(parents=True, exist_ok=True)
        md_path = out_dir / "summary.md"
        md_path.write_text(render_summary_markdown(rows, title=title), encoding="utf-8")
        console.print(f"[green]Markdown report:[/green] {md_path}")

        # Persist to SQLite (only if DB exists — `init` must have been run)
        if settings.db_path.exists():
            n = persist_results(settings.db_path, rows)
            console.print(f"[green]Persisted {n} rows to backtest_results.[/green]")
        else:
            console.print(
                "[yellow]DB not initialized; skipping SQLite persist. Run `windvane init` first.[/yellow]"
            )


@app.command()
def daemon() -> None:
    """Start scheduled daemon (TODO v0.1 #7)."""
    console.print("[yellow]TODO[/yellow] daemon — APScheduler every-day 17:30 ET")
    raise typer.Exit(code=0)




@app.command()
def watch(
    once: bool = typer.Option(False, "--once", help="Run a single polling pass then exit."),
    top: int = typer.Option(15, "--top", help="Watch the top-N names from the latest scan."),
    interval: int = typer.Option(900, "--interval", help="Seconds between polls during market hours."),
    no_notify: bool = typer.Option(False, "--no-notify", help="Don't post macOS notifications."),
    symbols: str | None = typer.Option(None, "--symbols", help="Comma-separated tickers."),
) -> None:
    """24h watch: poll the watchlist, alert on anomalies (free yfinance data)."""
    from windvane.watch.watcher import WatchConfig, load_watchlist, watch_loop

    settings = load_settings()
    if symbols:
        syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    else:
        syms = load_watchlist(settings.reports_dir, top=top)
    if not syms:
        console.print("[yellow]Watchlist empty. Run a scan first.[/yellow]")
        raise typer.Exit(code=2)
    console.print(f"[cyan]Watching {len(syms)} names:[/cyan] {', '.join(syms)}")
    cfg = WatchConfig(symbols=syms, interval_sec=interval, notify=not no_notify,
                      alerts_log=settings.reports_dir / "watch" / "alerts.jsonl")
    if once:
        fired = watch_loop(cfg, once=True)
        if fired:
            for a in fired:
                console.print(f"  [red]X[/red] {a.message}")
            console.print(f"[green]{len(fired)} alert(s). Logged.[/green]")
        else:
            console.print("[dim]No anomalies this pass.[/dim]")
        return
    console.print(f"[green]Watch loop started[/green] (every {interval}s, market hours). Ctrl-C to stop.")
    try:
        watch_loop(cfg, once=False)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")


@app.command(name="watch-install")
def watch_install() -> None:
    """Install the 24h watcher as a macOS auto-start service (launchd)."""
    from pathlib import Path as _P

    from windvane.watch.launchd import install

    settings = load_settings()
    project_dir = _P(__file__).resolve().parent.parent
    target, cmds = install(project_dir, settings.reports_dir / "watch", _P.home())
    console.print(f"[green]OK 已生成开机自启配置:[/green] {target}")
    console.print("\n[bold]最后一步 - 复制下面两行到终端回车:[/bold]")
    for c in cmds:
        console.print(f"  [cyan]{c}[/cyan]")


if __name__ == "__main__":
    app()
