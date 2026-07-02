-- Healthtech Dashboard 1.0 — initial schema.
-- Applied idempotently by web/scripts/migrate.mjs and pipeline/pipeline/db.py,
-- both of which record applied files in _migrations.

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name          TEXT,
    password_hash TEXT,                -- NULL = OTP-only account
    role          TEXT NOT NULL DEFAULT 'viewer'
                  CHECK (role IN ('viewer', 'reviewer', 'admin')),
    disabled      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,       -- sha256 of the cookie token
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE otp_codes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash  TEXT NOT NULL,          -- sha256 of the 6-digit code
    expires_at TEXT NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE companies (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name_canonical      TEXT NOT NULL UNIQUE,
    name_display        TEXT NOT NULL,
    cik                 TEXT,
    state               TEXT,
    year_of_inc         TEXT,
    entity_type         TEXT,
    industry_group      TEXT,
    focus               TEXT,
    website             TEXT,
    description         TEXT,
    description_source  TEXT,
    description_url     TEXT,
    first_surfaced_at   TEXT NOT NULL,
    first_funded_at     TEXT,
    last_updated_at     TEXT NOT NULL,
    -- review workflow (1.0): fail-closed — nothing public until validated
    status              TEXT NOT NULL DEFAULT 'pending_review'
                        CHECK (status IN ('pending_review', 'published',
                                          'invalidated', 'archived')),
    reviewed_by         INTEGER REFERENCES users(id),
    reviewed_at         TEXT,
    invalidation_reason TEXT
);
CREATE INDEX idx_companies_status ON companies(status);

CREATE TABLE filings (
    accession             TEXT PRIMARY KEY,
    company_id            INTEGER NOT NULL REFERENCES companies(id),
    source                TEXT NOT NULL,
    filing_date           TEXT,
    date_of_first_sale    TEXT,
    total_offering_amount REAL,
    filing_url            TEXT,
    observed_at           TEXT NOT NULL
);
CREATE INDEX idx_filings_company ON filings(company_id);
CREATE INDEX idx_filings_date ON filings(filing_date);

CREATE TABLE articles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id   INTEGER NOT NULL REFERENCES companies(id),
    source       TEXT NOT NULL,
    title        TEXT NOT NULL,
    url          TEXT NOT NULL UNIQUE,
    summary      TEXT,
    published_at TEXT,
    observed_at  TEXT NOT NULL
);
CREATE INDEX idx_articles_company ON articles(company_id);

CREATE TABLE tech_tags (
    company_id INTEGER NOT NULL REFERENCES companies(id),
    category   TEXT NOT NULL,
    confidence REAL NOT NULL,
    origin     TEXT NOT NULL DEFAULT 'machine'
               CHECK (origin IN ('machine', 'human')),
    tagged_at  TEXT NOT NULL,
    PRIMARY KEY (company_id, category)
);

CREATE TABLE name_aliases (
    company_id      INTEGER NOT NULL REFERENCES companies(id),
    alias_canonical TEXT NOT NULL,
    alias_display   TEXT NOT NULL,
    source          TEXT NOT NULL,
    PRIMARY KEY (company_id, alias_canonical)
);

CREATE TABLE weekly_snapshots (
    week_start         TEXT PRIMARY KEY,
    new_founded_count  INTEGER NOT NULL DEFAULT 0,
    new_funded_count   INTEGER NOT NULL DEFAULT 0,
    new_surfaced_count INTEGER NOT NULL DEFAULT 0,
    notes              TEXT,
    generated_at       TEXT NOT NULL
);

-- Replaces the POC's review/pending.md: a queryable, stateful queue.
CREATE TABLE review_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    type             TEXT NOT NULL
                     CHECK (type IN ('new_record', 'untagged', 'low_confidence',
                                     'fuzzy_match')),
    company_id       INTEGER REFERENCES companies(id),
    other_company_id INTEGER REFERENCES companies(id),   -- fuzzy_match pairs
    payload          TEXT,                               -- JSON context
    state            TEXT NOT NULL DEFAULT 'open'
                     CHECK (state IN ('open', 'resolved', 'dismissed')),
    assigned_to      INTEGER REFERENCES users(id),
    resolution_note  TEXT,
    resolved_by      INTEGER REFERENCES users(id),
    resolved_at      TEXT,
    created_at       TEXT NOT NULL,
    UNIQUE (type, company_id, other_company_id)
);
CREATE INDEX idx_review_items_state ON review_items(state);

-- Append-only audit log. Grounds the methodology's provenance claims.
CREATE TABLE revisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,          -- 'company' | 'tag' | 'review_item' | ...
    entity_id   INTEGER NOT NULL,
    action      TEXT NOT NULL,          -- 'edit' | 'validate' | 'invalidate' |
                                        -- 'merge' | 'create' | 'tag_add' | 'tag_remove'
    field       TEXT,
    old_value   TEXT,
    new_value   TEXT,
    user_id     INTEGER REFERENCES users(id),  -- NULL = pipeline
    created_at  TEXT NOT NULL
);
CREATE INDEX idx_revisions_entity ON revisions(entity_type, entity_id);

CREATE TABLE pipeline_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    window_start TEXT,
    window_end   TEXT,
    status       TEXT NOT NULL DEFAULT 'running'
                 CHECK (status IN ('running', 'succeeded', 'failed')),
    stats        TEXT,                  -- JSON: per-source counts
    qa_findings  TEXT,                  -- JSON: [{gate, level, message}]
    qa_acked_by  INTEGER REFERENCES users(id),
    qa_acked_at  TEXT,
    log_tail     TEXT
);

CREATE TABLE site_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT INTO site_settings (key, value) VALUES
    ('hero_title', 'New US healthtech companies, every week'),
    ('hero_subtitle', 'A human-reviewed repository of newly funded and newly surfaced US healthcare-technology startups, built from public SEC filings and trade press.'),
    ('publish_policy', 'fail_closed'),      -- 'fail_closed' | 'auto_badge'
    ('featured_categories', '[]'),          -- JSON array; [] = show all
    ('show_trends', '1'),
    ('cards_per_section', '12');
