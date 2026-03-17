# api_m/domains/questions_api.py

import json
import os
from pathlib import Path
from uuid import uuid4

from flask import current_app, request
from werkzeug.utils import secure_filename

from api_m.domains.base_api import BaseAPI
from services_m import build_public_question, evaluate_question_response, normalize_question_payload


class QuestionsAPI(BaseAPI):
    def register(self):
        self.app.add_url_rule("/api/questions/<int:question_id>", endpoint="api_questions_get", view_func=self.get_question, methods=["GET"])
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
        if not self.user_manager.user_has_role(user, "reviewer"):
            question = build_public_question(question, include_solution=False)
        return self.ok({"question": question})

    def create_question(self, exam_id):
        user, error = self.auth_user(request, min_role="reviewer")
        if error:
            return error
        exam = self.db.exams.get(exam_id)
        if not exam:
            return self.error("Exam not found.", 404)
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
        self.db.questions.delete(question_id)
        return self.ok({"status": "deleted"})

    def archive_question(self, question_id):
        user, error = self.auth_user(request, min_role="reviewer")
        if error:
            return error
        question = self.db.questions.get(question_id, include_answers=True)
        if not question:
            return self.error("Question not found.", 404)
        self.db.questions.archive(question_id)
        return self.ok({"status": "archived"})

    def check_question(self, question_id):
        user, error = self.auth_user(request)
        if error:
            return error
        question = self.db.questions.get(question_id, include_answers=True)
        if not question:
            return self.error("Question not found.", 404)
        response_payload = (request.get_json() or {}).get("response") or {}
        evaluation = evaluate_question_response(question, response_payload)
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
        if request.content_type and "multipart/form-data" in request.content_type:
            payload = json.loads(request.form.get("payload", "{}"))
        else:
            payload = request.get_json() or {}

        existing_assets = payload.get("assets") or (current_question.get("assets", []) if current_question else [])
        uploaded_asset = request.files.get("asset_file")
        if uploaded_asset and uploaded_asset.filename:
            relative_path = self._save_asset_file(exam_id, uploaded_asset)
            asset_meta = {"alt": payload.get("asset_alt") or uploaded_asset.filename}
            existing_assets = [
                {
                    "asset_type": payload.get("asset_type", "image"),
                    "file_path": relative_path,
                    "meta": asset_meta,
                }
            ]
        payload["assets"] = existing_assets
        return normalize_question_payload(payload)

    def _save_asset_file(self, exam_id, file_storage):
        project_root = Path(current_app.root_path).resolve().parents[0]
        safe_name = secure_filename(file_storage.filename)
        extension = Path(safe_name).suffix
        target_dir = project_root / "web_app" / "static" / "uploads" / "questions" / str(exam_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_name = f"{uuid4().hex}{extension}"
        target_path = target_dir / target_name
        file_storage.save(target_path)
        return str(target_path.relative_to(project_root))
