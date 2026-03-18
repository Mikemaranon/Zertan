# api_m/domains/attempts_api.py

from flask import request

from api_m.domains.base_api import BaseAPI
from services_m import AttemptService, LiveExamService


class AttemptsAPI(BaseAPI):
    def register(self):
        self.app.add_url_rule("/api/attempts/<int:attempt_id>", endpoint="api_attempts_get", view_func=self.get_attempt, methods=["GET"])
        self.app.add_url_rule(
            "/api/attempts/<int:attempt_id>/answers",
            endpoint="api_attempts_answers",
            view_func=self.save_answers,
            methods=["POST"],
        )
        self.app.add_url_rule(
            "/api/attempts/<int:attempt_id>/submit",
            endpoint="api_attempts_submit",
            view_func=self.submit_attempt,
            methods=["POST"],
        )
        self.app.add_url_rule(
            "/api/attempts/<int:attempt_id>/result",
            endpoint="api_attempts_result",
            view_func=self.get_result,
            methods=["GET"],
        )

    def get_attempt(self, attempt_id):
        user, error = self.auth_user(request)
        if error:
            return error
        service = AttemptService(self.db)
        payload = service.get_attempt_payload(attempt_id)
        if not payload:
            return self.error("Attempt not found.", 404)
        if not self._can_access_attempt(user, payload["attempt"]["user_id"]):
            return self.error("Forbidden", 403)
        return self.ok(payload)

    def save_answers(self, attempt_id):
        user, error = self.auth_user(request)
        if error:
            return error
        service = AttemptService(self.db)
        payload = service.get_attempt_payload(attempt_id)
        if not payload:
            return self.error("Attempt not found.", 404)
        if not self._can_access_attempt(user, payload["attempt"]["user_id"]):
            return self.error("Forbidden", 403)
        if payload["attempt"]["status"] != "in_progress":
            return self.error("Attempt is already submitted.", 400)
        answers = (request.get_json() or {}).get("answers", [])
        service.save_answers(attempt_id, answers)
        return self.ok({"status": "saved"})

    def submit_attempt(self, attempt_id):
        user, error = self.auth_user(request)
        if error:
            return error
        service = AttemptService(self.db)
        payload = service.get_attempt_payload(attempt_id)
        if not payload:
            return self.error("Attempt not found.", 404)
        if not self._can_access_attempt(user, payload["attempt"]["user_id"]):
            return self.error("Forbidden", 403)
        answers = (request.get_json() or {}).get("answers", [])
        if answers:
            service.save_answers(attempt_id, answers)
        result = service.submit_attempt(attempt_id)
        LiveExamService(self.db).mark_completed_for_attempt(attempt_id)
        return self.ok(result)

    def get_result(self, attempt_id):
        user, error = self.auth_user(request)
        if error:
            return error
        service = AttemptService(self.db)
        result = service.get_result_payload(attempt_id)
        if not result:
            return self.error("Attempt not found.", 404)
        if not self._can_access_attempt(user, result["attempt"]["user_id"]):
            return self.error("Forbidden", 403)
        return self.ok(result)

    def _can_access_attempt(self, user, owner_id):
        return owner_id == user["id"] or self.user_manager.user_has_role(user, "examiner")
