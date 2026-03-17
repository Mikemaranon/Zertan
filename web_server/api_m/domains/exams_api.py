# api_m/domains/exams_api.py

from flask import request

from api_m.domains.base_api import BaseAPI
from services_m import AttemptService, build_public_question


class ExamsAPI(BaseAPI):
    def register(self):
        self.app.add_url_rule("/api/exams", endpoint="api_exams_list", view_func=self.list_exams, methods=["GET"])
        self.app.add_url_rule("/api/exams", endpoint="api_exams_create", view_func=self.create_exam, methods=["POST"])
        self.app.add_url_rule("/api/exams/<int:exam_id>", endpoint="api_exams_get", view_func=self.get_exam, methods=["GET"])
        self.app.add_url_rule("/api/exams/<int:exam_id>", endpoint="api_exams_update", view_func=self.update_exam, methods=["PUT"])
        self.app.add_url_rule(
            "/api/exams/<int:exam_id>/study",
            endpoint="api_exams_study",
            view_func=self.get_study_mode,
            methods=["GET"],
        )
        self.app.add_url_rule(
            "/api/exams/<int:exam_id>/builder-meta",
            endpoint="api_exams_builder_meta",
            view_func=self.get_builder_meta,
            methods=["GET"],
        )
        self.app.add_url_rule(
            "/api/exams/<int:exam_id>/builder",
            endpoint="api_exams_builder",
            view_func=self.build_attempt,
            methods=["POST"],
        )

    def list_exams(self):
        user, error = self.auth_user(request)
        if error:
            return error
        exams = self.db.exams.list_all()
        return self.ok({"exams": exams, "user": user})

    def create_exam(self):
        user, error = self.auth_user(request, min_role="examiner")
        if error:
            return error
        payload = request.get_json() or {}
        required = ["code", "title", "provider"]
        if any(not str(payload.get(field, "")).strip() for field in required):
            return self.error("Code, title, and provider are required.", 400)
        try:
            exam_id = self.db.exams.create(payload, user["id"])
        except ValueError as exc:
            return self.error(str(exc), 400)
        return self.ok({"exam": self.db.exams.get(exam_id)}, 201)

    def get_exam(self, exam_id):
        user, error = self.auth_user(request)
        if error:
            return error
        exam = self.db.exams.get(exam_id)
        if not exam:
            return self.error("Exam not found.", 404)
        exam["builder_meta"] = self.db.exams.list_builder_metadata(exam_id)
        exam["can_manage"] = self.user_manager.user_has_role(user, "examiner")
        exam["can_edit_questions"] = self.user_manager.user_has_role(user, "reviewer")
        return self.ok({"exam": exam})

    def update_exam(self, exam_id):
        user, error = self.auth_user(request, min_role="examiner")
        if error:
            return error
        exam = self.db.exams.get(exam_id)
        if not exam:
            return self.error("Exam not found.", 404)
        payload = request.get_json() or {}
        required = ["code", "title", "provider"]
        if any(not str(payload.get(field, "")).strip() for field in required):
            return self.error("Code, title, and provider are required.", 400)
        try:
            self.db.exams.update(exam_id, payload)
        except ValueError as exc:
            return self.error(str(exc), 400)
        return self.ok({"exam": self.db.exams.get(exam_id)})

    def get_study_mode(self, exam_id):
        user, error = self.auth_user(request)
        if error:
            return error
        exam = self.db.exams.get(exam_id)
        if not exam:
            return self.error("Exam not found.", 404)
        questions = [
            build_public_question(question, include_solution=False)
            for question in self.db.questions.list_for_exam(exam_id, include_answers=False)
        ]
        exam["builder_meta"] = self.db.exams.list_builder_metadata(exam_id)
        exam["can_manage"] = self.user_manager.user_has_role(user, "examiner")
        exam["can_edit_questions"] = self.user_manager.user_has_role(user, "reviewer")
        return self.ok({"exam": exam, "questions": questions})

    def get_builder_meta(self, exam_id):
        user, error = self.auth_user(request)
        if error:
            return error
        exam = self.db.exams.get(exam_id)
        if not exam:
            return self.error("Exam not found.", 404)
        return self.ok({"builder_meta": self.db.exams.list_builder_metadata(exam_id), "exam": exam})

    def build_attempt(self, exam_id):
        user, error = self.auth_user(request)
        if error:
            return error
        exam = self.db.exams.get(exam_id)
        if not exam:
            return self.error("Exam not found.", 404)
        criteria = request.get_json() or {}
        try:
            attempt_id = AttemptService(self.db).create_attempt(exam_id, user["id"], criteria)
        except ValueError as exc:
            return self.error(str(exc), 400)
        return self.ok({"attempt_id": attempt_id}, 201)
