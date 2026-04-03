# db_methods/t_exams.py

from ..utils import (
    normalize_exam_group_ids,
    normalize_exam_payload,
    validate_exam_scope_group_ids,
)


class ExamsTable:
    def __init__(self, db):
        self.db = db

    def list_all(self, user_id=None, is_administrator=False):
        params = []
        visibility_clause = ""
        if user_id is not None and not is_administrator:
            visibility_clause = """
            WHERE (
                NOT EXISTS (
                    SELECT 1
                    FROM exam_group_assignments scope
                    WHERE scope.exam_id = e.id
                )
                OR EXISTS (
                    SELECT 1
                    FROM exam_group_assignments scope
                    JOIN user_group_memberships membership ON membership.group_id = scope.group_id
                    WHERE scope.exam_id = e.id
                    AND membership.user_id = ?
                )
            )
            """
            params.append(user_id)

        _, rows = self.db.execute(
            f"""
            SELECT
                e.id,
                e.code,
                e.title,
                e.provider,
                e.description,
                e.official_url,
                e.difficulty,
                e.status,
                e.created_at,
                e.updated_at,
                e.created_by,
                COUNT(DISTINCT q.id) AS question_count
            FROM exams e
            LEFT JOIN questions q ON q.exam_id = e.id AND q.status != 'archived'
            {visibility_clause}
            GROUP BY e.id
            ORDER BY e.provider, e.code
            """,
            tuple(params),
            fetchall=True,
        )
        scope_groups_map = self._scope_groups_by_exam_ids([row["id"] for row in rows])
        exams = []
        for row in rows:
            exams.append(self._row_to_exam(row, scope_groups_map.get(row["id"], [])))
        return exams

    def get(self, exam_id):
        _, row = self.db.execute(
            """
            SELECT
                e.id,
                e.code,
                e.title,
                e.provider,
                e.description,
                e.official_url,
                e.difficulty,
                e.status,
                e.created_at,
                e.updated_at,
                e.created_by,
                COUNT(DISTINCT q.id) AS question_count
            FROM exams e
            LEFT JOIN questions q ON q.exam_id = e.id AND q.status != 'archived'
            WHERE e.id = ?
            GROUP BY e.id
            """,
            (exam_id,),
            fetchone=True,
        )
        if not row:
            return None
        scope_groups_map = self._scope_groups_by_exam_ids([exam_id])
        return self._row_to_exam(row, scope_groups_map.get(exam_id, []))

    def create(self, payload, created_by, allowed_group_ids=None, allow_global=True):
        normalized_group_ids = validate_exam_scope_group_ids(
            self.db,
            payload.get("group_ids", []),
            allowed_group_ids=allowed_group_ids,
            allow_global=allow_global,
        )
        normalized = normalize_exam_payload(payload, group_ids=normalized_group_ids)
        exam_id = self.db.execute_insert(
            """
            INSERT INTO exams (code, title, provider, description, official_url, difficulty, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized["code"],
                normalized["title"],
                normalized["provider"],
                normalized["description"],
                normalized["official_url"],
                normalized["difficulty"],
                normalized["status"],
                created_by,
            ),
        )
        self.set_tags(exam_id, normalized.get("tags", []))
        self.set_group_scope(exam_id, normalized.get("group_ids", []))
        return exam_id

    def update(self, exam_id, payload, allowed_group_ids=None, allow_global=True):
        normalized_group_ids = validate_exam_scope_group_ids(
            self.db,
            payload.get("group_ids", []),
            allowed_group_ids=allowed_group_ids,
            allow_global=allow_global,
        )
        normalized = normalize_exam_payload(payload, group_ids=normalized_group_ids)
        self.db.execute(
            """
            UPDATE exams
            SET code = ?, title = ?, provider = ?, description = ?, official_url = ?, difficulty = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                normalized["code"],
                normalized["title"],
                normalized["provider"],
                normalized["description"],
                normalized["official_url"],
                normalized["difficulty"],
                normalized["status"],
                exam_id,
            ),
        )
        self.set_tags(exam_id, normalized.get("tags", []))
        self.set_group_scope(exam_id, normalized.get("group_ids", []))

    def delete(self, exam_id):
        self.db.execute("DELETE FROM exams WHERE id = ?", (exam_id,))

    def set_group_scope(self, exam_id, group_ids):
        normalized_group_ids = normalize_exam_group_ids(group_ids)
        self.db.execute("DELETE FROM exam_group_assignments WHERE exam_id = ?", (exam_id,))
        if not normalized_group_ids:
            return
        self.db.executemany(
            """
            INSERT INTO exam_group_assignments (exam_id, group_id)
            VALUES (?, ?)
            """,
            [(exam_id, group_id) for group_id in normalized_group_ids],
        )

    def user_can_access(self, exam_id, user_id=None, is_administrator=False):
        if is_administrator:
            return True

        _, scope_row = self.db.execute(
            """
            SELECT COUNT(*) AS total
            FROM exam_group_assignments
            WHERE exam_id = ?
            """,
            (exam_id,),
            fetchone=True,
        )
        if not scope_row or int(scope_row["total"] or 0) == 0:
            return True
        if user_id is None:
            return False

        _, row = self.db.execute(
            """
            SELECT 1
            FROM exam_group_assignments scope
            JOIN user_group_memberships membership ON membership.group_id = scope.group_id
            WHERE scope.exam_id = ?
            AND membership.user_id = ?
            LIMIT 1
            """,
            (exam_id, user_id),
            fetchone=True,
        )
        return bool(row)

    def set_tags(self, exam_id, tags):
        self.db.execute("DELETE FROM exam_tags WHERE exam_id = ?", (exam_id,))
        for tag_name in tags:
            tag_id = self._get_or_create_named_value("tags", tag_name)
            self.db.execute(
                "INSERT OR IGNORE INTO exam_tags (exam_id, tag_id) VALUES (?, ?)",
                (exam_id, tag_id),
            )

    def get_tags(self, exam_id):
        _, rows = self.db.execute(
            """
            SELECT t.name
            FROM exam_tags et
            JOIN tags t ON t.id = et.tag_id
            WHERE et.exam_id = ?
            ORDER BY t.name
            """,
            (exam_id,),
            fetchall=True,
        )
        return [row["name"] for row in rows]

    def list_builder_metadata(self, exam_id):
        _, types = self.db.execute(
            """
            SELECT DISTINCT type
            FROM questions
            WHERE exam_id = ? AND status = 'active'
            ORDER BY type
            """,
            (exam_id,),
            fetchall=True,
        )
        _, tags = self.db.execute(
            """
            SELECT DISTINCT t.name
            FROM question_tags qt
            JOIN tags t ON t.id = qt.tag_id
            JOIN questions q ON q.id = qt.question_id
            WHERE q.exam_id = ? AND q.status = 'active'
            ORDER BY t.name
            """,
            (exam_id,),
            fetchall=True,
        )
        _, topics = self.db.execute(
            """
            SELECT DISTINCT t.name
            FROM question_topics qt
            JOIN topics t ON t.id = qt.topic_id
            JOIN questions q ON q.id = qt.question_id
            WHERE q.exam_id = ? AND q.status = 'active'
            ORDER BY t.name
            """,
            (exam_id,),
            fetchall=True,
        )
        return {
            "question_types": [row["type"] for row in types],
            "tags": [row["name"] for row in tags],
            "topics": [row["name"] for row in topics],
        }

    def _get_or_create_named_value(self, table, value):
        _, row = self.db.execute(
            f"SELECT id FROM {table} WHERE lower(name) = lower(?)",
            (value.strip(),),
            fetchone=True,
        )
        if row:
            return row["id"]
        return self.db.execute_insert(f"INSERT INTO {table} (name) VALUES (?)", (value.strip(),))

    def _scope_groups_by_exam_ids(self, exam_ids):
        if not exam_ids:
            return {}
        _, rows = self.db.execute(
            f"""
            SELECT
                assignment.exam_id,
                g.id,
                g.code,
                g.name,
                g.status
            FROM exam_group_assignments assignment
            JOIN user_groups g ON g.id = assignment.group_id
            WHERE assignment.exam_id IN ({",".join("?" for _ in exam_ids)})
            ORDER BY lower(g.name), lower(g.code)
            """,
            tuple(exam_ids),
            fetchall=True,
        )
        groups_map = {exam_id: [] for exam_id in exam_ids}
        for row in rows:
            groups_map.setdefault(row["exam_id"], []).append(
                {
                    "id": row["id"],
                    "code": row["code"],
                    "name": row["name"],
                    "status": row["status"],
                }
            )
        return groups_map

    def _row_to_exam(self, row, scope_groups):
        return {
            "id": row["id"],
            "code": row["code"],
            "title": row["title"],
            "provider": row["provider"],
            "description": row["description"],
            "official_url": row["official_url"],
            "difficulty": row["difficulty"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "created_by": row["created_by"],
            "question_count": row["question_count"],
            "tags": self.get_tags(row["id"]),
            "scope_groups": scope_groups,
            "group_ids": [group["id"] for group in scope_groups],
            "scope_mode": "global" if not scope_groups else "groups",
            "is_global_scope": not scope_groups,
        }
