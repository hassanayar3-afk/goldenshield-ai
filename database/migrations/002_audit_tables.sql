CREATE TABLE IF NOT EXISTS market_snapshots (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    price REAL NOT NULL,
    score INTEGER NOT NULL,
    signal TEXT NOT NULL,
    passed INTEGER NOT NULL,
    halted INTEGER NOT NULL,
    reasons TEXT NOT NULL,
    sma REAL NOT NULL,
    captured_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_records (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL,
    snapshot_id TEXT,
    position_id TEXT,
    pnl REAL,
    shadow_consensus INTEGER,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY (snapshot_id) REFERENCES market_snapshots(id)
);

CREATE TABLE IF NOT EXISTS operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
