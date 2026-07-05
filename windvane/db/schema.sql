-- Windvane SQLite schema v0.1
-- See docs/superpowers/specs/2026-05-29-windvane-design.md §6

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ---------------------------------------------------------------------------
-- Universe & pool state
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tickers (
    symbol            TEXT PRIMARY KEY,
    cik               TEXT NOT NULL,
    name              TEXT,
    sector            TEXT,    -- GICS sector (from S&P 500 constituents)
    in_sp500          INTEGER NOT NULL DEFAULT 0,
    fixture_role      TEXT,    -- 'positive' | 'shell' | 'negative' | 'universe' | NULL
    pool_status       TEXT NOT NULL DEFAULT 'screening',  -- 'screening' | 'pool' | 'active'
    entered_pool_at   TIMESTAMP,
    last_score_id     INTEGER REFERENCES scores(id) ON DELETE SET NULL,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tickers_pool_status ON tickers(pool_status);
CREATE INDEX IF NOT EXISTS idx_tickers_fixture_role ON tickers(fixture_role);

-- ---------------------------------------------------------------------------
-- SEC EDGAR filings cache
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS filings (
    accession_no            TEXT PRIMARY KEY,    -- e.g. 0001628280-25-000001
    symbol                  TEXT NOT NULL,
    filing_type             TEXT NOT NULL,       -- '10-K' | '10-Q' | '8-K'
    filing_date             DATE NOT NULL,
    period_of_report        DATE,
    primary_doc_url         TEXT,
    raw_html_path           TEXT,                -- relative path under filings_cache_dir
    extracted_items_json    TEXT,                -- {item_1, item_1a, item_7}
    fetched_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES tickers(symbol) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_filings_symbol_type ON filings(symbol, filing_type);
CREATE INDEX IF NOT EXISTS idx_filings_filing_date ON filings(filing_date);

-- ---------------------------------------------------------------------------
-- Scoring history (powers rolling window z-score)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scores (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol                   TEXT NOT NULL,
    filing_accession         TEXT NOT NULL,
    compared_against_accession TEXT,             -- prior-year filing used for diff
    raw_strength             REAL NOT NULL,      -- stage-1 output [0, 1]
    raw_strength_critiqued   REAL NOT NULL,      -- after stage-2
    z_score                  REAL NOT NULL,
    percentile               REAL,
    window_mu                REAL,
    window_sigma             REAL,
    window_size_at_scoring   INTEGER,
    scored_at                TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES tickers(symbol) ON DELETE CASCADE,
    FOREIGN KEY (filing_accession) REFERENCES filings(accession_no) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scores_symbol ON scores(symbol);
CREATE INDEX IF NOT EXISTS idx_scores_scored_at ON scores(scored_at);
CREATE INDEX IF NOT EXISTS idx_scores_z ON scores(z_score);

-- ---------------------------------------------------------------------------
-- LLM reports (full extract + critique JSON for every scoring run)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS insights (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol                TEXT NOT NULL,
    filing_accession      TEXT NOT NULL,
    score_id              INTEGER REFERENCES scores(id) ON DELETE CASCADE,
    stage1_json           TEXT NOT NULL,
    stage2_critique_json  TEXT NOT NULL,
    narrative_summary     TEXT,
    report_md_path        TEXT,                  -- relative under reports_dir
    generated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES tickers(symbol) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_insights_symbol ON insights(symbol);

-- ---------------------------------------------------------------------------
-- Backtest results (real-world performance of pool entries)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_results (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol            TEXT NOT NULL,
    score_id          INTEGER REFERENCES scores(id) ON DELETE CASCADE,
    entry_date        DATE NOT NULL,
    entry_z           REAL,
    entry_direction   TEXT NOT NULL DEFAULT 'long',  -- v0.1 default; v0.2 from verification
    return_5d         REAL,
    return_20d        REAL,
    return_60d        REAL,
    return_120d       REAL,
    alpha_5d          REAL,
    alpha_20d         REAL,
    alpha_60d         REAL,
    alpha_120d        REAL,
    benchmark         TEXT NOT NULL DEFAULT 'SPY',
    computed_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES tickers(symbol) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_backtest_symbol_entry ON backtest_results(symbol, entry_date);

-- ---------------------------------------------------------------------------
-- Schema migration tracking
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('version', '0.2.0');
