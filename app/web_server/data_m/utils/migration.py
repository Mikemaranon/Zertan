# migration.py


class DatabaseMigrationManager:
    def __init__(self, db, *, project_root, upload_root):
        self.db = db
        self.project_root = project_root
        self.upload_root = upload_root

    def rename_legacy_live_exam_tables(self):
        assignment_columns = set(self.db.integrity.table_columns("live_exam_assignments"))
        if "session_id" not in assignment_columns or "live_exam_id" in assignment_columns:
            return

        rename_map = {
            "live_exam_assignments": "legacy_live_exam_assignments",
            "live_exam_sessions": "legacy_live_exam_sessions",
            "live_exam_session_questions": "legacy_live_exam_session_questions",
        }
        for source_table, target_table in rename_map.items():
            if not self.db.integrity.table_exists(source_table) or self.db.integrity.table_exists(target_table):
                continue
            self.db.execute(f"ALTER TABLE {source_table} RENAME TO {target_table}")

    def migrate_legacy_live_exam_data(self):
        if not self.db.integrity.table_exists("legacy_live_exam_sessions"):
            return

        self.db.execute(
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

        if self.db.integrity.table_exists("legacy_live_exam_assignments"):
            self.db.execute(
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

        self.db.execute("DROP TABLE IF EXISTS legacy_live_exam_assignments")
        self.db.execute("DROP TABLE IF EXISTS legacy_live_exam_session_questions")
        self.db.execute("DROP TABLE IF EXISTS legacy_live_exam_sessions")

    def migrate_live_exam_status(self):
        self.db.execute(
            """
            UPDATE live_exams
            SET status = CASE WHEN closed_at IS NOT NULL THEN 'closed' ELSE COALESCE(NULLIF(status, ''), 'active') END
            WHERE status IS NULL OR status = '' OR closed_at IS NOT NULL
            """
        )

    def migrate_user_identity_fields(self):
        _, rows = self.db.execute(
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
            self.db.execute(
                """
                UPDATE users
                SET username = ?, login_name = ?, display_name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (login_name, login_name, display_name, row["id"]),
            )

    def migrate_static_uploads_to_data_assets(self):
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

        self.db.execute(
            """
            UPDATE question_assets
            SET file_path = REPLACE(file_path, 'web_app/static/uploads/', '')
            WHERE file_path LIKE 'web_app/static/uploads/%'
            """
        )
        self.db.execute(
            """
            UPDATE users
            SET avatar_path = REPLACE(avatar_path, 'web_app/static/uploads/', '')
            WHERE avatar_path LIKE 'web_app/static/uploads/%'
            """
        )
        self.db.execute(
            """
            UPDATE question_assets
            SET file_path = REPLACE(file_path, 'web_server/data_m/assets/', '')
            WHERE file_path LIKE 'web_server/data_m/assets/%'
            """
        )
        self.db.execute(
            """
            UPDATE users
            SET avatar_path = REPLACE(avatar_path, 'web_server/data_m/assets/', '')
            WHERE avatar_path LIKE 'web_server/data_m/assets/%'
            """
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
