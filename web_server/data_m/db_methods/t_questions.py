# db_methods/t_questions.py

import json


class QuestionsTable:
    def __init__(self, db):
        self.db = db

    def list_for_exam(self, exam_id, include_answers=True, include_archived=False):
        query = """
            SELECT id
            FROM questions
            WHERE exam_id = ?
        """
        params = [exam_id]
        if not include_archived:
            query += " AND status != 'archived'"
        query += " ORDER BY position, id"
        _, rows = self.db.execute(query, params, fetchall=True)
        return [self.get(row["id"], include_answers=include_answers) for row in rows]

    def list_filtered_ids(self, exam_id, filters):
        query = """
            SELECT DISTINCT q.id
            FROM questions q
            LEFT JOIN question_tags qt ON qt.question_id = q.id
            LEFT JOIN tags t ON t.id = qt.tag_id
            LEFT JOIN question_topics qtp ON qtp.question_id = q.id
            LEFT JOIN topics tp ON tp.id = qtp.topic_id
            WHERE q.exam_id = ? AND q.status = 'active'
        """
        params = [exam_id]
        question_types = filters.get("question_types") or []
        tags = filters.get("tags") or []
        topics = filters.get("topics") or []
        difficulty = filters.get("difficulty")

        if question_types:
            placeholders = ",".join(["?"] * len(question_types))
            query += f" AND q.type IN ({placeholders})"
            params.extend(question_types)
        if tags:
            placeholders = ",".join(["?"] * len(tags))
            query += f" AND t.name IN ({placeholders})"
            params.extend(tags)
        if topics:
            placeholders = ",".join(["?"] * len(topics))
            query += f" AND tp.name IN ({placeholders})"
            params.extend(topics)
        if difficulty:
            query += " AND q.difficulty = ?"
            params.append(difficulty)

        query += " ORDER BY q.position, q.id"
        _, rows = self.db.execute(query, params, fetchall=True)
        return [row["id"] for row in rows]

    def get(self, question_id, include_answers=True):
        _, row = self.db.execute(
            """
            SELECT
                id, exam_id, type, title, statement, explanation, difficulty, status,
                position, config_json, source_json_path, created_at, updated_at, archived_at
            FROM questions
            WHERE id = ?
            """,
            (question_id,),
            fetchone=True,
        )
        if not row:
            return None

        question = {
            "id": row["id"],
            "exam_id": row["exam_id"],
            "type": row["type"],
            "title": row["title"],
            "statement": row["statement"],
            "explanation": row["explanation"],
            "difficulty": row["difficulty"],
            "status": row["status"],
            "position": row["position"],
            "config": json.loads(row["config_json"] or "{}"),
            "source_json_path": row["source_json_path"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "archived_at": row["archived_at"],
            "options": self._get_options(question_id, include_answers=include_answers),
            "assets": self._get_assets(question_id),
            "tags": self._get_names("question_tags", "tag_id", "tags", question_id),
            "topics": self._get_names("question_topics", "topic_id", "topics", question_id),
        }
        return question

    def create(self, exam_id, payload):
        position = payload.get("position")
        if position is None:
            _, row = self.db.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 AS next_position FROM questions WHERE exam_id = ?",
                (exam_id,),
                fetchone=True,
            )
            position = row["next_position"]

        self.db.execute(
            """
            INSERT INTO questions (
                exam_id, type, title, statement, explanation, difficulty, status, position, config_json, source_json_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exam_id,
                payload["type"],
                payload.get("title", ""),
                payload["statement"],
                payload.get("explanation", ""),
                payload.get("difficulty", "intermediate"),
                payload.get("status", "active"),
                position,
                json.dumps(payload.get("config", {})),
                payload.get("source_json_path"),
            ),
        )
        _, row = self.db.execute(
            """
            SELECT id
            FROM questions
            WHERE exam_id = ? AND position = ?
            ORDER BY id DESC LIMIT 1
            """,
            (exam_id, position),
            fetchone=True,
        )
        question_id = row["id"]
        self._replace_options(question_id, payload.get("options", []))
        self._replace_assets(question_id, payload.get("assets", []))
        self._replace_named_relations(question_id, "question_tags", "tag_id", "tags", payload.get("tags", []))
        self._replace_named_relations(question_id, "question_topics", "topic_id", "topics", payload.get("topics", []))
        return question_id

    def update(self, question_id, payload):
        self.db.execute(
            """
            UPDATE questions
            SET
                type = ?,
                title = ?,
                statement = ?,
                explanation = ?,
                difficulty = ?,
                status = ?,
                position = ?,
                config_json = ?,
                source_json_path = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                payload["type"],
                payload.get("title", ""),
                payload["statement"],
                payload.get("explanation", ""),
                payload.get("difficulty", "intermediate"),
                payload.get("status", "active"),
                payload.get("position", 0),
                json.dumps(payload.get("config", {})),
                payload.get("source_json_path"),
                question_id,
            ),
        )
        self._replace_options(question_id, payload.get("options", []))
        self._replace_assets(question_id, payload.get("assets", []))
        self._replace_named_relations(question_id, "question_tags", "tag_id", "tags", payload.get("tags", []))
        self._replace_named_relations(question_id, "question_topics", "topic_id", "topics", payload.get("topics", []))

    def archive(self, question_id):
        self.db.execute(
            """
            UPDATE questions
            SET status = 'archived', archived_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (question_id,),
        )

    def delete(self, question_id):
        self.db.execute("DELETE FROM questions WHERE id = ?", (question_id,))

    def _get_options(self, question_id, include_answers):
        _, rows = self.db.execute(
            """
            SELECT option_key, option_text, is_correct, sort_order
            FROM question_options
            WHERE question_id = ?
            ORDER BY sort_order, id
            """,
            (question_id,),
            fetchall=True,
        )
        options = []
        for row in rows:
            item = {
                "key": row["option_key"],
                "text": row["option_text"],
                "sort_order": row["sort_order"],
            }
            if include_answers:
                item["is_correct"] = bool(row["is_correct"])
            options.append(item)
        return options

    def _get_assets(self, question_id):
        _, rows = self.db.execute(
            """
            SELECT id, asset_type, file_path, meta_json, created_at
            FROM question_assets
            WHERE question_id = ?
            ORDER BY id
            """,
            (question_id,),
            fetchall=True,
        )
        return [
            {
                "id": row["id"],
                "asset_type": row["asset_type"],
                "file_path": row["file_path"],
                "meta": json.loads(row["meta_json"] or "{}"),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def _replace_options(self, question_id, options):
        self.db.execute("DELETE FROM question_options WHERE question_id = ?", (question_id,))
        if not options:
            return
        rows = [
            (
                question_id,
                option["key"],
                option["text"],
                1 if option.get("is_correct") else 0,
                index,
            )
            for index, option in enumerate(options, start=1)
        ]
        self.db.executemany(
            """
            INSERT INTO question_options (question_id, option_key, option_text, is_correct, sort_order)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )

    def _replace_assets(self, question_id, assets):
        self.db.execute("DELETE FROM question_assets WHERE question_id = ?", (question_id,))
        if not assets:
            return
        rows = [
            (
                question_id,
                asset["asset_type"],
                asset["file_path"],
                json.dumps(asset.get("meta", {})),
            )
            for asset in assets
        ]
        self.db.executemany(
            """
            INSERT INTO question_assets (question_id, asset_type, file_path, meta_json)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )

    def _replace_named_relations(self, question_id, relation_table, relation_key, value_table, values):
        self.db.execute(f"DELETE FROM {relation_table} WHERE question_id = ?", (question_id,))
        for value in values:
            value_id = self._get_or_create_named_value(value_table, value)
            self.db.execute(
                f"INSERT OR IGNORE INTO {relation_table} (question_id, {relation_key}) VALUES (?, ?)",
                (question_id, value_id),
            )

    def _get_or_create_named_value(self, table, value):
        clean_value = value.strip()
        _, row = self.db.execute(
            f"SELECT id FROM {table} WHERE lower(name) = lower(?)",
            (clean_value,),
            fetchone=True,
        )
        if row:
            return row["id"]
        self.db.execute(f"INSERT INTO {table} (name) VALUES (?)", (clean_value,))
        _, row = self.db.execute(
            f"SELECT id FROM {table} WHERE lower(name) = lower(?)",
            (clean_value,),
            fetchone=True,
        )
        return row["id"]

    def _get_names(self, relation_table, relation_key, value_table, question_id):
        _, rows = self.db.execute(
            f"""
            SELECT v.name
            FROM {relation_table} r
            JOIN {value_table} v ON v.id = r.{relation_key}
            WHERE r.question_id = ?
            ORDER BY v.name
            """,
            (question_id,),
            fetchall=True,
        )
        return [row["name"] for row in rows]
