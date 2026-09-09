CREATE TABLE IF NOT EXISTS products (
    item_id TEXT PRIMARY KEY CHECK (length(item_id) = 24),
    original_input TEXT NOT NULL,
    source_url TEXT,
    title TEXT,
    shop_id TEXT,
    shop_name TEXT,
    observed_since TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    decision_status TEXT NOT NULL DEFAULT 'watching'
        CHECK (decision_status IN ('watching', 'reviewing', 'testing', 'dropped', 'scaling')),
    audience TEXT,
    scenario TEXT,
    problem TEXT,
    delivery TEXT,
    notes TEXT,
    next_action TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger TEXT NOT NULL
        CHECK (trigger IN ('daily', 'hourly', 'manual', 'recovery')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    success_count INTEGER NOT NULL DEFAULT 0 CHECK (success_count >= 0),
    failure_count INTEGER NOT NULL DEFAULT 0 CHECK (failure_count >= 0),
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'succeeded', 'partial', 'failed'))
);

CREATE TABLE IF NOT EXISTS collection_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES collection_runs(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES products(item_id) ON DELETE CASCADE,
    attempted_at TEXT NOT NULL,
    succeeded INTEGER NOT NULL CHECK (succeeded IN (0, 1)),
    http_status INTEGER,
    error_type TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES collection_runs(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES products(item_id) ON DELETE CASCADE,
    captured_at TEXT NOT NULL,
    source TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    sold_reported INTEGER NOT NULL CHECK (sold_reported >= 0),
    title TEXT NOT NULL,
    shop_id TEXT,
    shop_name TEXT NOT NULL,
    response_hash TEXT,
    UNIQUE (item_id, captured_at, source)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_item_time
    ON snapshots(item_id, captured_at);

CREATE INDEX IF NOT EXISTS idx_attempts_run
    ON collection_attempts(run_id, attempted_at);
