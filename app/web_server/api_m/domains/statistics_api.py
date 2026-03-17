# api_m/domains/statistics_api.py

from flask import request

from api_m.domains.base_api import BaseAPI


class StatisticsAPI(BaseAPI):
    def register(self):
        self.app.add_url_rule("/api/statistics/overview", endpoint="api_statistics_overview", view_func=self.overview, methods=["GET"])
        self.app.add_url_rule("/api/statistics/me", endpoint="api_statistics_me", view_func=self.my_statistics, methods=["GET"])
        self.app.add_url_rule(
            "/api/statistics/exams/<int:exam_id>",
            endpoint="api_statistics_exam",
            view_func=self.exam_statistics,
            methods=["GET"],
        )
        self.app.add_url_rule(
            "/api/statistics/platform",
            endpoint="api_statistics_platform",
            view_func=self.platform_statistics,
            methods=["GET"],
        )

    def overview(self):
        user, error = self.auth_user(request)
        if error:
            return error
        stats = {
            "kpis": self.db.statistics.user_overview(user["id"]),
            "by_exam": self.db.statistics.user_success_by_exam(user["id"]),
            "recent_attempts": self.db.attempts.list_recent_for_user(user["id"], limit=4),
        }
        return self.ok(stats)

    def my_statistics(self):
        user, error = self.auth_user(request)
        if error:
            return error
        return self.ok(
            {
                "kpis": self.db.statistics.user_overview(user["id"]),
                "by_exam": self.db.statistics.user_success_by_exam(user["id"]),
                "by_question_type": self.db.statistics.user_success_by_question_type(user["id"]),
            }
        )

    def exam_statistics(self, exam_id):
        user, error = self.auth_user(request)
        if error:
            return error
        exam = self.db.exams.get(exam_id)
        if not exam:
            return self.error("Exam not found.", 404)
        return self.ok({"exam": exam, "statistics": self.db.statistics.exam_overview(exam_id)})

    def platform_statistics(self):
        user, error = self.auth_user(request, min_role="examiner")
        if error:
            return error
        return self.ok({"platform": self.db.statistics.platform_overview()})
