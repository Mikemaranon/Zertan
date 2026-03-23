# seeding_data.py

import json
import hashlib
import secrets

try:
    from werkzeug.security import generate_password_hash
except ModuleNotFoundError:  # pragma: no cover - fallback for limited test environments
    def generate_password_hash(password):
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            str(password).encode("utf-8"),
            salt.encode("utf-8"),
            600000,
        ).hex()
        return f"pbkdf2:sha256:600000${salt}${digest}"


class DatabaseSeeder:
    def __init__(self, db, *, runtime_config, project_root, upload_root):
        self.db = db
        self.runtime_config = runtime_config
        self.project_root = project_root
        self.upload_root = upload_root

    def seed_defaults(self):
        self.db.executemany(
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

        _, count_row = self.db.execute("SELECT COUNT(*) AS total FROM users", fetchone=True)
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

            self.db.executemany(
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

        _, exams_row = self.db.execute("SELECT COUNT(*) AS total FROM exams", fetchone=True)
        if exams_row["total"] > 0 or not self.runtime_config.get("seed_demo_content"):
            return

        admin_id = self.db.execute(
            "SELECT id FROM users WHERE username = ?",
            (admin_username,),
            fetchone=True,
        )[1]["id"]

        mock_exam = {
            "code": "ZT-100",
            "title": "Zertan Platform Mock Exam",
            "provider": "Zertan",
            "description": "Mock certification bank covering the supported interactive question types and exam behaviors of the platform.",
            "official_url": "https://github.com/Mikemaranon/Zertan",
            "difficulty": "intermediate",
            "status": "published",
            "tags": ["mock", "platform", "zt-100"],
        }

        self.db.execute(
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

        exam_id = self.db.execute(
            "SELECT id FROM exams WHERE code = ?",
            (mock_exam["code"],),
            fetchone=True,
        )[1]["id"]

        for tag in mock_exam["tags"]:
            tag_id = self._get_or_create("tags", tag)
            self.db.execute(
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

    def seed_exam_links(self):
        seeded_links = {
            "ZT-100": "https://github.com/Mikemaranon/Zertan",
        }
        for code, official_url in seeded_links.items():
            self.db.execute(
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
            self.db.execute(
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
            question_id = self.db.execute(
                "SELECT last_insert_rowid() AS id",
                fetchone=True,
            )[1]["id"]
            if not question_id:
                question_id = self.db.execute(
                    "SELECT id FROM questions WHERE exam_id = ? AND position = ?",
                    (exam_id, position),
                    fetchone=True,
                )[1]["id"]

            option_rows = [
                (question_id, key, text, is_correct, order)
                for order, (key, text, is_correct) in enumerate(question.get("options", []), start=1)
            ]
            if option_rows:
                self.db.executemany(
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
                self.db.executemany(
                    """
                    INSERT INTO question_assets (question_id, asset_type, file_path, meta_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    asset_rows,
                )

            for tag in question.get("tags", []):
                tag_id = self._get_or_create("tags", tag)
                self.db.execute(
                    "INSERT OR IGNORE INTO question_tags (question_id, tag_id) VALUES (?, ?)",
                    (question_id, tag_id),
                )
            for topic in question.get("topics", []):
                topic_id = self._get_or_create("topics", topic)
                self.db.execute(
                    "INSERT OR IGNORE INTO question_topics (question_id, topic_id) VALUES (?, ?)",
                    (question_id, topic_id),
                )
            position += 1

    def _get_or_create(self, table_name, value):
        value = value.strip()
        _, row = self.db.execute(
            f"SELECT id FROM {table_name} WHERE lower(name) = lower(?)",
            (value,),
            fetchone=True,
        )
        if row:
            return row["id"]

        self.db.execute(
            f"INSERT INTO {table_name} (name) VALUES (?)",
            (value,),
        )
        return self.db.execute(
            f"SELECT id FROM {table_name} WHERE lower(name) = lower(?)",
            (value,),
            fetchone=True,
        )[1]["id"]
