# db_methods/t_attempts.py

import json


class AttemptsTable:
    def __init__(self, db):
        self.db = db

    def create(self, exam_id, user_id, criteria, question_count, random_order=True, time_limit_minutes=None):
        return self.db.execute_insert(
            """
            INSERT INTO exam_attempts (
                exam_id, user_id, status, criteria_json, question_count, random_order, time_limit_minutes
            ) VALUES (?, ?, 'in_progress', ?, ?, ?, ?)
            """,
            (
                exam_id,
                user_id,
                json.dumps(criteria or {}),
                question_count,
                1 if random_order else 0,
                time_limit_minutes,
            ),
        )

    def add_questions(self, attempt_id, question_snapshots):
        rows = []
        for index, snapshot in enumerate(question_snapshots, start=1):
            rows.append(
                (
                    attempt_id,
                    snapshot["question_id"],
                    index,
                    ((index - 1) // 5) + 1,
                    json.dumps(snapshot["snapshot"]),
                )
            )
        self.db.executemany(
            """
            INSERT INTO exam_attempt_questions (
                attempt_id, question_id, question_order, page_number, snapshot_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        _, stored = self.db.execute(
            """
            SELECT id, attempt_id, question_id
            FROM exam_attempt_questions
            WHERE attempt_id = ?
            ORDER BY question_order
            """,
            (attempt_id,),
            fetchall=True,
        )
        self.db.executemany(
            """
            INSERT INTO exam_answers (attempt_question_id, attempt_id, question_id, omitted)
            VALUES (?, ?, ?, 1)
            """,
            [(row["id"], row["attempt_id"], row["question_id"]) for row in stored],
        )

    def get_attempt(self, attempt_id):
        _, row = self.db.execute(
            """
            SELECT
                a.id,
                a.exam_id,
                a.user_id,
                a.status,
                a.criteria_json,
                a.question_count,
                a.random_order,
                a.time_limit_minutes,
                a.started_at,
                a.submitted_at,
                a.duration_seconds,
                a.score_percent,
                a.correct_count,
                a.incorrect_count,
                a.omitted_count,
                e.code AS exam_code,
                e.title AS exam_title
            FROM exam_attempts a
            JOIN exams e ON e.id = a.exam_id
            WHERE a.id = ?
            """,
            (attempt_id,),
            fetchone=True,
        )
        if not row:
            return None
        return {
            "id": row["id"],
            "exam_id": row["exam_id"],
            "user_id": row["user_id"],
            "status": row["status"],
            "criteria": json.loads(row["criteria_json"] or "{}"),
            "question_count": row["question_count"],
            "random_order": bool(row["random_order"]),
            "time_limit_minutes": row["time_limit_minutes"],
            "started_at": row["started_at"],
            "submitted_at": row["submitted_at"],
            "duration_seconds": row["duration_seconds"],
            "score_percent": row["score_percent"],
            "correct_count": row["correct_count"],
            "incorrect_count": row["incorrect_count"],
            "omitted_count": row["omitted_count"],
            "exam_code": row["exam_code"],
            "exam_title": row["exam_title"],
        }

    def get_attempt_questions(self, attempt_id, page_number=None):
        query = """
            SELECT
                aq.id,
                aq.question_id,
                aq.question_order,
                aq.page_number,
                aq.snapshot_json,
                ans.response_json,
                ans.is_correct,
                ans.omitted,
                ans.score,
                ans.answered_at
            FROM exam_attempt_questions aq
            LEFT JOIN exam_answers ans ON ans.attempt_question_id = aq.id
            WHERE aq.attempt_id = ?
        """
        params = [attempt_id]
        if page_number is not None:
            query += " AND aq.page_number = ?"
            params.append(page_number)
        query += " ORDER BY aq.question_order"

        _, rows = self.db.execute(
            query,
            tuple(params),
            fetchall=True,
        )
        payload = []
        for row in rows:
            payload.append(
                {
                    "attempt_question_id": row["id"],
                    "question_id": row["question_id"],
                    "question_order": row["question_order"],
                    "page_number": row["page_number"],
                    "snapshot": json.loads(row["snapshot_json"]),
                    "response": json.loads(row["response_json"]) if row["response_json"] else None,
                    "is_correct": None if row["is_correct"] is None else bool(row["is_correct"]),
                    "omitted": bool(row["omitted"]),
                    "score": row["score"],
                    "answered_at": row["answered_at"],
                }
            )
        return payload

    def save_response(self, attempt_question_id, attempt_id, question_id, response, omitted):
        self.db.execute(
            """
            UPDATE exam_answers
            SET response_json = ?, omitted = ?, answered_at = CURRENT_TIMESTAMP
            WHERE attempt_question_id = ? AND attempt_id = ? AND question_id = ?
            """,
            (
                json.dumps(response) if response is not None else None,
                1 if omitted else 0,
                attempt_question_id,
                attempt_id,
                question_id,
            ),
        )

    def finalize_answer(self, attempt_question_id, is_correct, score, omitted):
        self.db.execute(
            """
            UPDATE exam_answers
            SET is_correct = ?, score = ?, omitted = ?, answered_at = COALESCE(answered_at, CURRENT_TIMESTAMP)
            WHERE attempt_question_id = ?
            """,
            (1 if is_correct else 0, score, 1 if omitted else 0, attempt_question_id),
        )

    def mark_submitted(self, attempt_id, correct_count, incorrect_count, omitted_count, score_percent):
        self.db.execute(
            """
            UPDATE exam_attempts
            SET
                status = 'submitted',
                submitted_at = CURRENT_TIMESTAMP,
                duration_seconds = CAST((julianday(CURRENT_TIMESTAMP) - julianday(started_at)) * 86400 AS INTEGER),
                correct_count = ?,
                incorrect_count = ?,
                omitted_count = ?,
                score_percent = ?
            WHERE id = ?
            """,
            (correct_count, incorrect_count, omitted_count, score_percent, attempt_id),
        )

    def list_recent_for_user(self, user_id, limit=4):
        _, rows = self.db.execute(
            """
            SELECT
                a.id,
                a.exam_id,
                a.status,
                a.started_at,
                a.submitted_at,
                a.score_percent,
                e.code,
                e.title
            FROM exam_attempts a
            JOIN exams e ON e.id = a.exam_id
            WHERE a.user_id = ?
            ORDER BY a.id DESC
            LIMIT ?
            """,
            (user_id, limit),
            fetchall=True,
        )
        return [
            {
                "id": row["id"],
                "exam_id": row["exam_id"],
                "status": row["status"],
                "started_at": row["started_at"],
                "submitted_at": row["submitted_at"],
                "score_percent": row["score_percent"],
                "exam_code": row["code"],
                "exam_title": row["title"],
            }
            for row in rows
        ]

    def delete(self, attempt_id):
        self.db.execute("DELETE FROM exam_attempts WHERE id = ?", (attempt_id,))
