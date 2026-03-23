# db_methods/t_statistics.py


class StatisticsTable:
    def __init__(self, db):
        self.db = db

    def _normalize_group_ids(self, group_ids):
        if group_ids is None:
            return None
        if isinstance(group_ids, (list, tuple, set)):
            values = group_ids
        else:
            values = [group_ids]
        normalized = []
        seen = set()
        for value in values:
            try:
                group_id = int(value)
            except (TypeError, ValueError):
                continue
            if group_id < 1 or group_id in seen:
                continue
            seen.add(group_id)
            normalized.append(group_id)
        return normalized

    def _build_group_scope_clause(self, user_column, group_ids, prefix="AND"):
        normalized_group_ids = self._normalize_group_ids(group_ids)
        if normalized_group_ids is None:
            return "", []
        if not normalized_group_ids:
            return f" {prefix} 1 = 0 ", []
        placeholders = ",".join("?" for _ in normalized_group_ids)
        return (
            f"""
                {prefix} EXISTS (
                    SELECT 1
                    FROM user_group_memberships gm
                    WHERE gm.user_id = {user_column}
                    AND gm.group_id IN ({placeholders})
                )
            """,
            normalized_group_ids,
        )

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

    def hardest_questions(self, limit=5, group_ids=None):
        params = []
        query = """
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
        """
        scope_clause, scope_params = self._build_group_scope_clause("a.user_id", group_ids, prefix="AND")
        query += scope_clause
        params.extend(scope_params)
        query += """
            GROUP BY q.id
            HAVING COUNT(ans.id) > 0
            ORDER BY success_rate ASC, answers_count DESC
            LIMIT ?
        """
        params.append(limit)
        _, rows = self.db.execute(query, tuple(params), fetchall=True)
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

    def hardest_topics(self, limit=5, group_ids=None):
        params = []
        query = """
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
        """
        scope_clause, scope_params = self._build_group_scope_clause("a.user_id", group_ids, prefix="AND")
        query += scope_clause
        params.extend(scope_params)
        query += """
            GROUP BY tp.id
            HAVING COUNT(ans.id) > 0
            ORDER BY success_rate ASC, answers_count DESC
            LIMIT ?
        """
        params.append(limit)
        _, rows = self.db.execute(query, tuple(params), fetchall=True)
        return [
            {
                "topic": row["topic"],
                "success_rate": round(row["success_rate"] or 0, 2),
                "answers_count": row["answers_count"],
            }
            for row in rows
        ]

    def hardest_tags(self, limit=5, group_ids=None):
        params = []
        query = """
            SELECT
                tg.name AS tag,
                AVG(COALESCE(ans.is_correct, 0)) * 100 AS success_rate,
                COUNT(ans.id) AS answers_count
            FROM exam_answers ans
            JOIN questions q ON q.id = ans.question_id
            JOIN question_tags qt ON qt.question_id = q.id
            JOIN tags tg ON tg.id = qt.tag_id
            JOIN exam_attempts a ON a.id = ans.attempt_id
            WHERE a.status = 'submitted'
        """
        scope_clause, scope_params = self._build_group_scope_clause("a.user_id", group_ids, prefix="AND")
        query += scope_clause
        params.extend(scope_params)
        query += """
            GROUP BY tg.id
            HAVING COUNT(ans.id) > 0
            ORDER BY success_rate ASC, answers_count DESC
            LIMIT ?
        """
        params.append(limit)
        _, rows = self.db.execute(query, tuple(params), fetchall=True)
        return [
            {
                "tag": row["tag"],
                "success_rate": round(row["success_rate"] or 0, 2),
                "answers_count": row["answers_count"],
            }
            for row in rows
        ]

    def platform_summary(self, group_ids=None):
        user_params = []
        user_query = """
            SELECT
                COUNT(*) AS total_users,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_users
            FROM users
        """
        user_scope_clause, user_scope_params = self._build_group_scope_clause("users.id", group_ids, prefix="WHERE")
        user_query += user_scope_clause
        user_params.extend(user_scope_params)
        _, users = self.db.execute(user_query, tuple(user_params), fetchone=True)

        attempt_params = []
        attempt_query = """
            SELECT
                COUNT(*) AS submitted_attempts,
                COALESCE(SUM(question_count), 0) AS total_questions_answered,
                COALESCE(SUM(correct_count), 0) AS total_correct,
                COALESCE(SUM(incorrect_count), 0) AS total_incorrect,
                COALESCE(SUM(omitted_count), 0) AS total_omitted,
                COALESCE(AVG(duration_seconds), 0) AS average_completion_time,
                COALESCE(AVG(question_count), 0) AS average_questions_per_attempt
            FROM exam_attempts
            WHERE status = 'submitted'
        """
        attempt_scope_clause, attempt_scope_params = self._build_group_scope_clause(
            "exam_attempts.user_id",
            group_ids,
            prefix="AND",
        )
        attempt_query += attempt_scope_clause
        attempt_params.extend(attempt_scope_params)
        _, attempts = self.db.execute(attempt_query, tuple(attempt_params), fetchone=True)
        total_questions = attempts["total_questions_answered"] or 0
        total_correct = attempts["total_correct"] or 0
        success_rate = round((total_correct * 100.0 / total_questions), 2) if total_questions else 0
        return {
            "total_users": users["total_users"] or 0,
            "active_users": users["active_users"] or 0,
            "submitted_attempts": attempts["submitted_attempts"] or 0,
            "total_questions_answered": total_questions,
            "total_correct": total_correct,
            "total_incorrect": attempts["total_incorrect"] or 0,
            "total_omitted": attempts["total_omitted"] or 0,
            "global_success_rate": success_rate,
            "average_completion_time": int(attempts["average_completion_time"] or 0),
            "average_questions_per_attempt": round(attempts["average_questions_per_attempt"] or 0, 1),
        }

    def platform_user_comparison(self, group_ids=None):
        params = []
        query = """
            SELECT
                u.id,
                u.display_name,
                u.login_name,
                u.role,
                u.status,
                COUNT(a.id) AS submitted_attempts,
                COALESCE(SUM(a.question_count), 0) AS questions_answered,
                COALESCE(SUM(a.correct_count), 0) AS total_correct,
                COALESCE(SUM(a.incorrect_count), 0) AS total_incorrect,
                COALESCE(SUM(a.omitted_count), 0) AS total_omitted,
                COALESCE(AVG(a.score_percent), 0) AS average_score,
                COALESCE(AVG(a.duration_seconds), 0) AS average_completion_time
            FROM users u
            LEFT JOIN exam_attempts a
                ON a.user_id = u.id
                AND a.status = 'submitted'
            WHERE lower(COALESCE(u.role, 'user')) != 'administrator'
        """
        scope_clause, scope_params = self._build_group_scope_clause("u.id", group_ids, prefix="AND")
        query += scope_clause
        params.extend(scope_params)
        query += """
            GROUP BY u.id
            ORDER BY submitted_attempts DESC, average_score DESC, lower(u.display_name), lower(u.login_name)
        """
        _, rows = self.db.execute(query, tuple(params), fetchall=True)
        payload = []
        for row in rows:
            answered = row["questions_answered"] or 0
            correct = row["total_correct"] or 0
            payload.append(
                {
                    "user_id": row["id"],
                    "display_name": row["display_name"],
                    "login_name": row["login_name"],
                    "role": row["role"],
                    "status": row["status"],
                    "submitted_attempts": row["submitted_attempts"] or 0,
                    "questions_answered": answered,
                    "total_correct": correct,
                    "total_incorrect": row["total_incorrect"] or 0,
                    "total_omitted": row["total_omitted"] or 0,
                    "success_rate": round((correct * 100.0 / answered), 2) if answered else 0,
                    "average_score": round(row["average_score"] or 0, 2),
                    "average_completion_time": int(row["average_completion_time"] or 0),
                }
            )
        return payload

    def platform_success_by_exam(self, group_ids=None):
        params = []
        query = """
            SELECT
                e.id,
                e.code,
                e.title,
                COUNT(a.id) AS attempts,
                COUNT(DISTINCT a.user_id) AS active_users,
                AVG(a.score_percent) AS success_rate,
                AVG(a.duration_seconds) AS average_completion_time
            FROM exams e
            LEFT JOIN exam_attempts a
                ON a.exam_id = e.id
                AND a.status = 'submitted'
        """
        scope_clause, scope_params = self._build_group_scope_clause("a.user_id", group_ids, prefix="AND")
        query += scope_clause
        params.extend(scope_params)
        query += """
            GROUP BY e.id
            ORDER BY attempts DESC, lower(e.code), lower(e.title)
        """
        _, rows = self.db.execute(query, tuple(params), fetchall=True)
        return [
            {
                "exam_id": row["id"],
                "code": row["code"],
                "title": row["title"],
                "attempts": row["attempts"] or 0,
                "active_users": row["active_users"] or 0,
                "success_rate": round(row["success_rate"] or 0, 2),
                "average_completion_time": int(row["average_completion_time"] or 0),
            }
            for row in rows
        ]

    def platform_success_by_question_type(self, group_ids=None):
        params = []
        query = """
            SELECT
                aq_snapshot.type AS question_type,
                COUNT(*) AS total_answers,
                AVG(COALESCE(ans.is_correct, 0)) * 100 AS success_rate
            FROM (
                SELECT
                    aq.id,
                    json_extract(aq.snapshot_json, '$.type') AS type
                FROM exam_attempt_questions aq
            ) aq_snapshot
            JOIN exam_answers ans ON ans.attempt_question_id = aq_snapshot.id
            JOIN exam_attempts a ON a.id = ans.attempt_id
            WHERE a.status = 'submitted'
        """
        scope_clause, scope_params = self._build_group_scope_clause("a.user_id", group_ids, prefix="AND")
        query += scope_clause
        params.extend(scope_params)
        query += """
            GROUP BY aq_snapshot.type
            ORDER BY total_answers DESC, aq_snapshot.type
        """
        _, rows = self.db.execute(query, tuple(params), fetchall=True)
        return [
            {
                "question_type": row["question_type"],
                "total_answers": row["total_answers"] or 0,
                "success_rate": round(row["success_rate"] or 0, 2),
            }
            for row in rows
        ]

    def platform_activity_by_week(self, limit=8, group_ids=None):
        params = []
        query = """
            SELECT
                date(submitted_at, 'weekday 0', '-6 days') AS week_start,
                COUNT(*) AS attempts,
                COUNT(DISTINCT user_id) AS active_users
            FROM exam_attempts
            WHERE status = 'submitted'
        """
        scope_clause, scope_params = self._build_group_scope_clause("exam_attempts.user_id", group_ids, prefix="AND")
        query += scope_clause
        params.extend(scope_params)
        query += """
            GROUP BY week_start
            ORDER BY week_start DESC
            LIMIT ?
        """
        params.append(limit)
        _, rows = self.db.execute(query, tuple(params), fetchall=True)
        payload = [
            {
                "week_start": row["week_start"],
                "attempts": row["attempts"] or 0,
                "active_users": row["active_users"] or 0,
            }
            for row in rows
        ]
        payload.reverse()
        return payload

    def platform_overview(self, group_ids=None):
        return {
            "summary": self.platform_summary(group_ids),
            "users": self.platform_user_comparison(group_ids),
            "by_exam": self.platform_success_by_exam(group_ids),
            "by_question_type": self.platform_success_by_question_type(group_ids),
            "activity_by_week": self.platform_activity_by_week(group_ids=group_ids),
            "hardest_questions": self.hardest_questions(group_ids=group_ids),
            "hardest_topics": self.hardest_topics(group_ids=group_ids),
            "hardest_tags": self.hardest_tags(group_ids=group_ids),
        }
