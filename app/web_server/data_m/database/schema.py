SCHEMA_VERSION = 11

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT UNIQUE,
    login_name TEXT,
    display_name TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    status TEXT NOT NULL DEFAULT 'active',
    avatar_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS user_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_group_memberships (
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (group_id, user_id),
    FOREIGN KEY (group_id) REFERENCES user_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    provider TEXT NOT NULL,
    description TEXT DEFAULT '',
    official_url TEXT DEFAULT '',
    difficulty TEXT DEFAULT 'intermediate',
    status TEXT NOT NULL DEFAULT 'draft',
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS exam_tags (
    exam_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (exam_id, tag_id),
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS exam_group_assignments (
    exam_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (exam_id, group_id),
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES user_groups(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    title TEXT DEFAULT '',
    statement TEXT NOT NULL,
    explanation TEXT DEFAULT '',
    difficulty TEXT DEFAULT 'intermediate',
    status TEXT NOT NULL DEFAULT 'active',
    position INTEGER NOT NULL DEFAULT 0,
    config_json TEXT DEFAULT '{}',
    source_json_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TEXT,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS question_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    option_key TEXT NOT NULL,
    option_text TEXT NOT NULL,
    is_correct INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS question_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    asset_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    meta_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS question_tags (
    question_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (question_id, tag_id),
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS question_topics (
    question_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    PRIMARY KEY (question_id, topic_id),
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS exam_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress',
    criteria_json TEXT DEFAULT '{}',
    question_count INTEGER NOT NULL DEFAULT 0,
    random_order INTEGER NOT NULL DEFAULT 1,
    time_limit_minutes INTEGER,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    submitted_at TEXT,
    duration_seconds INTEGER,
    score_percent REAL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    incorrect_count INTEGER NOT NULL DEFAULT 0,
    omitted_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS exam_attempt_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    question_order INTEGER NOT NULL,
    page_number INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS exam_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_question_id INTEGER NOT NULL UNIQUE,
    attempt_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    response_json TEXT,
    is_correct INTEGER,
    score REAL DEFAULT 0,
    omitted INTEGER NOT NULL DEFAULT 1,
    answered_at TEXT,
    FOREIGN KEY (attempt_question_id) REFERENCES exam_attempt_questions(id) ON DELETE CASCADE,
    FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS live_exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    instructions TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    question_count INTEGER NOT NULL DEFAULT 10,
    time_limit_minutes INTEGER,
    criteria_json TEXT DEFAULT '{}',
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS live_exam_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    live_exam_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    attempt_id INTEGER UNIQUE,
    assignment_status TEXT NOT NULL DEFAULT 'pending',
    assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (live_exam_id) REFERENCES live_exams(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id) ON DELETE SET NULL,
    UNIQUE (live_exam_id, user_id)
);

CREATE TABLE IF NOT EXISTS data_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source TEXT,
    level TEXT,
    message TEXT,
    payload TEXT
);

CREATE TABLE IF NOT EXISTS agent_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS log_registry_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    actor_user_id INTEGER,
    actor_login_name TEXT NOT NULL DEFAULT '',
    actor_display_name TEXT NOT NULL DEFAULT '',
    actor_role TEXT NOT NULL DEFAULT '',
    exam_id INTEGER,
    exam_code TEXT NOT NULL DEFAULT '',
    exam_title TEXT NOT NULL DEFAULT '',
    question_id INTEGER,
    question_label TEXT NOT NULL DEFAULT '',
    question_type TEXT NOT NULL DEFAULT '',
    question_position INTEGER,
    details TEXT DEFAULT '',
    before_snapshot_json TEXT,
    after_snapshot_json TEXT,
    before_content_text TEXT DEFAULT '',
    after_content_text TEXT DEFAULT '',
    diff_text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS log_registry_scope_groups (
    log_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    group_code TEXT NOT NULL DEFAULT '',
    group_name TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (log_id, group_id),
    FOREIGN KEY (log_id) REFERENCES log_registry_entries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS site_features (
    feature_key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    description TEXT DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS server_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT DEFAULT '',
    host TEXT NOT NULL UNIQUE,
    host_type TEXT NOT NULL,
    port INTEGER,
    verification_status TEXT NOT NULL DEFAULT 'pending',
    verification_message TEXT DEFAULT '',
    resolved_ips_json TEXT DEFAULT '[]',
    last_verified_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_questions_exam_id ON questions(exam_id);
CREATE INDEX IF NOT EXISTS idx_question_options_question_id_sort_order ON question_options(question_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_question_assets_question_id ON question_assets(question_id);
CREATE INDEX IF NOT EXISTS idx_question_tags_question_id ON question_tags(question_id);
CREATE INDEX IF NOT EXISTS idx_question_topics_question_id ON question_topics(question_id);
CREATE INDEX IF NOT EXISTS idx_exam_tags_exam_id ON exam_tags(exam_id);
CREATE INDEX IF NOT EXISTS idx_attempts_user_id ON exam_attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_attempts_exam_id ON exam_attempts(exam_id);
CREATE INDEX IF NOT EXISTS idx_attempt_questions_attempt_order ON exam_attempt_questions(attempt_id, question_order);
CREATE INDEX IF NOT EXISTS idx_attempt_questions_attempt_page_order ON exam_attempt_questions(attempt_id, page_number, question_order);
CREATE INDEX IF NOT EXISTS idx_answers_attempt_id ON exam_answers(attempt_id);
CREATE INDEX IF NOT EXISTS idx_answers_question_id ON exam_answers(question_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id_expires_at ON sessions(user_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_user_group_memberships_user_id ON user_group_memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_exam_group_assignments_group_id ON exam_group_assignments(group_id);
CREATE INDEX IF NOT EXISTS idx_live_exams_status ON live_exams(status, created_at);
CREATE INDEX IF NOT EXISTS idx_live_exam_assignments_user_id ON live_exam_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_live_exam_assignments_live_exam_id ON live_exam_assignments(live_exam_id);
CREATE INDEX IF NOT EXISTS idx_log_registry_exam_id_created_at ON log_registry_entries(exam_id, created_at);
CREATE INDEX IF NOT EXISTS idx_log_registry_action_created_at ON log_registry_entries(action, created_at);
CREATE INDEX IF NOT EXISTS idx_log_registry_scope_group_id ON log_registry_scope_groups(group_id, log_id);
"""
