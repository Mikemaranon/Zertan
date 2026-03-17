# db_methods/t_statistics.py


class StatisticsTable:
    def __init__(self, db):
        self.db = db

    def user_overview(self, user_id):
        _, totals = self.db.execute(
            """
            SELECT
                COUNT(*) AS exams_completed,
                COALESCE(SUM(question_count), 0) AS questions_answered,
                COALESCE(SUM(correct_count), 0) AS total_correct,
                COALESCE(SUM(incorrect_count), 0) AS total_incorrect,
                COALESCE(SUM(omitted_count), 0) AS total_omitted,
                COALESCE(AVG(score_percent), 0) AS global_success_rate,
                COALESCE(AVG(duration_seconds), 0) AS average_completion_time
            FROM exam_attempts
            WHERE user_id = ? AND status = 'submitted'
            """,
            (user_id,),
            fetchone=True,
        )
        return {
            "exams_completed": totals["exams_completed"],
            "questions_answered": totals["questions_answered"],
            "total_correct": totals["total_correct"],
            "total_incorrect": totals["total_incorrect"],
            "total_omitted": totals["total_omitted"],
            "global_success_rate": round(totals["global_success_rate"] or 0, 2),
            "average_completion_time": int(totals["average_completion_time"] or 0),
        }

    def user_success_by_exam(self, user_id):
        _, rows = self.db.execute(
            """
            SELECT
                e.id,
                e.code,
                e.title,
                COUNT(a.id) AS attempts,
                AVG(a.score_percent) AS success_rate
            FROM exam_attempts a
            JOIN exams e ON e.id = a.exam_id
            WHERE a.user_id = ? AND a.status = 'submitted'
            GROUP BY e.id
            ORDER BY e.code
            """,
            (user_id,),
            fetchall=True,
        )
        return [
            {
                "exam_id": row["id"],
                "code": row["code"],
                "title": row["title"],
                "attempts": row["attempts"],
                "success_rate": round(row["success_rate"] or 0, 2),
            }
            for row in rows
        ]

    def user_success_by_question_type(self, user_id):
        _, rows = self.db.execute(
            """
            SELECT
                aq_snapshot.type AS question_type,
                COUNT(*) AS total,
                AVG(COALESCE(ans.is_correct, 0)) * 100 AS success_rate
            FROM (
                SELECT
                    aq.id,
                    json_extract(aq.snapshot_json, '$.type') AS type
                FROM exam_attempt_questions aq
            ) aq_snapshot
            JOIN exam_answers ans ON ans.attempt_question_id = aq_snapshot.id
            JOIN exam_attempts a ON a.id = ans.attempt_id
            WHERE a.user_id = ? AND a.status = 'submitted'
            GROUP BY aq_snapshot.type
            ORDER BY aq_snapshot.type
            """,
            (user_id,),
            fetchall=True,
        )
        return [
            {
                "question_type": row["question_type"],
                "total": row["total"],
                "success_rate": round(row["success_rate"] or 0, 2),
            }
            for row in rows
        ]

    def exam_overview(self, exam_id):
        _, row = self.db.execute(
            """
            SELECT
                COUNT(*) AS attempts,
                AVG(score_percent) AS average_score,
                AVG(duration_seconds) AS average_completion_time
            FROM exam_attempts
            WHERE exam_id = ? AND status = 'submitted'
            """,
            (exam_id,),
            fetchone=True,
        )
        return {
            "attempts": row["attempts"],
            "average_score": round(row["average_score"] or 0, 2),
            "average_completion_time": int(row["average_completion_time"] or 0),
        }

    def hardest_questions(self, limit=5):
        _, rows = self.db.execute(
            """
            SELECT
                q.id,
                q.title,
                q.statement,
                e.code,
                AVG(COALESCE(ans.is_correct, 0)) * 100 AS success_rate,
                COUNT(ans.id) AS answers_count
            FROM exam_answers ans
            JOIN questions q ON q.id = ans.question_id
            JOIN exams e ON e.id = q.exam_id
            JOIN exam_attempts a ON a.id = ans.attempt_id
            WHERE a.status = 'submitted'
            GROUP BY q.id
            HAVING COUNT(ans.id) > 0
            ORDER BY success_rate ASC, answers_count DESC
            LIMIT ?
            """,
            (limit,),
            fetchall=True,
        )
        return [
            {
                "question_id": row["id"],
                "title": row["title"],
                "statement": row["statement"],
                "exam_code": row["code"],
                "success_rate": round(row["success_rate"] or 0, 2),
                "answers_count": row["answers_count"],
            }
            for row in rows
        ]

    def hardest_topics(self, limit=5):
        _, rows = self.db.execute(
            """
            SELECT
                tp.name AS topic,
                AVG(COALESCE(ans.is_correct, 0)) * 100 AS success_rate,
                COUNT(ans.id) AS answers_count
            FROM exam_answers ans
            JOIN questions q ON q.id = ans.question_id
            JOIN question_topics qt ON qt.question_id = q.id
            JOIN topics tp ON tp.id = qt.topic_id
            JOIN exam_attempts a ON a.id = ans.attempt_id
            WHERE a.status = 'submitted'
            GROUP BY tp.id
            HAVING COUNT(ans.id) > 0
            ORDER BY success_rate ASC, answers_count DESC
            LIMIT ?
            """,
            (limit,),
            fetchall=True,
        )
        return [
            {
                "topic": row["topic"],
                "success_rate": round(row["success_rate"] or 0, 2),
                "answers_count": row["answers_count"],
            }
            for row in rows
        ]

    def platform_overview(self):
        _, exams = self.db.execute("SELECT COUNT(*) AS total FROM exams", fetchone=True)
        _, users = self.db.execute("SELECT COUNT(*) AS total FROM users", fetchone=True)
        _, attempts = self.db.execute(
            "SELECT COUNT(*) AS total FROM exam_attempts WHERE status = 'submitted'",
            fetchone=True,
        )
        return {
            "exam_count": exams["total"],
            "user_count": users["total"],
            "submitted_attempts": attempts["total"],
            "hardest_questions": self.hardest_questions(),
            "hardest_topics": self.hardest_topics(),
        }
