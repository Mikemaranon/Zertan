# api_m/domains/statistics_api.py

from flask import request

from api_m.domains.base_api import BaseAPI


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
        stats = self._build_dashboard_payload(user["id"])["overview"]
        return self.ok(stats)

    def my_statistics(self):
        user, error = self.auth_user(request)
        if error:
            return error
        return self.ok(self._build_dashboard_payload(user["id"])["personal"])

    def user_statistics(self, user_id):
        _, error = self.auth_user(request, min_role="administrator")
        if error:
            return error
        target_user = self.db.users.get_by_id(user_id)
        if not target_user:
            return self.error("User not found.", 404)
        payload = self._build_dashboard_payload(user_id)
        payload["user"] = self.user_manager.public_user(target_user)
        return self.ok(payload)

    def exam_statistics(self, exam_id):
        user, error = self.auth_user(request)
        if error:
            return error
        exam = self.db.exams.get(exam_id)
        if not exam:
            return self.error("Exam not found.", 404)
        return self.ok({"exam": exam, "statistics": self.db.statistics.exam_overview(exam_id)})

    def platform_statistics(self):
        user, error = self.auth_user(request)
        if error:
            return error
        if not self.feature_enabled("global_stats_page"):
            return self.error("Global Stats is currently disabled by an administrator.", 403)
        is_administrator = self.user_manager.user_has_role(user, "administrator")
        allowed_groups = self.db.groups.list_scope_options_for_user(None if is_administrator else user["id"])
        requested_group_id = request.args.get("group_id", "").strip()
        selected_group_id = None
        if requested_group_id:
            try:
                selected_group_id = int(requested_group_id)
            except ValueError:
                return self.error("Group id must be a valid integer.", 400)
            allowed_group_ids = {group["id"] for group in allowed_groups}
            if selected_group_id not in allowed_group_ids:
                return self.error("Selected group is not available for this user.", 403)

        scope_group_ids = None
        if is_administrator:
            if selected_group_id is not None:
                scope_group_ids = [selected_group_id]
        else:
            scope_group_ids = [selected_group_id] if selected_group_id is not None else [group["id"] for group in allowed_groups]

        return self.ok(
            {
                "platform": self.db.statistics.platform_overview(scope_group_ids),
                "current_user_id": user["id"],
                "current_user_role": user["role"],
                "comparison_groups": allowed_groups,
                "selected_group_id": selected_group_id,
            }
        )

    def _build_dashboard_payload(self, user_id):
        kpis = self.db.statistics.user_overview(user_id)
        by_exam = self.db.statistics.user_success_by_exam(user_id)
        return {
            "overview": {
                "kpis": kpis,
                "by_exam": by_exam,
                "recent_attempts": self.db.attempts.list_recent_for_user(user_id, limit=4),
            },
            "personal": {
                "kpis": kpis,
                "by_exam": by_exam,
                "by_question_type": self.db.statistics.user_success_by_question_type(user_id),
            },
        }
