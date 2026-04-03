# api_m/domains/statistics_api.py

from flask import request

from .base_api import BaseAPI


class StatisticsAPI(BaseAPI):
    def register(self):
        self.app.add_url_rule("/api/statistics/overview", endpoint="api_statistics_overview", view_func=self.overview, methods=["GET"])
        self.app.add_url_rule("/api/statistics/me", endpoint="api_statistics_me", view_func=self.my_statistics, methods=["GET"])
        self.app.add_url_rule(
            "/api/statistics/users/<int:user_id>",
            endpoint="api_statistics_user",
            view_func=self.user_statistics,
            methods=["GET"],
        )
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
        stats = self.services.statistics.build_dashboard_payload(user["id"])["overview"]
        return self.ok(stats)

    def my_statistics(self):
        user, error = self.auth_user(request)
        if error:
            return error
        return self.ok(self.services.statistics.build_dashboard_payload(user["id"])["personal"])

    def user_statistics(self, user_id):
        _, error = self.auth_user(request, min_role="administrator")
        if error:
            return error
        target_user = self.db.users.get_by_id(user_id)
        if not target_user:
            return self.error("User not found.", 404)
        payload = self.services.statistics.build_dashboard_payload(user_id)
        payload["user"] = self.user_manager.public_user(target_user)
        return self.ok(payload)

    def exam_statistics(self, exam_id):
        user, error = self.auth_user(request)
        if error:
            return error
        exam, exam_error = self.get_accessible_exam(user, exam_id)
        if exam_error:
            return exam_error
        return self.ok({"exam": exam, "statistics": self.db.statistics.exam_overview(exam_id)})

    def platform_statistics(self):
        user, error = self.auth_user(request)
        if error:
            return error
        if not self.feature_enabled("global_stats_page"):
            return self.error("Global Stats is currently disabled by an administrator.", 403)
        requested_group_id = request.args.get("group_id", "").strip()
        try:
            payload = self.services.statistics.build_platform_payload(user, requested_group_id)
        except ValueError as exc:
            return self.error(str(exc), 400)
        except PermissionError as exc:
            return self.error(str(exc), 403)
        return self.ok(payload)
