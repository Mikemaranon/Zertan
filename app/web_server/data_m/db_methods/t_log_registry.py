import json


class LogRegistryTable:
    def __init__(self, db):
        self.db = db

    def create(
        self,
        *,
        action,
        entity_type,
        actor_user_id=None,
        actor_login_name="",
        actor_display_name="",
        actor_role="",
        exam_id=None,
        exam_code="",
        exam_title="",
        question_id=None,
        question_label="",
        question_type="",
        question_position=None,
        details="",
        before_snapshot=None,
        after_snapshot=None,
        before_content_text="",
        after_content_text="",
        diff_text="",
        scope_groups=None,
    ):
        log_id = self.db.execute_insert(
            """
            INSERT INTO log_registry_entries (
                action,
                entity_type,
                actor_user_id,
                actor_login_name,
                actor_display_name,
                actor_role,
                exam_id,
                exam_code,
                exam_title,
                question_id,
                question_label,
                question_type,
                question_position,
                details,
                before_snapshot_json,
                after_snapshot_json,
                before_content_text,
                after_content_text,
                diff_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action,
                entity_type,
                actor_user_id,
                actor_login_name,
                actor_display_name,
                actor_role,
                exam_id,
                exam_code,
                exam_title,
                question_id,
                question_label,
                question_type,
                question_position,
                details,
                self._dump(before_snapshot),
                self._dump(after_snapshot),
                before_content_text,
                after_content_text,
                diff_text,
            ),
        )
        normalized_groups = self._normalize_scope_groups(scope_groups)
        if normalized_groups:
            self.db.executemany(
                """
                INSERT INTO log_registry_scope_groups (log_id, group_id, group_code, group_name)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        log_id,
                        group["id"],
                        group["code"],
                        group["name"],
                    )
                    for group in normalized_groups
                ],
            )
        return log_id

    def list_entries(self, *, exam_id=None, group_id=None):
        join_clause = ""
        where_clauses = []
        params = []

        if group_id is not None:
            join_clause = "JOIN log_registry_scope_groups scope ON scope.log_id = l.id"
            where_clauses.append("scope.group_id = ?")
            params.append(group_id)
        if exam_id is not None:
            where_clauses.append("l.exam_id = ?")
            params.append(exam_id)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        _, rows = self.db.execute(
            f"""
            SELECT
                l.id,
                l.action,
                l.entity_type,
                l.actor_user_id,
                l.actor_login_name,
                l.actor_display_name,
                l.actor_role,
                l.exam_id,
                l.exam_code,
                l.exam_title,
                l.question_id,
                l.question_label,
                l.question_type,
                l.question_position,
                l.details,
                l.before_snapshot_json,
                l.after_snapshot_json,
                l.before_content_text,
                l.after_content_text,
                l.diff_text,
                l.created_at
            FROM log_registry_entries l
            {join_clause}
            {where_sql}
            ORDER BY l.id DESC
            """,
            tuple(params),
            fetchall=True,
        )
        return [self._row_to_entry(row) for row in rows]

    def summarize_by_exam_ids(self, exam_ids):
        normalized_exam_ids = self._normalize_ids(exam_ids)
        if not normalized_exam_ids:
            return {}
        placeholders = ",".join("?" for _ in normalized_exam_ids)
        _, rows = self.db.execute(
            f"""
            SELECT exam_id, COUNT(*) AS log_count, MAX(created_at) AS latest_log_at
            FROM log_registry_entries
            WHERE exam_id IN ({placeholders})
            GROUP BY exam_id
            """,
            tuple(normalized_exam_ids),
            fetchall=True,
        )
        return {
            row["exam_id"]: {
                "log_count": int(row["log_count"] or 0),
                "latest_log_at": row["latest_log_at"],
            }
            for row in rows
        }

    def delete_entries(self, *, exam_id=None, group_id=None):
        log_ids = self.list_entry_ids(exam_id=exam_id, group_id=group_id)
        if not log_ids:
            return 0
        placeholders = ",".join("?" for _ in log_ids)
        self.db.execute(
            f"DELETE FROM log_registry_entries WHERE id IN ({placeholders})",
            tuple(log_ids),
        )
        return len(log_ids)

    def list_entry_ids(self, *, exam_id=None, group_id=None):
        join_clause = ""
        where_clauses = []
        params = []

        if group_id is not None:
            join_clause = "JOIN log_registry_scope_groups scope ON scope.log_id = l.id"
            where_clauses.append("scope.group_id = ?")
            params.append(group_id)
        if exam_id is not None:
            where_clauses.append("l.exam_id = ?")
            params.append(exam_id)

        if not where_clauses:
            _, rows = self.db.execute(
                "SELECT id FROM log_registry_entries ORDER BY id DESC",
                fetchall=True,
            )
            return [row["id"] for row in rows]

        where_sql = "WHERE " + " AND ".join(where_clauses)
        _, rows = self.db.execute(
            f"""
            SELECT DISTINCT l.id
            FROM log_registry_entries l
            {join_clause}
            {where_sql}
            ORDER BY l.id DESC
            """,
            tuple(params),
            fetchall=True,
        )
        return [row["id"] for row in rows]

    def _row_to_entry(self, row):
        return {
            "id": row["id"],
            "action": row["action"],
            "entity_type": row["entity_type"],
            "actor": {
                "id": row["actor_user_id"],
                "login_name": row["actor_login_name"],
                "display_name": row["actor_display_name"],
                "role": row["actor_role"],
            },
            "exam": {
                "id": row["exam_id"],
                "code": row["exam_code"],
                "title": row["exam_title"],
            },
            "question": {
                "id": row["question_id"],
                "label": row["question_label"],
                "type": row["question_type"],
                "position": row["question_position"],
            },
            "details": row["details"] or "",
            "before_snapshot": self._load(row["before_snapshot_json"]),
            "after_snapshot": self._load(row["after_snapshot_json"]),
            "before_content_text": row["before_content_text"] or "",
            "after_content_text": row["after_content_text"] or "",
            "diff_text": row["diff_text"] or "",
            "created_at": row["created_at"],
            "scope_groups": self._scope_groups_for_log_id(row["id"]),
        }

    def _scope_groups_for_log_id(self, log_id):
        _, rows = self.db.execute(
            """
            SELECT group_id, group_code, group_name
            FROM log_registry_scope_groups
            WHERE log_id = ?
            ORDER BY lower(group_name), lower(group_code)
            """,
            (log_id,),
            fetchall=True,
        )
        return [
            {
                "id": row["group_id"],
                "code": row["group_code"],
                "name": row["group_name"],
            }
            for row in rows
        ]

    def _normalize_scope_groups(self, scope_groups):
        normalized = []
        seen = set()
        for group in scope_groups or []:
            try:
                group_id = int(group.get("id"))
            except (AttributeError, TypeError, ValueError):
                continue
            if group_id < 1 or group_id in seen:
                continue
            seen.add(group_id)
            normalized.append(
                {
                    "id": group_id,
                    "code": str(group.get("code") or "").strip(),
                    "name": str(group.get("name") or "").strip(),
                }
            )
        return normalized

    def _normalize_ids(self, values):
        normalized = []
        seen = set()
        for value in values or []:
            try:
                numeric = int(value)
            except (TypeError, ValueError):
                continue
            if numeric < 1 or numeric in seen:
                continue
            seen.add(numeric)
            normalized.append(numeric)
        return normalized

    def _dump(self, value):
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=True, sort_keys=True)

    def _load(self, value):
        if not value:
            return None
        return json.loads(value)
