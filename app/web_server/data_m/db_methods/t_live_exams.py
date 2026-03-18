# db_methods/t_live_exams.py

import json


class LiveExamsTable:
    def __init__(self, db):
        self.db = db

    def create(self, payload, created_by):
        self.db.execute(
            """
            INSERT INTO live_exams (
                exam_id, title, description, instructions, status, question_count, time_limit_minutes, criteria_json, created_by
            ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?)
            """,
            (
                payload["exam_id"],
                payload["title"],
                payload.get("description", ""),
                payload.get("instructions", ""),
                payload["question_count"],
                payload.get("time_limit_minutes"),
                json.dumps(payload.get("criteria", {})),
                created_by,
            ),
        )
        _, row = self.db.execute(
            """
            SELECT id
            FROM live_exams
            ORDER BY id DESC
            LIMIT 1
            """,
            fetchone=True,
        )
        return row["id"]

    def set_assignments(self, live_exam_id, user_ids):
        self.db.execute("DELETE FROM live_exam_assignments WHERE live_exam_id = ?", (live_exam_id,))
        if not user_ids:
            return
        self.db.executemany(
            """
            INSERT INTO live_exam_assignments (live_exam_id, user_id, assignment_status)
            VALUES (?, ?, 'pending')
            """,
            [(live_exam_id, user_id) for user_id in user_ids],
        )

    def get(self, live_exam_id):
        _, row = self.db.execute(
            """
            SELECT
                le.id,
                le.exam_id,
                le.title,
                le.description,
                le.instructions,
                le.status,
                le.question_count,
                le.time_limit_minutes,
                le.criteria_json,
                le.created_by,
                le.created_at,
                le.updated_at,
                le.closed_at,
                e.code AS exam_code,
                e.title AS exam_title,
                e.provider AS exam_provider,
                u.display_name AS created_by_name
            FROM live_exams le
            JOIN exams e ON e.id = le.exam_id
            LEFT JOIN users u ON u.id = le.created_by
            WHERE le.id = ?
            """,
            (live_exam_id,),
            fetchone=True,
        )
        if not row:
            return None
        live_exam = self._row_to_live_exam(row)
        live_exam["assignments"] = self.list_assignments(live_exam_id)
        live_exam["counts"] = self._summarize_assignments(live_exam["assignments"])
        return live_exam

    def list_for_admin(self):
        _, rows = self.db.execute(
            """
            SELECT
                le.id,
                le.exam_id,
                le.title,
                le.description,
                le.instructions,
                le.status,
                le.question_count,
                le.time_limit_minutes,
                le.criteria_json,
                le.created_by,
                le.created_at,
                le.updated_at,
                le.closed_at,
                e.code AS exam_code,
                e.title AS exam_title,
                e.provider AS exam_provider,
                u.display_name AS created_by_name
            FROM live_exams le
            JOIN exams e ON e.id = le.exam_id
            LEFT JOIN users u ON u.id = le.created_by
            WHERE le.status = 'active'
            ORDER BY datetime(le.created_at) DESC, le.id DESC
            """,
            fetchall=True,
        )
        payload = []
        for row in rows:
            live_exam = self._row_to_live_exam(row)
            live_exam["assignments"] = self.list_assignments(live_exam["id"])
            live_exam["counts"] = self._summarize_assignments(live_exam["assignments"])
            payload.append(live_exam)
        return payload

    def list_for_user(self, user_id):
        _, rows = self.db.execute(
            """
            SELECT
                la.id AS assignment_id,
                la.live_exam_id,
                la.user_id,
                la.attempt_id,
                la.assignment_status,
                la.assigned_at,
                la.started_at AS assignment_started_at,
                la.completed_at,
                le.title AS live_exam_title,
                le.description AS live_exam_description,
                le.instructions AS live_exam_instructions,
                le.status AS live_exam_status,
                le.question_count,
                le.time_limit_minutes,
                le.criteria_json,
                le.created_at AS live_exam_created_at,
                e.id AS exam_id,
                e.code AS exam_code,
                e.title AS exam_title,
                e.provider AS exam_provider,
                a.status AS attempt_status,
                a.started_at AS attempt_started_at,
                a.submitted_at AS attempt_submitted_at,
                a.score_percent
            FROM live_exam_assignments la
            JOIN live_exams le ON le.id = la.live_exam_id
            JOIN exams e ON e.id = le.exam_id
            LEFT JOIN exam_attempts a ON a.id = la.attempt_id
            WHERE la.user_id = ? AND le.status = 'active'
            ORDER BY
                CASE la.assignment_status
                    WHEN 'pending' THEN 0
                    WHEN 'in_progress' THEN 1
                    ELSE 2
                END,
                datetime(la.assigned_at) DESC,
                lower(le.title),
                lower(e.code)
            """,
            (user_id,),
            fetchall=True,
        )
        return [self._row_to_assignment(row) for row in rows]

    def list_assignments(self, live_exam_id):
        _, rows = self.db.execute(
            """
            SELECT
                la.id AS assignment_id,
                la.live_exam_id,
                la.user_id,
                la.attempt_id,
                la.assignment_status,
                la.assigned_at,
                la.started_at AS assignment_started_at,
                la.completed_at,
                u.display_name,
                u.login_name,
                a.status AS attempt_status,
                a.started_at AS attempt_started_at,
                a.submitted_at AS attempt_submitted_at,
                a.score_percent
            FROM live_exam_assignments la
            JOIN users u ON u.id = la.user_id
            LEFT JOIN exam_attempts a ON a.id = la.attempt_id
            WHERE la.live_exam_id = ?
            ORDER BY lower(u.display_name), lower(u.login_name)
            """,
            (live_exam_id,),
            fetchall=True,
        )
        return [self._row_to_assignment(row) for row in rows]

    def get_assignment(self, assignment_id):
        _, row = self.db.execute(
            """
            SELECT
                la.id AS assignment_id,
                la.live_exam_id,
                la.user_id,
                la.attempt_id,
                la.assignment_status,
                la.assigned_at,
                la.started_at AS assignment_started_at,
                la.completed_at,
                le.exam_id,
                le.title AS live_exam_title,
                le.description AS live_exam_description,
                le.instructions AS live_exam_instructions,
                le.status AS live_exam_status,
                le.question_count,
                le.time_limit_minutes,
                le.criteria_json,
                e.code AS exam_code,
                e.title AS exam_title,
                e.provider AS exam_provider,
                a.status AS attempt_status,
                a.started_at AS attempt_started_at,
                a.submitted_at AS attempt_submitted_at,
                a.score_percent
            FROM live_exam_assignments la
            JOIN live_exams le ON le.id = la.live_exam_id
            JOIN exams e ON e.id = le.exam_id
            LEFT JOIN exam_attempts a ON a.id = la.attempt_id
            WHERE la.id = ?
            """,
            (assignment_id,),
            fetchone=True,
        )
        return self._row_to_assignment(row)

    def list_attempt_ids(self, live_exam_id):
        _, rows = self.db.execute(
            """
            SELECT attempt_id
            FROM live_exam_assignments
            WHERE live_exam_id = ? AND attempt_id IS NOT NULL
            ORDER BY attempt_id
            """,
            (live_exam_id,),
            fetchall=True,
        )
        return [row["attempt_id"] for row in rows]

    def close(self, live_exam_id):
        self.db.execute(
            """
            UPDATE live_exams
            SET status = 'closed', closed_at = COALESCE(closed_at, CURRENT_TIMESTAMP), updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status != 'closed'
            """,
            (live_exam_id,),
        )
        return self.get(live_exam_id)

    def delete(self, live_exam_id):
        self.db.execute("DELETE FROM live_exams WHERE id = ?", (live_exam_id,))

    def attach_attempt(self, assignment_id, attempt_id):
        self.db.execute(
            """
            UPDATE live_exam_assignments
            SET
                attempt_id = ?,
                assignment_status = 'in_progress',
                started_at = COALESCE(started_at, CURRENT_TIMESTAMP)
            WHERE id = ?
            """,
            (attempt_id, assignment_id),
        )
        return self.get_assignment(assignment_id)

    def mark_assignment_completed_by_attempt(self, attempt_id):
        self.db.execute(
            """
            UPDATE live_exam_assignments
            SET
                assignment_status = 'completed',
                completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP)
            WHERE attempt_id = ?
            """,
            (attempt_id,),
        )

    def _row_to_live_exam(self, row):
        return {
            "id": row["id"],
            "exam_id": row["exam_id"],
            "title": row["title"],
            "description": row["description"] or "",
            "instructions": row["instructions"] or "",
            "status": row["status"],
            "question_count": row["question_count"],
            "time_limit_minutes": row["time_limit_minutes"],
            "criteria": json.loads(row["criteria_json"] or "{}"),
            "created_by": row["created_by"],
            "created_by_name": row["created_by_name"] or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "closed_at": row["closed_at"],
            "exam_code": row["exam_code"],
            "exam_title": row["exam_title"],
            "exam_provider": row["exam_provider"],
        }

    def _row_to_assignment(self, row):
        if not row:
            return None
        effective_status = self._resolve_assignment_status(row)
        read = lambda key, default=None: row[key] if key in row.keys() else default
        return {
            "assignment_id": row["assignment_id"],
            "live_exam_id": row["live_exam_id"],
            "user_id": row["user_id"],
            "attempt_id": row["attempt_id"],
            "assignment_status": effective_status,
            "assigned_at": row["assigned_at"],
            "started_at": row["assignment_started_at"] or read("attempt_started_at"),
            "completed_at": row["completed_at"] or read("attempt_submitted_at"),
            "live_exam_title": read("live_exam_title", "") or "",
            "live_exam_description": read("live_exam_description", "") or "",
            "live_exam_instructions": read("live_exam_instructions", "") or "",
            "live_exam_status": read("live_exam_status", "active") or "active",
            "question_count": read("question_count"),
            "time_limit_minutes": read("time_limit_minutes"),
            "criteria": json.loads(row["criteria_json"] or "{}") if "criteria_json" in row.keys() else {},
            "exam_id": read("exam_id"),
            "exam_code": read("exam_code", "") or "",
            "exam_title": read("exam_title", "") or "",
            "exam_provider": read("exam_provider", "") or "",
            "display_name": read("display_name", "") or "",
            "login_name": read("login_name", "") or "",
            "attempt_status": read("attempt_status"),
            "attempt_started_at": read("attempt_started_at"),
            "attempt_submitted_at": read("attempt_submitted_at"),
            "score_percent": read("score_percent"),
        }

    def _resolve_assignment_status(self, row):
        read = lambda key, default=None: row[key] if key in row.keys() else default
        if read("attempt_status") == "submitted" or read("completed_at"):
            return "completed"
        if read("assignment_status") == "in_progress" or read("attempt_id") or read("assignment_started_at"):
            return "in_progress"
        return "pending"

    def _summarize_assignments(self, assignments):
        counts = {
            "assigned": len(assignments),
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
        }
        for assignment in assignments:
            counts[assignment["assignment_status"]] += 1
        return counts
