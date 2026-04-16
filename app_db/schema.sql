-- SQLite schema for supplier orchestration MVP
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS suppliers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    inn TEXT,
    city TEXT,
    activity_direction TEXT,
    website_url TEXT,
    email TEXT,
    phone TEXT,
    source TEXT,
    verification_status TEXT,
    notes_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (inn)
);

CREATE INDEX IF NOT EXISTS idx_suppliers_city_direction ON suppliers (city, activity_direction);

CREATE TABLE IF NOT EXISTS user_requests (
    id TEXT PRIMARY KEY,
    raw_query TEXT NOT NULL,
    structured_json TEXT,
    clarification_json TEXT,
    selected_supplier_ids TEXT,
    city TEXT,
    activity_direction TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS request_audit_events (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES user_requests (id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    payload_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_request_audit_request ON request_audit_events (request_id);

CREATE TABLE IF NOT EXISTS outbound_email_drafts (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES user_requests (id) ON DELETE CASCADE,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    user_confirmed INTEGER NOT NULL DEFAULT 0,
    sent_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_outbound_request ON outbound_email_drafts (request_id);

-- Сессии оркестратора заявок (то же определение, что SESSIONS_DDL в orchestration/service.py)
CREATE TABLE IF NOT EXISTS orchestration_sessions (
    request_id TEXT PRIMARY KEY,
    step TEXT NOT NULL,
    context_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Асинхронные задачи GET/POST /api/v1/search (общая БД с поставщиками)
CREATE TABLE IF NOT EXISTS api_search_jobs (
    search_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    product TEXT NOT NULL,
    region TEXT NOT NULL,
    quantity TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error_message TEXT,
    result_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_api_search_jobs_status ON api_search_jobs (status);

-- BEGIN FTS5 OPTIONAL
-- Полнотекстовый индекс поставщиков (FTS5, tokenize unicode61 — базовая поддержка Unicode).
-- Выполняется отдельно из init_db в ensure_suppliers_fts() в try/except, чтобы сборка без FTS5 не ломала инициализацию.
CREATE VIRTUAL TABLE IF NOT EXISTS suppliers_fts USING fts5(
    name,
    city,
    activity_direction,
    inn,
    content='suppliers',
    content_rowid='rowid',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS suppliers_fts_ai AFTER INSERT ON suppliers BEGIN
    INSERT INTO suppliers_fts(rowid, name, city, activity_direction, inn)
    VALUES (new.rowid, new.name, new.city, new.activity_direction, new.inn);
END;

CREATE TRIGGER IF NOT EXISTS suppliers_fts_ad AFTER DELETE ON suppliers BEGIN
    INSERT INTO suppliers_fts(suppliers_fts, rowid, name, city, activity_direction, inn)
    VALUES ('delete', old.rowid, old.name, old.city, old.activity_direction, old.inn);
END;

CREATE TRIGGER IF NOT EXISTS suppliers_fts_au AFTER UPDATE ON suppliers BEGIN
    INSERT INTO suppliers_fts(suppliers_fts, rowid, name, city, activity_direction, inn)
    VALUES ('delete', old.rowid, old.name, old.city, old.activity_direction, old.inn);
    INSERT INTO suppliers_fts(rowid, name, city, activity_direction, inn)
    VALUES (new.rowid, new.name, new.city, new.activity_direction, new.inn);
END;
