# db_methods/t_exams.py

import json
from urllib.parse import urlparse


class ExamsTable:
    def __init__(self, db):
        self.db = db

    def list_all(self):
        _, rows = self.db.execute(
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
                COUNT(q.id) AS question_count
            FROM exams e
            LEFT JOIN questions q ON q.exam_id = e.id AND q.status != 'archived'
            GROUP BY e.id
            ORDER BY e.provider, e.code
            """,
            fetchall=True,
        )
        exams = []
        for row in rows:
            exam = {
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
                "question_count": row["question_count"],
                "tags": self.get_tags(row["id"]),
            }
            exams.append(exam)
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
                COUNT(q.id) AS question_count
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
        }

    def create(self, payload, created_by):
        normalized = self._normalize_payload(payload)
        self.db.execute(
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
        _, row = self.db.execute(
            "SELECT id FROM exams WHERE code = ?",
            (normalized["code"],),
            fetchone=True,
        )
        exam_id = row["id"]
        self.set_tags(exam_id, normalized.get("tags", []))
        return exam_id

    def update(self, exam_id, payload):
        normalized = self._normalize_payload(payload)
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

    def delete(self, exam_id):
        self.db.execute("DELETE FROM exams WHERE id = ?", (exam_id,))

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
        self.db.execute(f"INSERT INTO {table} (name) VALUES (?)", (value.strip(),))
        _, created = self.db.execute(
            f"SELECT id FROM {table} WHERE lower(name) = lower(?)",
            (value.strip(),),
            fetchone=True,
        )
        return created["id"]

    def _normalize_payload(self, payload):
        official_url = str(payload.get("official_url", "") or "").strip()
        if official_url:
            parsed = urlparse(official_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Official exam URL must be a valid http or https address.")

        return {
            "code": str(payload["code"]).strip(),
            "title": str(payload["title"]).strip(),
            "provider": str(payload["provider"]).strip(),
            "description": str(payload.get("description", "") or "").strip(),
            "official_url": official_url,
            "difficulty": str(payload.get("difficulty", "intermediate") or "intermediate").strip(),
            "status": str(payload.get("status", "draft") or "draft").strip(),
            "tags": [tag.strip() for tag in payload.get("tags", []) if str(tag).strip()],
        }
