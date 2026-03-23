# api_m/domains/questions_api.py

from flask import current_app, request

from api_m.question_payload_parser import QuestionPayloadParser
from api_m.domains.base_api import BaseAPI


class QuestionsAPI(BaseAPI):
    def register(self):
        self.app.add_url_rule("/api/questions/<int:question_id>", endpoint="api_questions_get", view_func=self.get_question, methods=["GET"])
        self.app.add_url_rule(
            "/api/exams/<int:exam_id>/questions",
            endpoint="api_questions_list",
            view_func=self.list_questions_for_exam,
            methods=["GET"],
        )
        self.app.add_url_rule(
            "/api/exams/<int:exam_id>/questions",
            endpoint="api_questions_create",
            view_func=self.create_question,
            methods=["POST"],
        )
        self.app.add_url_rule("/api/questions/<int:question_id>", endpoint="api_questions_update", view_func=self.update_question, methods=["PUT"])
        self.app.add_url_rule("/api/questions/<int:question_id>", endpoint="api_questions_delete", view_func=self.delete_question, methods=["DELETE"])
        self.app.add_url_rule(
            "/api/questions/<int:question_id>/archive",
            endpoint="api_questions_archive",
            view_func=self.archive_question,
            methods=["POST"],
        )
        self.app.add_url_rule(
            "/api/questions/<int:question_id>/check",
            endpoint="api_questions_check",
            view_func=self.check_question,
            methods=["POST"],
        )

    def list_questions_for_exam(self, exam_id):
        user, error = self.auth_user(request, min_role="reviewer")
        if error:
            return error
        exam, exam_error = self.get_accessible_exam(user, exam_id)
        if exam_error:
            return exam_error
        if not self.user_can_manage_exam(user, exam):
            return self.error("Forbidden", 403)

        questions = self.db.questions.list_for_exam(exam_id, include_answers=False, include_archived=True)
        items = [self._serialize_question_summary(question, user) for question in questions]
        return self.ok(
            {
                "exam": {
                    **exam,
                    "can_edit_questions": self.user_manager.user_has_role(user, "reviewer") and self.user_can_manage_exam(user, exam),
                    "can_delete_questions": self.user_manager.user_has_role(user, "examiner") and self.user_can_manage_exam(user, exam),
                },
                "questions": items,
            }
        )

    def get_question(self, question_id):
        user, error = self.auth_user(request)
        if error:
            return error
        question = self.db.questions.get(
            question_id,
            include_answers=self.user_manager.user_has_role(user, "reviewer"),
        )
        if not question:
            return self.error("Question not found.", 404)
        if not self.user_can_access_exam(user, question["exam_id"]):
            return self.error("Forbidden", 403)
        if not self.user_manager.user_has_role(user, "reviewer"):
            question = self.services.question_logic.build_public_question(question, include_solution=False)
        return self.ok({"question": question})

    def create_question(self, exam_id):
        user, error = self.auth_user(request, min_role="reviewer")
        if error:
            return error
        _, exam_error = self.get_accessible_exam(user, exam_id)
        if exam_error:
            return exam_error
        exam = self.db.exams.get(exam_id)
        if not self.user_can_manage_exam(user, exam):
            return self.error("Forbidden", 403)
        try:
            payload = self._parse_question_payload(exam_id)
            question_id = self.db.questions.create(exam_id, payload)
        except ValueError as exc:
            return self.error(str(exc), 400)
        return self.ok({"question": self.db.questions.get(question_id, include_answers=True)}, 201)

    def update_question(self, question_id):
        user, error = self.auth_user(request, min_role="reviewer")
        if error:
            return error
        current_question = self.db.questions.get(question_id, include_answers=True)
        if not current_question:
            return self.error("Question not found.", 404)
        if not self.user_can_access_exam(user, current_question["exam_id"]):
            return self.error("Forbidden", 403)
        exam = self.db.exams.get(current_question["exam_id"])
        if not self.user_can_manage_exam(user, exam):
            return self.error("Forbidden", 403)
        try:
            payload = self._parse_question_payload(current_question["exam_id"], current_question=current_question)
            self.db.questions.update(question_id, payload)
        except ValueError as exc:
            return self.error(str(exc), 400)
        return self.ok({"question": self.db.questions.get(question_id, include_answers=True)})

    def delete_question(self, question_id):
        user, error = self.auth_user(request, min_role="examiner")
        if error:
            return error
        question = self.db.questions.get(question_id, include_answers=True)
        if not question:
            return self.error("Question not found.", 404)
        if not self.user_can_access_exam(user, question["exam_id"]):
            return self.error("Forbidden", 403)
        exam = self.db.exams.get(question["exam_id"])
        if not self.user_can_manage_exam(user, exam):
            return self.error("Forbidden", 403)
        self.db.questions.delete(question_id)
        return self.ok({"status": "deleted"})

    def archive_question(self, question_id):
        user, error = self.auth_user(request, min_role="reviewer")
        if error:
            return error
        question = self.db.questions.get(question_id, include_answers=True)
        if not question:
            return self.error("Question not found.", 404)
        if not self.user_can_access_exam(user, question["exam_id"]):
            return self.error("Forbidden", 403)
        exam = self.db.exams.get(question["exam_id"])
        if not self.user_can_manage_exam(user, exam):
            return self.error("Forbidden", 403)
        self.db.questions.archive(question_id)
        return self.ok({"status": "archived"})

    def check_question(self, question_id):
        user, error = self.auth_user(request)
        if error:
            return error
        question = self.db.questions.get(question_id, include_answers=True)
        if not question:
            return self.error("Question not found.", 404)
        if not self.user_can_access_exam(user, question["exam_id"]):
            return self.error("Forbidden", 403)
        response_payload = (request.get_json() or {}).get("response") or {}
        evaluation = self.services.question_logic.evaluate_question_response(question, response_payload)
        return self.ok(
            {
                "result": {
                    "is_correct": evaluation["is_correct"],
                    "omitted": evaluation["omitted"],
                    "correct_answer": evaluation["correct_answer"],
                    "explanation": question["explanation"],
                }
            }
        )

    def _parse_question_payload(self, exam_id, current_question=None):
        parser = QuestionPayloadParser(current_app.config["MEDIA_ROOT"], self.services)
        return parser.parse(request, exam_id, current_question=current_question)

    def _save_asset_file(self, exam_id, file_storage):
        parser = QuestionPayloadParser(current_app.config["MEDIA_ROOT"], self.services)
        return parser.save_asset_file(exam_id, file_storage)

    def _validate_hotspot_asset_file(self, file_storage):
        parser = QuestionPayloadParser(current_app.config["MEDIA_ROOT"], self.services)
        return parser.validate_hotspot_asset_file(file_storage)

    def _serialize_question_summary(self, question, user):
        return {
            "id": question["id"],
            "exam_id": question["exam_id"],
            "title": (question.get("title") or "").strip(),
            "type": question["type"],
            "difficulty": question.get("difficulty") or "intermediate",
            "status": question.get("status") or "active",
            "position": question.get("position") or 0,
            "tags": question.get("tags", []),
            "topics": question.get("topics", []),
            "option_count": len(question.get("options", [])),
            "asset_count": len(question.get("assets", [])),
            "updated_at": question.get("updated_at"),
            "created_at": question.get("created_at"),
            "can_edit": self.user_manager.user_has_role(user, "reviewer"),
            "can_delete": self.user_manager.user_has_role(user, "examiner"),
        }
