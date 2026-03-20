# database.py

import json
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

from werkzeug.security import generate_password_hash

from runtime_config import get_runtime_config
from storage_paths import build_media_path

from .db_connector import DBConnector


SCHEMA_VERSION = 8


class Database:
    def __init__(self, *, connector=None, runtime_config=None):
        self.runtime_config = dict(runtime_config or get_runtime_config())
        self.connector = connector or DBConnector(db_path=self.runtime_config["db_path"])
        self.project_root = self.runtime_config["app_root"]
        self.upload_root = self.runtime_config["media_root"]
        self.init_lock_path = self._build_init_lock_path(self.runtime_config["db_path"])
        with self._db_init_lock():
            self._init_db()

    def _build_init_lock_path(self, db_path):
        db_path = Path(db_path)
        return db_path.with_name(f"{db_path.name}.init.lock")

    @contextmanager
    def _db_init_lock(self):
        self.init_lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.init_lock_path.open("w", encoding="utf-8") as lock_file:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def execute(self, query, params=(), *, fetchone=False, fetchall=False):
        conn = self.connector.connect()
        cursor = conn.cursor()

        try:
            cursor.execute(query, params)
            conn.commit()

            op = query.strip().split()[0].upper()

            if fetchone:
                data = cursor.fetchone()
            elif fetchall:
                data = cursor.fetchall()
            else:
                data = None

            return op, data
        except Exception as exc:
            conn.rollback()
            raise exc
        finally:
            cursor.close()
            self.connector.close(conn)

    def executemany(self, query, seq_of_params):
        conn = self.connector.connect()
        cursor = conn.cursor()

        try:
            cursor.executemany(query, seq_of_params)
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise exc
        finally:
            cursor.close()
            self.connector.close(conn)

    def execute_script(self, script):
        conn = self.connector.connect()
        cursor = conn.cursor()

        try:
            cursor.executescript(script)
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise exc
        finally:
            cursor.close()
            self.connector.close(conn)

    def _init_db(self):
        self.upload_root.mkdir(parents=True, exist_ok=True)
        self._rename_legacy_live_exam_tables()
        self.execute_script(
            """
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

            CREATE TABLE IF NOT EXISTS site_features (
                feature_key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                description TEXT DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_questions_exam_id ON questions(exam_id);
            CREATE INDEX IF NOT EXISTS idx_attempts_user_id ON exam_attempts(user_id);
            CREATE INDEX IF NOT EXISTS idx_attempts_exam_id ON exam_attempts(exam_id);
            CREATE INDEX IF NOT EXISTS idx_answers_attempt_id ON exam_answers(attempt_id);
            CREATE INDEX IF NOT EXISTS idx_user_group_memberships_user_id ON user_group_memberships(user_id);
            CREATE INDEX IF NOT EXISTS idx_exam_group_assignments_group_id ON exam_group_assignments(group_id);
            CREATE INDEX IF NOT EXISTS idx_live_exam_assignments_user_id ON live_exam_assignments(user_id);
            CREATE INDEX IF NOT EXISTS idx_live_exam_assignments_live_exam_id ON live_exam_assignments(live_exam_id);
            """
        )

        self._ensure_column("exams", "official_url", "TEXT DEFAULT ''")
        self._ensure_column("users", "login_name", "TEXT")
        self._ensure_column("users", "display_name", "TEXT")
        self._ensure_column("users", "avatar_path", "TEXT")
        self._ensure_column("live_exams", "status", "TEXT NOT NULL DEFAULT 'active'")
        self._ensure_column("live_exams", "closed_at", "TEXT")
        self._migrate_legacy_live_exam_data()
        self._migrate_live_exam_status()
        self._migrate_user_identity_fields()

        _, row = self.execute(
            "SELECT version FROM schema_meta ORDER BY version DESC LIMIT 1",
            fetchone=True,
        )
        current_version = row["version"] if row else 0
        if not row:
            self.execute("INSERT INTO schema_meta (version) VALUES (?)", (SCHEMA_VERSION,))
        elif current_version < SCHEMA_VERSION:
            self.execute("UPDATE schema_meta SET version = ?", (SCHEMA_VERSION,))

        self._seed_defaults()
        self._ensure_users_indexes()
        if current_version < 2:
            self._seed_exam_links()
        if current_version < 4:
            self._migrate_static_uploads_to_data_assets()

    def _rename_legacy_live_exam_tables(self):
        assignment_columns = set(self._table_columns("live_exam_assignments"))
        if "session_id" not in assignment_columns or "live_exam_id" in assignment_columns:
            return

        rename_map = {
            "live_exam_assignments": "legacy_live_exam_assignments",
            "live_exam_sessions": "legacy_live_exam_sessions",
            "live_exam_session_questions": "legacy_live_exam_session_questions",
        }
        for source_table, target_table in rename_map.items():
            if not self._table_exists(source_table) or self._table_exists(target_table):
                continue
            self.execute(f"ALTER TABLE {source_table} RENAME TO {target_table}")

    def _migrate_legacy_live_exam_data(self):
        if not self._table_exists("legacy_live_exam_sessions"):
            return

        self.execute(
            """
            INSERT OR IGNORE INTO live_exams (
                id, exam_id, title, description, instructions, status, question_count, time_limit_minutes, criteria_json,
                created_by, created_at, updated_at, closed_at
            )
            SELECT
                ls.id,
                ls.exam_id,
                ls.title,
                '',
                '',
                CASE
                    WHEN ls.closed_at IS NOT NULL THEN 'closed'
                    ELSE 'active'
                END,
                ls.question_count,
                ls.time_limit_minutes,
                COALESCE(ls.criteria_json, '{}'),
                ls.created_by,
                ls.started_at,
                COALESCE(ls.closed_at, ls.started_at, CURRENT_TIMESTAMP),
                ls.closed_at
            FROM legacy_live_exam_sessions ls
            """
        )

        if self._table_exists("legacy_live_exam_assignments"):
            self.execute(
                """
                INSERT OR IGNORE INTO live_exam_assignments (
                    id, live_exam_id, user_id, attempt_id, assignment_status, assigned_at, started_at, completed_at
                )
                SELECT
                    la.id,
                    la.session_id,
                    la.user_id,
                    la.attempt_id,
                    CASE
                        WHEN a.status = 'submitted' THEN 'completed'
                        ELSE 'in_progress'
                    END,
                    la.created_at,
                    COALESCE(a.started_at, la.created_at),
                    a.submitted_at
                FROM legacy_live_exam_assignments la
                LEFT JOIN exam_attempts a ON a.id = la.attempt_id
                """
            )

        self.execute("DROP TABLE IF EXISTS legacy_live_exam_assignments")
        self.execute("DROP TABLE IF EXISTS legacy_live_exam_session_questions")
        self.execute("DROP TABLE IF EXISTS legacy_live_exam_sessions")

    def _migrate_live_exam_status(self):
        self.execute(
            """
            UPDATE live_exams
            SET status = CASE WHEN closed_at IS NOT NULL THEN 'closed' ELSE COALESCE(NULLIF(status, ''), 'active') END
            WHERE status IS NULL OR status = '' OR closed_at IS NOT NULL
            """
        )

    def _ensure_column(self, table, column_name, definition):
        _, rows = self.execute(f"PRAGMA table_info({table})", fetchall=True)
        existing_columns = {row["name"] for row in rows}
        if column_name not in existing_columns:
            self.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {definition}")

    def _table_exists(self, table_name):
        _, row = self.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (table_name,),
            fetchone=True,
        )
        return bool(row)

    def _table_columns(self, table_name):
        if not self._table_exists(table_name):
            return []
        _, rows = self.execute(f"PRAGMA table_info({table_name})", fetchall=True)
        return [row["name"] for row in rows]

    def _migrate_user_identity_fields(self):
        _, rows = self.execute(
            """
            SELECT id, username, email, login_name, display_name
            FROM users
            ORDER BY id
            """,
            fetchall=True,
        )
        if not rows:
            return

        reserved = set()
        for row in rows:
            current_login = (row["login_name"] or "").strip().lower()
            if current_login:
                reserved.add(current_login)

        for row in rows:
            display_name = (row["display_name"] or "").strip() or (row["username"] or "").strip() or "User"
            login_name = self._build_login_name(row, reserved)
            self.execute(
                """
                UPDATE users
                SET username = ?, login_name = ?, display_name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (login_name, login_name, display_name, row["id"]),
            )

    def _build_login_name(self, row, reserved):
        current_login = (row["login_name"] or "").strip().lower()
        if current_login and self._login_name_is_available(current_login, row["login_name"], reserved):
            return current_login

        candidates = [
            self._extract_login_candidate(row["email"]),
            (row["username"] or "").strip().lower(),
            f"user{row['id']}",
        ]
        for candidate in candidates:
            if candidate and candidate not in reserved:
                reserved.add(candidate)
                return candidate

        suffix = 2
        base = candidates[-1]
        while f"{base}{suffix}" in reserved:
            suffix += 1
        generated = f"{base}{suffix}"
        reserved.add(generated)
        return generated

    def _login_name_is_available(self, candidate, existing_value, reserved):
        existing_normalized = (existing_value or "").strip().lower()
        return candidate == existing_normalized or candidate not in reserved

    def _extract_login_candidate(self, email):
        value = (email or "").strip().lower()
        if not value:
            return ""
        local_part = value.split("@", 1)[0]
        return local_part.strip()

    def _ensure_users_indexes(self):
        self.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_login_name_unique
            ON users (lower(login_name))
            """
        )

    def _seed_defaults(self):
        self.executemany(
            """
            INSERT OR IGNORE INTO site_features (feature_key, label, description, enabled)
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    "global_stats_page",
                    "Global Stats",
                    "Expose the domain-wide statistics workspace to all authenticated users.",
                    1,
                ),
                (
                    "live_exams_page",
                    "Live Exams",
                    "Expose the assigned live exam workspace to authenticated non-administrator users.",
                    1,
                ),
            ],
        )

        admin_username = self.runtime_config.get("bootstrap_admin_username") or "admin"

        _, count_row = self.execute("SELECT COUNT(*) AS total FROM users", fetchone=True)
        if count_row["total"] == 0:
            admin_email = self.runtime_config.get("bootstrap_admin_email") or "admin@zertan.local"
            admin_password = self.runtime_config.get("bootstrap_admin_password") or ""
            seed_demo_content = bool(self.runtime_config.get("seed_demo_content"))

            if not seed_demo_content and not admin_password:
                raise RuntimeError(
                    "First startup requires ZERTAN_BOOTSTRAP_ADMIN_PASSWORD when ZERTAN_SEED_DEMO_CONTENT is disabled."
                )

            if seed_demo_content and not admin_password:
                admin_password = "admin123"

            self.executemany(
                """
                INSERT INTO users (username, email, login_name, display_name, password_hash, role, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        admin_username,
                        admin_email,
                        admin_username,
                        "Admin",
                        generate_password_hash(admin_password),
                        "administrator",
                        "active",
                    ),
                ],
            )

        _, exams_row = self.execute("SELECT COUNT(*) AS total FROM exams", fetchone=True)
        if exams_row["total"] > 0 or not self.runtime_config.get("seed_demo_content"):
            return

        admin_id = self.execute(
            "SELECT id FROM users WHERE username = ?",
            (admin_username,),
            fetchone=True,
        )[1]["id"]

        mock_exam = {
            "code": "ZT-100",
            "title": "Zertan Platform Mock Exam",
            "provider": "Zertan",
            "description": "Mock certification bank covering the supported interactive question types and exam behaviors of the platform.",
            "official_url": "https://zertan.local/exams/zt-100",
            "difficulty": "intermediate",
            "status": "published",
            "tags": ["mock", "platform", "zt-100"],
        }

        self.execute(
            """
            INSERT INTO exams (code, title, provider, description, official_url, difficulty, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mock_exam["code"],
                mock_exam["title"],
                mock_exam["provider"],
                mock_exam["description"],
                mock_exam["official_url"],
                mock_exam["difficulty"],
                mock_exam["status"],
                admin_id,
            ),
        )

        exam_id = self.execute(
            "SELECT id FROM exams WHERE code = ?",
            (mock_exam["code"],),
            fetchone=True,
        )[1]["id"]

        for tag in mock_exam["tags"]:
            tag_id = self._get_or_create("tags", tag)
            self.execute(
                "INSERT OR IGNORE INTO exam_tags (exam_id, tag_id) VALUES (?, ?)",
                (exam_id, tag_id),
            )

        self._seed_questions(
            exam_id,
            [
                {
                    "type": "single_select",
                    "title": "Official scoring source",
                    "statement": "Which mode stores official attempt statistics for KPI reporting?",
                    "explanation": "Study mode is intentionally non-official. Exam mode creates a fixed attempt and persists the evaluative statistics.",
                    "difficulty": "foundational",
                    "tags": ["modes", "scoring"],
                    "topics": ["exam-mode"],
                    "options": [
                        ("A", "Study mode", 0),
                        ("B", "Exam mode", 1),
                        ("C", "Question editor preview", 0),
                        ("D", "Import/export flow", 0),
                    ],
                },
                {
                    "type": "multiple_choice",
                    "title": "Study mode behavior",
                    "statement": "Which behaviors belong to study mode?",
                    "explanation": "Study mode is flexible: immediate correction is allowed, filters are available, and question content may be maintained by authorized roles.",
                    "difficulty": "intermediate",
                    "tags": ["study-mode", "workflow"],
                    "topics": ["study-mode"],
                    "options": [
                        ("A", "Immediate per-question correction", 1),
                        ("B", "Filtering by topic or tag", 1),
                        ("C", "Frozen official attempt scoring", 0),
                        ("D", "Question editing by authorized roles", 1),
                    ],
                },
                {
                    "type": "hot_spot",
                    "title": "Mode identification",
                    "statement": "For each numbered marker in the diagram, choose the correct workspace mode.",
                    "explanation": "Marker 1 identifies Study mode and marker 2 identifies Exam mode in the simplified workflow.",
                    "difficulty": "intermediate",
                    "tags": ["hotspot", "workflow"],
                    "topics": ["mode-identification"],
                    "config": {
                        "dropdowns": [
                            {
                                "id": "dropdown-1",
                                "order": 1,
                                "label": "Marker 1",
                                "options": [
                                    "Study mode",
                                    "Exam mode",
                                    "Admin panel",
                                ],
                                "correct_option": "Study mode",
                            },
                            {
                                "id": "dropdown-2",
                                "order": 2,
                                "label": "Marker 2",
                                "options": [
                                    "Study mode",
                                    "Exam mode",
                                    "Import package",
                                ],
                                "correct_option": "Exam mode",
                            },
                        ]
                    },
                    "assets": [
                        {
                            "asset_type": "image",
                            "file_path": "web_app/static/assets/zt-100-hotspot.svg",
                            "meta": {"alt": "ZT-100 workflow diagram"},
                        }
                    ],
                },
                {
                    "type": "drag_drop",
                    "title": "Role to responsibility",
                    "statement": "Match each role to the responsibility that best fits it. Each role can be used only once.",
                    "explanation": "This is a unique drag and drop question: every destination has a distinct correct role.",
                    "difficulty": "intermediate",
                    "tags": ["dragdrop", "roles"],
                    "topics": ["role-model"],
                    "config": {
                        "mode": "U",
                        "items": [
                            {"id": "item-admin", "label": "Administrator"},
                            {"id": "item-reviewer", "label": "Reviewer"},
                            {"id": "item-user", "label": "User"},
                        ],
                        "destinations": [
                            {"id": "dest-users", "label": "Manage users and assign roles"},
                            {"id": "dest-content", "label": "Maintain question content"},
                            {"id": "dest-attempts", "label": "Run exams and view personal results"},
                        ],
                        "mappings": {
                            "dest-users": "item-admin",
                            "dest-content": "item-reviewer",
                            "dest-attempts": "item-user",
                        },
                    },
                },
                {
                    "type": "drag_drop",
                    "title": "Mode to capability",
                    "statement": "Drag the correct mode onto each capability. A mode may be reused when appropriate.",
                    "explanation": "This is a reusable drag and drop question: Study mode correctly maps to more than one destination.",
                    "difficulty": "intermediate",
                    "tags": ["dragdrop", "modes"],
                    "topics": ["mode-capabilities"],
                    "config": {
                        "mode": "R",
                        "items": [
                            {"id": "item-study", "label": "Study mode"},
                            {"id": "item-exam", "label": "Exam mode"},
                        ],
                        "destinations": [
                            {"id": "dest-correction", "label": "Immediate answer correction"},
                            {"id": "dest-kpi", "label": "Official KPI storage"},
                            {"id": "dest-filters", "label": "Flexible filtering while reviewing content"},
                        ],
                        "mappings": {
                            "dest-correction": "item-study",
                            "dest-kpi": "item-exam",
                            "dest-filters": "item-study",
                        },
                    },
                },
            ],
        )

    def _seed_exam_links(self):
        seeded_links = {
            "ZT-100": "https://zertan.local/exams/zt-100",
        }
        for code, official_url in seeded_links.items():
            self.execute(
                """
                UPDATE exams
                SET official_url = ?, updated_at = CURRENT_TIMESTAMP
                WHERE code = ? AND COALESCE(official_url, '') = ''
                """,
                (official_url, code),
            )

    def _seed_questions(self, exam_id, questions):
        position = 1
        for question in questions:
            self.execute(
                """
                INSERT INTO questions (
                    exam_id, type, title, statement, explanation, difficulty, status, position, config_json
                ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    exam_id,
                    question["type"],
                    question.get("title", ""),
                    question["statement"],
                    question.get("explanation", ""),
                    question.get("difficulty", "intermediate"),
                    position,
                    json.dumps(question.get("config", {})),
                ),
            )
            question_id = self.execute(
                "SELECT last_insert_rowid() AS id",
                fetchone=True,
            )[1]["id"]
            if not question_id:
                question_id = self.execute(
                    "SELECT id FROM questions WHERE exam_id = ? AND position = ?",
                    (exam_id, position),
                    fetchone=True,
                )[1]["id"]

            option_rows = [
                (question_id, key, text, is_correct, order)
                for order, (key, text, is_correct) in enumerate(question.get("options", []), start=1)
            ]
            if option_rows:
                self.executemany(
                    """
                    INSERT INTO question_options (question_id, option_key, option_text, is_correct, sort_order)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    option_rows,
                )

            asset_rows = [
                (
                    question_id,
                    asset["asset_type"],
                    asset["file_path"],
                    json.dumps(asset.get("meta", {})),
                )
                for asset in question.get("assets", [])
            ]
            if asset_rows:
                self.executemany(
                    """
                    INSERT INTO question_assets (question_id, asset_type, file_path, meta_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    asset_rows,
                )

            for tag in question.get("tags", []):
                tag_id = self._get_or_create("tags", tag)
                self.execute(
                    "INSERT OR IGNORE INTO question_tags (question_id, tag_id) VALUES (?, ?)",
                    (question_id, tag_id),
                )
            for topic in question.get("topics", []):
                topic_id = self._get_or_create("topics", topic)
                self.execute(
                    "INSERT OR IGNORE INTO question_topics (question_id, topic_id) VALUES (?, ?)",
                    (question_id, topic_id),
                )
            position += 1

    def _get_or_create(self, table_name, value):
        value = value.strip()
        _, row = self.execute(
            f"SELECT id FROM {table_name} WHERE lower(name) = lower(?)",
            (value,),
            fetchone=True,
        )
        if row:
            return row["id"]

        self.execute(
            f"INSERT INTO {table_name} (name) VALUES (?)",
            (value,),
        )
        return self.execute(
            f"SELECT id FROM {table_name} WHERE lower(name) = lower(?)",
            (value,),
            fetchone=True,
        )[1]["id"]

    def _ensure_svg_asset(self, relative_path, content):
        target = self.upload_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text(content, encoding="utf-8")
        return build_media_path(relative_path)

    def _migrate_static_uploads_to_data_assets(self):
        old_root = self.project_root / "web_app" / "static" / "uploads"
        if old_root.exists():
            for source_path in old_root.rglob("*"):
                if not source_path.is_file():
                    continue
                relative_path = source_path.relative_to(old_root)
                target_path = self.upload_root / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                if not target_path.exists():
                    source_path.replace(target_path)

        self.execute(
            """
            UPDATE question_assets
            SET file_path = REPLACE(file_path, 'web_app/static/uploads/', '')
            WHERE file_path LIKE 'web_app/static/uploads/%'
            """
        )
        self.execute(
            """
            UPDATE users
            SET avatar_path = REPLACE(avatar_path, 'web_app/static/uploads/', '')
            WHERE avatar_path LIKE 'web_app/static/uploads/%'
            """
        )
        self.execute(
            """
            UPDATE question_assets
            SET file_path = REPLACE(file_path, 'web_server/data_m/assets/', '')
            WHERE file_path LIKE 'web_server/data_m/assets/%'
            """
        )
        self.execute(
            """
            UPDATE users
            SET avatar_path = REPLACE(avatar_path, 'web_server/data_m/assets/', '')
            WHERE avatar_path LIKE 'web_server/data_m/assets/%'
            """
        )
