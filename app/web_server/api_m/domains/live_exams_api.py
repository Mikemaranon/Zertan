# api_m/domains/live_exams_api.py

from flask import request

from api_m.domains.base_api import BaseAPI


class LiveExamsAPI(BaseAPI):
    def register(self):
        self.app.add_url_rule("/api/live-exams", endpoint="api_live_exams_list", view_func=self.list_live_exams, methods=["GET"])
        self.app.add_url_rule("/api/live-exams", endpoint="api_live_exams_create", view_func=self.create_live_exam, methods=["POST"])
        self.app.add_url_rule(
            "/api/live-exams/<int:live_exam_id>/close",
            endpoint="api_live_exams_close",
            view_func=self.close_live_exam,
            methods=["POST"],
        )
        self.app.add_url_rule(
            "/api/live-exams/<int:live_exam_id>",
            endpoint="api_live_exams_delete",
            view_func=self.delete_live_exam,
            methods=["DELETE"],
        )
        self.app.add_url_rule(
            "/api/live-exams/assignments/<int:assignment_id>/start",
            endpoint="api_live_exams_start_assignment",
            view_func=self.start_assignment,
            methods=["POST"],
        )

    def list_live_exams(self):
        user, error = self.auth_user(request)
        if error:
            return error
        if not self.feature_enabled("live_exams_page"):
            return self.error("Live exams workspace is currently disabled.", 403)

        is_admin = self.user_manager.user_has_role(user, "administrator")
        if is_admin:
            users = [entry for entry in self.db.users.all() if entry["status"] == "active"]
            groups = []
            for entry in self.db.groups.all():
                if entry["status"] != "active":
                    continue
                active_members = [member for member in entry.get("members", []) if member["status"] == "active"]
                if not active_members:
                    continue
                groups.append(
                    {
                        **entry,
                        "members": active_members,
                        "member_count": len(active_members),
                    }
                )
            exams = [entry for entry in self.db.exams.list_all() if entry["question_count"] > 0]
            return self.ok(
                {
                    "mode": "administrator",
                    "live_exams": self.services.live_exams.list_for_admin(),
                    "available_users": users,
                    "available_groups": groups,
                    "available_exams": exams,
                    "feature_enabled": self.feature_enabled("live_exams_page"),
                }
            )

        return self.ok(
            {
                "mode": "user",
                "assignments": self.services.live_exams.list_for_user(user["id"]),
                "feature_enabled": self.feature_enabled("live_exams_page"),
            }
        )

    def create_live_exam(self):
        user, error = self.auth_user(request, min_role="administrator")
        if error:
            return error
        if not self.feature_enabled("live_exams_page"):
            return self.error("Live exams workspace is currently disabled.", 403)
        try:
            live_exam = self.services.live_exams.create_live_exam(request.get_json() or {}, user["id"])
        except ValueError as exc:
            return self.error(str(exc), 400)
        return self.ok({"live_exam": live_exam}, 201)

    def close_live_exam(self, live_exam_id):
        user, error = self.auth_user(request, min_role="administrator")
        if error:
            return error
        if not self.feature_enabled("live_exams_page"):
            return self.error("Live exams workspace is currently disabled.", 403)
        try:
            live_exam = self.services.live_exams.close_live_exam(live_exam_id)
        except ValueError as exc:
            return self.error(str(exc), 400)
        return self.ok({"live_exam": live_exam})

    def delete_live_exam(self, live_exam_id):
        user, error = self.auth_user(request, min_role="administrator")
        if error:
            return error
        if not self.feature_enabled("live_exams_page"):
            return self.error("Live exams workspace is currently disabled.", 403)
        try:
            self.services.live_exams.delete_live_exam(live_exam_id)
        except ValueError as exc:
            return self.error(str(exc), 400)
        return self.ok({"status": "deleted"})

    def start_assignment(self, assignment_id):
        user, error = self.auth_user(request)
        if error:
            return error
        if not self.feature_enabled("live_exams_page"):
            return self.error("Live exams workspace is currently disabled.", 403)
        try:
            attempt_id = self.services.live_exams.start_assignment(assignment_id, user)
        except ValueError as exc:
            return self.error(str(exc), 400)
        return self.ok({"attempt_id": attempt_id})
