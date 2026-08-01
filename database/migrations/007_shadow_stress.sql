-- Shadow Stress / Cognitive Hedge tables
CREATE TABLE IF NOT EXISTS shadow_hypotheses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    score INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    pattern_key TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'watching',
    outcome TEXT,
    created_at TEXT NOT NULL,
    resolve_after TEXT NOT NULL,
    resolved_at TEXT,
    exit_price REAL,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_shadow_hypotheses_status
    ON shadow_hypotheses(status, resolve_after);

CREATE TABLE IF NOT EXISTS trap_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    pattern_key TEXT NOT NULL,
    fail_streak INTEGER NOT NULL DEFAULT 1,
    cooldown_until TEXT,
    created_at TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_trap_events_symbol
    ON trap_events(symbol, created_at);

CREATE TABLE IF NOT EXISTS blackbox_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    pnl REAL NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    indicators_json TEXT NOT NULL DEFAULT '{}',
    orderbook_json TEXT NOT NULL DEFAULT '{}',
    weight_adjust_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS adaptive_weights (
    component TEXT PRIMARY KEY,
    weight REAL NOT NULL DEFAULT 1.0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS symbol_cooldowns (
    symbol TEXT PRIMARY KEY,
    cooldown_until TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
