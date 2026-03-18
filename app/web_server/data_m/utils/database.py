# database.py

import json
from pathlib import Path

from werkzeug.security import generate_password_hash

from .db_connector import DBConnector


SCHEMA_VERSION = 7


class Database:
    def __init__(self):
        self.connector = DBConnector()
        self.project_root = Path(__file__).resolve().parents[3]
        self.upload_root = self.project_root / "web_server" / "data_m" / "assets"
        self._init_db()

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

        _, count_row = self.execute("SELECT COUNT(*) AS total FROM users", fetchone=True)
        if count_row["total"] == 0:
            self.executemany(
                """
                INSERT INTO users (username, email, login_name, display_name, password_hash, role, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "admin",
                        "admin@zertan.local",
                        "admin",
                        "Admin",
                        generate_password_hash("admin123"),
                        "administrator",
                        "active",
                    ),
                    (
                        "examiner",
                        "examiner@zertan.local",
                        "examiner",
                        "Examiner",
                        generate_password_hash("examiner123"),
                        "examiner",
                        "active",
                    ),
                    (
                        "reviewer",
                        "reviewer@zertan.local",
                        "reviewer",
                        "Reviewer",
                        generate_password_hash("reviewer123"),
                        "reviewer",
                        "active",
                    ),
                    (
                        "candidate",
                        "candidate@zertan.local",
                        "candidate",
                        "Candidate",
                        generate_password_hash("candidate123"),
                        "user",
                        "active",
                    ),
                ],
            )

        _, exams_row = self.execute("SELECT COUNT(*) AS total FROM exams", fetchone=True)
        if exams_row["total"] > 0:
            return

        ai_asset = self._ensure_svg_asset(
            "exams/ai-102/architecture-hotspot.svg",
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" viewBox="0 0 900 520">
              <rect width="900" height="520" fill="#f8fbff"/>
              <rect x="60" y="90" width="220" height="120" rx="14" fill="#dcedff" stroke="#8eb8e8"/>
              <text x="170" y="155" text-anchor="middle" font-family="Arial" font-size="24" fill="#27496d">Document Store</text>
              <rect x="340" y="90" width="220" height="120" rx="14" fill="#dcedff" stroke="#8eb8e8"/>
              <text x="450" y="155" text-anchor="middle" font-family="Arial" font-size="24" fill="#27496d">Document Intelligence</text>
              <rect x="620" y="90" width="220" height="120" rx="14" fill="#dcedff" stroke="#8eb8e8"/>
              <text x="730" y="155" text-anchor="middle" font-family="Arial" font-size="24" fill="#27496d">Azure AI Search</text>
              <circle cx="530" cy="110" r="20" fill="#27496d"/>
              <text x="530" y="117" text-anchor="middle" font-family="Arial" font-size="20" fill="#ffffff">1</text>
              <circle cx="810" cy="110" r="20" fill="#27496d"/>
              <text x="810" y="117" text-anchor="middle" font-family="Arial" font-size="20" fill="#ffffff">2</text>
              <rect x="340" y="300" width="220" height="120" rx="14" fill="#eef3f8" stroke="#9ea9b8"/>
              <text x="450" y="365" text-anchor="middle" font-family="Arial" font-size="24" fill="#51606f">Web App</text>
              <line x1="280" y1="150" x2="340" y2="150" stroke="#8eb8e8" stroke-width="6"/>
              <line x1="560" y1="150" x2="620" y2="150" stroke="#8eb8e8" stroke-width="6"/>
              <line x1="450" y1="210" x2="450" y2="300" stroke="#8eb8e8" stroke-width="6"/>
            </svg>
            """.strip(),
        )

        admin_id = self.execute(
            "SELECT id FROM users WHERE username = ?",
            ("admin",),
            fetchone=True,
        )[1]["id"]

        exams = [
            {
                "code": "AI-102",
                "title": "Designing and Implementing an Azure AI Solution",
                "provider": "Microsoft",
                "description": "Structured preparation for Azure AI services, RAG patterns, search, and responsible AI.",
                "official_url": "https://learn.microsoft.com/en-us/credentials/certifications/azure-ai-engineer/",
                "difficulty": "advanced",
                "status": "published",
                "tags": ["azure-ai", "microsoft", "production"],
            },
            {
                "code": "AZ-900",
                "title": "Microsoft Azure Fundamentals",
                "provider": "Microsoft",
                "description": "Foundational Azure study bank focused on cloud concepts, governance, and core services.",
                "official_url": "https://learn.microsoft.com/en-us/credentials/certifications/azure-fundamentals/",
                "difficulty": "foundational",
                "status": "published",
                "tags": ["azure", "fundamentals"],
            },
        ]

        for exam in exams:
            self.execute(
                """
                INSERT INTO exams (code, title, provider, description, official_url, difficulty, status, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    exam["code"],
                    exam["title"],
                    exam["provider"],
                    exam["description"],
                    exam["official_url"],
                    exam["difficulty"],
                    exam["status"],
                    admin_id,
                ),
            )
            exam_id = self.execute(
                "SELECT id FROM exams WHERE code = ?",
                (exam["code"],),
                fetchone=True,
            )[1]["id"]
            for tag in exam["tags"]:
                tag_id = self._get_or_create("tags", tag)
                self.execute(
                    "INSERT OR IGNORE INTO exam_tags (exam_id, tag_id) VALUES (?, ?)",
                    (exam_id, tag_id),
                )

        ai_exam_id = self.execute(
            "SELECT id FROM exams WHERE code = 'AI-102'",
            fetchone=True,
        )[1]["id"]
        az_exam_id = self.execute(
            "SELECT id FROM exams WHERE code = 'AZ-900'",
            fetchone=True,
        )[1]["id"]

        self._seed_questions(
            ai_exam_id,
            [
                {
                    "type": "single_select",
                    "title": "Indexer scheduling",
                    "statement": "Which Azure AI Search component is responsible for regularly pulling content from a supported data source into an index?",
                    "explanation": "Indexers orchestrate scheduled ingestion from supported data sources into Azure AI Search indexes.",
                    "difficulty": "intermediate",
                    "tags": ["azure-ai", "search"],
                    "topics": ["indexing"],
                    "options": [
                        ("A", "Skillset", 0),
                        ("B", "Indexer", 1),
                        ("C", "Synonym map", 0),
                        ("D", "Scoring profile", 0),
                    ],
                },
                {
                    "type": "multiple_choice",
                    "title": "RAG design",
                    "statement": "You are designing a retrieval-augmented generation workflow. Which actions improve answer relevance and grounding?",
                    "explanation": "Chunking, metadata filtering, and embeddings help retrieval quality. Longer prompts alone do not create grounded retrieval.",
                    "difficulty": "advanced",
                    "tags": ["rag", "azure-ai"],
                    "topics": ["retrieval"],
                    "options": [
                        ("A", "Chunk documents into semantically coherent segments", 1),
                        ("B", "Attach topic metadata for filtering", 1),
                        ("C", "Disable embeddings to reduce vector size", 0),
                        ("D", "Use embeddings for semantic retrieval", 1),
                    ],
                },
                {
                    "type": "single_select",
                    "title": "Responsible AI",
                    "statement": "Which practice best supports responsible AI review before releasing a conversational assistant?",
                    "explanation": "A documented evaluation and red-team process is core to responsible release management.",
                    "difficulty": "intermediate",
                    "tags": ["governance", "azure-ai"],
                    "topics": ["responsible-ai"],
                    "options": [
                        ("A", "Skip manual review if model confidence is high", 0),
                        ("B", "Red-team and document safety mitigations", 1),
                        ("C", "Increase token limits for all requests", 0),
                        ("D", "Expose chain-of-thought to end users", 0),
                    ],
                },
                {
                    "type": "hot_spot",
                    "title": "Service identification",
                    "statement": "For each numbered marker in the image, choose the correct Azure service from the matching dropdown.",
                    "explanation": "Marker 1 points to Document Intelligence and marker 2 points to Azure AI Search in the ingestion flow.",
                    "difficulty": "advanced",
                    "tags": ["architecture", "hotspot"],
                    "topics": ["service-identification"],
                    "config": {
                        "dropdowns": [
                            {
                                "id": "dropdown-1",
                                "order": 1,
                                "label": "Marker 1",
                                "options": [
                                    "Azure AI Search",
                                    "Azure AI Document Intelligence",
                                    "Azure AI Language",
                                ],
                                "correct_option": "Azure AI Document Intelligence",
                            },
                            {
                                "id": "dropdown-2",
                                "order": 2,
                                "label": "Marker 2",
                                "options": [
                                    "Azure AI Search",
                                    "Azure AI Content Safety",
                                    "Azure AI Vision",
                                ],
                                "correct_option": "Azure AI Search",
                            },
                        ]
                    },
                    "assets": [
                        {
                            "asset_type": "image",
                            "file_path": ai_asset,
                            "meta": {"alt": "Azure AI architecture diagram"},
                        }
                    ],
                },
                {
                    "type": "drag_drop",
                    "title": "Map each service",
                    "statement": "Drag each item to the matching responsibility.",
                    "explanation": "Each Azure AI service maps to a distinct workload concern.",
                    "difficulty": "advanced",
                    "tags": ["architecture", "dragdrop"],
                    "topics": ["service-selection"],
                    "config": {
                        "mode": "U",
                        "items": [
                            {"id": "item-search", "label": "Azure AI Search"},
                            {"id": "item-language", "label": "Azure AI Language"},
                            {"id": "item-content", "label": "Azure AI Content Safety"},
                        ],
                        "destinations": [
                            {"id": "dest-retrieval", "label": "Retrieval across indexed enterprise content"},
                            {"id": "dest-linguistic", "label": "Key phrase extraction and sentiment analysis"},
                            {"id": "dest-guardrails", "label": "Moderation and policy enforcement"},
                        ],
                        "mappings": {
                            "dest-retrieval": "item-search",
                            "dest-linguistic": "item-language",
                            "dest-guardrails": "item-content",
                        },
                    },
                },
                {
                    "type": "multiple_choice",
                    "title": "Vector search",
                    "statement": "Which statements about vector search in Azure AI Search are correct?",
                    "explanation": "Vector search depends on embeddings and can be combined with filters and keyword scoring.",
                    "difficulty": "advanced",
                    "tags": ["search", "vector"],
                    "topics": ["vector-search"],
                    "options": [
                        ("A", "Embeddings convert content into numeric vectors", 1),
                        ("B", "Vector search cannot be combined with filters", 0),
                        ("C", "Hybrid search can combine vector and keyword signals", 1),
                        ("D", "Vector fields are only useful for images", 0),
                    ],
                },
                {
                    "type": "single_select",
                    "title": "Language service",
                    "statement": "Which Azure AI service would you use for named entity recognition in text?",
                    "explanation": "Named entity recognition is part of Azure AI Language.",
                    "difficulty": "foundational",
                    "tags": ["language", "azure-ai"],
                    "topics": ["nlp"],
                    "options": [
                        ("A", "Azure AI Language", 1),
                        ("B", "Azure AI Search", 0),
                        ("C", "Azure AI Vision", 0),
                        ("D", "Azure OpenAI data plane", 0),
                    ],
                },
                {
                    "type": "single_select",
                    "title": "Latency mitigation",
                    "statement": "What is the most practical first step when an exam scenario requires lower retrieval latency for repeated prompts?",
                    "explanation": "Caching stable retrieval responses or embeddings often delivers immediate latency benefits without architectural upheaval.",
                    "difficulty": "intermediate",
                    "tags": ["operations", "performance"],
                    "topics": ["optimization"],
                    "options": [
                        ("A", "Cache stable retrieval artifacts", 1),
                        ("B", "Always increase model size", 0),
                        ("C", "Disable authentication checks", 0),
                        ("D", "Store all prompts in a single blob", 0),
                    ],
                },
            ],
        )
        self._seed_questions(
            az_exam_id,
            [
                {
                    "type": "single_select",
                    "title": "Cloud model",
                    "statement": "Which cloud model provides exclusive use of computing resources for a single organization?",
                    "explanation": "Private cloud resources are dedicated to one organization.",
                    "difficulty": "foundational",
                    "tags": ["cloud"],
                    "topics": ["cloud-concepts"],
                    "options": [
                        ("A", "Private cloud", 1),
                        ("B", "Public cloud", 0),
                        ("C", "Hybrid cloud", 0),
                        ("D", "Community cloud", 0),
                    ],
                },
                {
                    "type": "multiple_choice",
                    "title": "Benefits of cloud",
                    "statement": "Which are common benefits of cloud computing?",
                    "explanation": "Elasticity, high availability patterns, and global reach are standard cloud benefits.",
                    "difficulty": "foundational",
                    "tags": ["cloud"],
                    "topics": ["cloud-benefits"],
                    "options": [
                        ("A", "Elastic scaling", 1),
                        ("B", "Global distribution", 1),
                        ("C", "Guaranteed zero cost", 0),
                        ("D", "High availability options", 1),
                    ],
                },
                {
                    "type": "single_select",
                    "title": "CAPEX vs OPEX",
                    "statement": "Moving from buying physical servers to pay-as-you-go Azure services primarily shifts spending toward which model?",
                    "explanation": "Consumption services are generally treated as operational expenditure.",
                    "difficulty": "foundational",
                    "tags": ["finance"],
                    "topics": ["pricing"],
                    "options": [
                        ("A", "Capital expenditure", 0),
                        ("B", "Operational expenditure", 1),
                        ("C", "Deferred revenue", 0),
                        ("D", "Inventory cost", 0),
                    ],
                },
                {
                    "type": "single_select",
                    "title": "Shared responsibility",
                    "statement": "In a SaaS service, which party is primarily responsible for managing the application runtime?",
                    "explanation": "In SaaS the provider manages the application runtime and infrastructure.",
                    "difficulty": "foundational",
                    "tags": ["governance"],
                    "topics": ["shared-responsibility"],
                    "options": [
                        ("A", "Customer", 0),
                        ("B", "Provider", 1),
                        ("C", "Independent auditor", 0),
                        ("D", "Network carrier", 0),
                    ],
                },
                {
                    "type": "multiple_choice",
                    "title": "Governance tools",
                    "statement": "Which Azure services help enforce governance and compliance?",
                    "explanation": "Azure Policy and RBAC help enforce governance controls.",
                    "difficulty": "foundational",
                    "tags": ["governance"],
                    "topics": ["governance"],
                    "options": [
                        ("A", "Azure Policy", 1),
                        ("B", "Role-based access control", 1),
                        ("C", "Azure Queue Storage", 0),
                        ("D", "Azure Virtual Desktop", 0),
                    ],
                },
                {
                    "type": "single_select",
                    "title": "Regions",
                    "statement": "What is an Azure region?",
                    "explanation": "A region is a geographic area containing one or more datacenters connected by a low-latency network.",
                    "difficulty": "foundational",
                    "tags": ["infrastructure"],
                    "topics": ["regions"],
                    "options": [
                        ("A", "A pricing tier", 0),
                        ("B", "A geographic area with datacenters", 1),
                        ("C", "A type of subscription", 0),
                        ("D", "A support plan", 0),
                    ],
                },
            ],
        )

    def _seed_exam_links(self):
        seeded_links = {
            "AI-102": "https://learn.microsoft.com/en-us/credentials/certifications/azure-ai-engineer/",
            "AZ-900": "https://learn.microsoft.com/en-us/credentials/certifications/azure-fundamentals/",
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
        return str(target.relative_to(self.project_root))

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
            SET file_path = REPLACE(file_path, 'web_app/static/uploads/', 'web_server/data_m/assets/')
            WHERE file_path LIKE 'web_app/static/uploads/%'
            """
        )
        self.execute(
            """
            UPDATE users
            SET avatar_path = REPLACE(avatar_path, 'web_app/static/uploads/', 'web_server/data_m/assets/')
            WHERE avatar_path LIKE 'web_app/static/uploads/%'
            """
        )
