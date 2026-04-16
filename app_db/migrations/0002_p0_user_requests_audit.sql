-- P0: аудит заявок и расширение user_requests (идемпотентно через init_db + migrate).
CREATE TABLE IF NOT EXISTS request_audit_events (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES user_requests (id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    payload_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_request_audit_request ON request_audit_events (request_id);
