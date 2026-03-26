# db_methods/t_questions.py

import json


class QuestionsTable:
    def __init__(self, db):
        self.db = db

    def list_for_exam(self, exam_id, include_answers=True, include_archived=False):
        query = self._base_question_select_query()
        query += """
            WHERE q.exam_id = ?
        """
        params = [exam_id]
        if not include_archived:
            query += " AND q.status != 'archived'"
        query += " ORDER BY q.position, q.id"
        _, rows = self.db.execute(query, params, fetchall=True)
        return self._hydrate_question_rows(rows, include_answers=include_answers)

    def get_many(self, question_ids, include_answers=True):
        normalized_question_ids = self._normalize_question_ids(question_ids)
        if not normalized_question_ids:
            return []

        placeholders = ",".join("?" for _ in normalized_question_ids)
        _, rows = self.db.execute(
            f"""
            {self._base_question_select_query()}
            WHERE q.id IN ({placeholders})
            """,
            tuple(normalized_question_ids),
            fetchall=True,
        )
        hydrated = self._hydrate_question_rows(rows, include_answers=include_answers)
        questions_by_id = {question["id"]: question for question in hydrated}
        return [questions_by_id[question_id] for question_id in normalized_question_ids if question_id in questions_by_id]

    def list_filtered_ids(self, exam_id, filters):
        query = """
            SELECT q.id
            FROM questions q
            WHERE q.exam_id = ? AND q.status = 'active'
        """
        params = [exam_id]
        question_types = self._normalize_filter_group(filters.get("question_types"))
        tags = self._normalize_filter_group(filters.get("tags"))
        topics = self._normalize_filter_group(filters.get("topics"))
        difficulty = filters.get("difficulty")

        if question_types["include"]:
            placeholders = ",".join(["?"] * len(question_types["include"]))
            query += f" AND q.type IN ({placeholders})"
            params.extend(question_types["include"])
        if question_types["exclude"]:
            placeholders = ",".join(["?"] * len(question_types["exclude"]))
            query += f" AND q.type NOT IN ({placeholders})"
            params.extend(question_types["exclude"])
        if tags["include"]:
            placeholders = ",".join(["?"] * len(tags["include"]))
            query += f"""
                AND EXISTS (
                    SELECT 1
                    FROM question_tags qt
                    JOIN tags t ON t.id = qt.tag_id
                    WHERE qt.question_id = q.id AND t.name IN ({placeholders})
                )
            """
            params.extend(tags["include"])
        if tags["exclude"]:
            placeholders = ",".join(["?"] * len(tags["exclude"]))
            query += f"""
                AND NOT EXISTS (
                    SELECT 1
                    FROM question_tags qt
                    JOIN tags t ON t.id = qt.tag_id
                    WHERE qt.question_id = q.id AND t.name IN ({placeholders})
                )
            """
            params.extend(tags["exclude"])
        if topics["include"]:
            placeholders = ",".join(["?"] * len(topics["include"]))
            query += f"""
                AND EXISTS (
                    SELECT 1
                    FROM question_topics qt
                    JOIN topics tp ON tp.id = qt.topic_id
                    WHERE qt.question_id = q.id AND tp.name IN ({placeholders})
                )
            """
            params.extend(topics["include"])
        if topics["exclude"]:
            placeholders = ",".join(["?"] * len(topics["exclude"]))
            query += f"""
                AND NOT EXISTS (
                    SELECT 1
                    FROM question_topics qt
                    JOIN topics tp ON tp.id = qt.topic_id
                    WHERE qt.question_id = q.id AND tp.name IN ({placeholders})
                )
            """
            params.extend(topics["exclude"])
        if difficulty:
            query += " AND q.difficulty = ?"
            params.append(difficulty)

        query += " ORDER BY q.position, q.id"
        _, rows = self.db.execute(query, params, fetchall=True)
        return [row["id"] for row in rows]

    def _normalize_filter_group(self, value):
        if isinstance(value, list):
            include = value
            exclude = []
        else:
            include = (value or {}).get("include") or []
            exclude = (value or {}).get("exclude") or []
        include = [item for item in include if str(item).strip()]
        exclude = [item for item in exclude if str(item).strip() and item not in include]
        return {
            "include": include,
            "exclude": exclude,
        }

    def get(self, question_id, include_answers=True):
        questions = self.get_many([question_id], include_answers=include_answers)
        return questions[0] if questions else None

    def create(self, exam_id, payload):
        position = self._normalize_requested_position(payload.get("position"))
        if position is None:
            position = self._next_position_for_exam(exam_id)

        question_id = self.db.execute_insert(
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
        self._replace_options(question_id, payload.get("options", []))
        self._replace_assets(question_id, payload.get("assets", []))
        self._replace_named_relations(question_id, "question_tags", "tag_id", "tags", payload.get("tags", []))
        self._replace_named_relations(question_id, "question_topics", "topic_id", "topics", payload.get("topics", []))
        self._resequence_exam_questions(
            exam_id,
            anchor_question_id=question_id,
            requested_position=position,
        )
        return question_id

    def update(self, question_id, payload):
        current = self.get(question_id, include_answers=True)
        if not current:
            return
        requested_position = self._normalize_requested_position(payload.get("position"))
        if requested_position is None:
            requested_position = current.get("position") or self._next_position_for_exam(current["exam_id"])

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
                requested_position,
                json.dumps(payload.get("config", {})),
                payload.get("source_json_path"),
                question_id,
            ),
        )
        self._replace_options(question_id, payload.get("options", []))
        self._replace_assets(question_id, payload.get("assets", []))
        self._replace_named_relations(question_id, "question_tags", "tag_id", "tags", payload.get("tags", []))
        self._replace_named_relations(question_id, "question_topics", "topic_id", "topics", payload.get("topics", []))
        self._resequence_exam_questions(
            current["exam_id"],
            anchor_question_id=question_id,
            requested_position=requested_position,
        )

    def archive(self, question_id):
        _, row = self.db.execute(
            "SELECT exam_id FROM questions WHERE id = ?",
            (question_id,),
            fetchone=True,
        )
        if not row:
            return
        self.db.execute(
            """
            UPDATE questions
            SET status = 'archived', archived_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (question_id,),
        )
        self._resequence_exam_questions(row["exam_id"], anchor_question_id=question_id)

    def delete(self, question_id):
        _, row = self.db.execute(
            "SELECT exam_id FROM questions WHERE id = ?",
            (question_id,),
            fetchone=True,
        )
        if not row:
            return
        self.db.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        self.normalize_positions_for_exam(row["exam_id"])

    def normalize_positions_for_exam(self, exam_id):
        _, rows = self.db.execute(
            """
            SELECT id
            FROM questions
            WHERE exam_id = ?
            ORDER BY
                CASE WHEN status = 'archived' THEN 1 ELSE 0 END,
                position,
                id
            """,
            (exam_id,),
            fetchall=True,
        )
        for index, row in enumerate(rows, start=1):
            self.db.execute(
                """
                UPDATE questions
                SET position = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (index, row["id"]),
            )

    def normalize_all_positions(self):
        _, rows = self.db.execute(
            """
            SELECT id
            FROM exams
            ORDER BY id
            """,
            fetchall=True,
        )
        for row in rows:
            self.normalize_positions_for_exam(row["id"])

    def _get_options(self, question_id, include_answers):
        return self._get_options_by_question_ids([question_id], include_answers=include_answers).get(question_id, [])

    def _get_assets(self, question_id):
        return self._get_assets_by_question_ids([question_id]).get(question_id, [])

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
        return self.db.execute_insert(f"INSERT INTO {table} (name) VALUES (?)", (clean_value,))

    def _get_names(self, relation_table, relation_key, value_table, question_id):
        return self._get_names_by_question_ids(relation_table, relation_key, value_table, [question_id]).get(question_id, [])

    def _base_question_select_query(self):
        return """
            SELECT
                q.id,
                q.exam_id,
                q.type,
                q.title,
                q.statement,
                q.explanation,
                q.difficulty,
                q.status,
                q.position,
                q.config_json,
                q.source_json_path,
                q.created_at,
                q.updated_at,
                q.archived_at
            FROM questions q
        """

    def _normalize_question_ids(self, question_ids):
        normalized = []
        seen = set()
        for value in question_ids or []:
            try:
                question_id = int(value)
            except (TypeError, ValueError):
                continue
            if question_id < 1 or question_id in seen:
                continue
            seen.add(question_id)
            normalized.append(question_id)
        return normalized

    def _normalize_requested_position(self, value):
        try:
            position = int(value)
        except (TypeError, ValueError):
            return None
        return max(1, position)

    def _next_position_for_exam(self, exam_id):
        _, row = self.db.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 AS next_position FROM questions WHERE exam_id = ?",
            (exam_id,),
            fetchone=True,
        )
        return row["next_position"]

    def _resequence_exam_questions(self, exam_id, anchor_question_id=None, requested_position=None):
        _, rows = self.db.execute(
            """
            SELECT id, status, position
            FROM questions
            WHERE exam_id = ?
            ORDER BY position, id
            """,
            (exam_id,),
            fetchall=True,
        )
        if not rows:
            return

        active_ids = []
        archived_ids = []
        anchor_row = None
        for row in rows:
            if anchor_question_id is not None and row["id"] == anchor_question_id:
                anchor_row = row
                continue
            if row["status"] == "archived":
                archived_ids.append(row["id"])
            else:
                active_ids.append(row["id"])

        if anchor_row is not None:
            if anchor_row["status"] == "archived":
                archived_ids.append(anchor_row["id"])
            else:
                target_index = max(0, min((requested_position or 1) - 1, len(active_ids)))
                active_ids.insert(target_index, anchor_row["id"])

        ordered_ids = active_ids + archived_ids
        for index, question_id in enumerate(ordered_ids, start=1):
            self.db.execute(
                """
                UPDATE questions
                SET position = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (index, question_id),
            )

    def _hydrate_question_rows(self, rows, include_answers):
        if not rows:
            return []

        question_ids = [row["id"] for row in rows]
        options_map = self._get_options_by_question_ids(question_ids, include_answers=include_answers)
        assets_map = self._get_assets_by_question_ids(question_ids)
        tags_map = self._get_names_by_question_ids("question_tags", "tag_id", "tags", question_ids)
        topics_map = self._get_names_by_question_ids("question_topics", "topic_id", "topics", question_ids)

        questions = []
        for row in rows:
            question_id = row["id"]
            questions.append(
                {
                    "id": question_id,
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
                    "options": options_map.get(question_id, []),
                    "assets": assets_map.get(question_id, []),
                    "tags": tags_map.get(question_id, []),
                    "topics": topics_map.get(question_id, []),
                }
            )
        return questions

    def _get_options_by_question_ids(self, question_ids, include_answers):
        normalized_question_ids = self._normalize_question_ids(question_ids)
        if not normalized_question_ids:
            return {}

        placeholders = ",".join("?" for _ in normalized_question_ids)
        _, rows = self.db.execute(
            f"""
            SELECT question_id, option_key, option_text, is_correct, sort_order
            FROM question_options
            WHERE question_id IN ({placeholders})
            ORDER BY question_id, sort_order, id
            """,
            tuple(normalized_question_ids),
            fetchall=True,
        )
        options_map = {question_id: [] for question_id in normalized_question_ids}
        for row in rows:
            item = {
                "key": row["option_key"],
                "text": row["option_text"],
                "sort_order": row["sort_order"],
            }
            if include_answers:
                item["is_correct"] = bool(row["is_correct"])
            options_map.setdefault(row["question_id"], []).append(item)
        return options_map

    def _get_assets_by_question_ids(self, question_ids):
        normalized_question_ids = self._normalize_question_ids(question_ids)
        if not normalized_question_ids:
            return {}

        placeholders = ",".join("?" for _ in normalized_question_ids)
        _, rows = self.db.execute(
            f"""
            SELECT question_id, id, asset_type, file_path, meta_json, created_at
            FROM question_assets
            WHERE question_id IN ({placeholders})
            ORDER BY question_id, id
            """,
            tuple(normalized_question_ids),
            fetchall=True,
        )
        assets_map = {question_id: [] for question_id in normalized_question_ids}
        for row in rows:
            assets_map.setdefault(row["question_id"], []).append(
                {
                    "id": row["id"],
                    "asset_type": row["asset_type"],
                    "file_path": row["file_path"],
                    "meta": json.loads(row["meta_json"] or "{}"),
                    "created_at": row["created_at"],
                }
            )
        return assets_map

    def _get_names_by_question_ids(self, relation_table, relation_key, value_table, question_ids):
        normalized_question_ids = self._normalize_question_ids(question_ids)
        if not normalized_question_ids:
            return {}

        placeholders = ",".join("?" for _ in normalized_question_ids)
        _, rows = self.db.execute(
            f"""
            SELECT r.question_id, v.name
            FROM {relation_table} r
            JOIN {value_table} v ON v.id = r.{relation_key}
            WHERE r.question_id IN ({placeholders})
            ORDER BY r.question_id, v.name
            """,
            tuple(normalized_question_ids),
            fetchall=True,
        )
        names_map = {question_id: [] for question_id in normalized_question_ids}
        for row in rows:
            names_map.setdefault(row["question_id"], []).append(row["name"])
        return names_map
