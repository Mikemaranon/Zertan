# api_m/domains/exams_api.py

import shutil
from pathlib import Path

from flask import current_app, request

from api_m.domains.base_api import BaseAPI
from services_m import AttemptService, build_public_question
from storage_paths import resolve_stored_path


class ExamsAPI(BaseAPI):
    def register(self):
        self.app.add_url_rule("/api/exams", endpoint="api_exams_list", view_func=self.list_exams, methods=["GET"])
        self.app.add_url_rule("/api/exams", endpoint="api_exams_create", view_func=self.create_exam, methods=["POST"])
        self.app.add_url_rule("/api/exams/<int:exam_id>", endpoint="api_exams_get", view_func=self.get_exam, methods=["GET"])
        self.app.add_url_rule("/api/exams/<int:exam_id>", endpoint="api_exams_update", view_func=self.update_exam, methods=["PUT"])
        self.app.add_url_rule("/api/exams/<int:exam_id>", endpoint="api_exams_delete", view_func=self.delete_exam, methods=["DELETE"])
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
        exams = []
        scope_options = self.list_exam_scope_options_for_user(user)
        allow_global_scope = self.user_is_administrator(user)
        for exam in self.db.exams.list_all(user_id=user["id"], is_administrator=self.user_is_administrator(user)):
            enriched_exam = dict(exam)
            enriched_exam["can_manage"] = self.user_manager.user_has_role(user, "examiner") and self.user_can_manage_exam(user, exam)
            enriched_exam["can_edit_questions"] = self.user_manager.user_has_role(user, "reviewer") and self.user_can_manage_exam(user, exam)
            enriched_exam["can_export_package"] = self.user_manager.user_has_role(user, "examiner") and self.user_can_manage_exam(user, exam)
            exams.append(enriched_exam)
        return self.ok(
            {
                "exams": exams,
                "user": user,
                "scope_options": scope_options,
                "scope_permissions": {
                    "allow_global": allow_global_scope,
                    "allow_groups": bool(scope_options),
                },
            }
        )

    def create_exam(self):
        user, error = self.auth_user(request, min_role="examiner")
        if error:
            return error
        payload = request.get_json() or {}
        required = ["code", "title", "provider"]
        if any(not str(payload.get(field, "")).strip() for field in required):
            return self.error("Code, title, and provider are required.", 400)
        try:
            exam_id = self.db.exams.create(
                payload,
                user["id"],
                allowed_group_ids=[group["id"] for group in self.list_exam_scope_options_for_user(user)],
                allow_global=self.user_is_administrator(user),
            )
        except ValueError as exc:
            return self.error(str(exc), 400)
        return self.ok({"exam": self.db.exams.get(exam_id)}, 201)

    def get_exam(self, exam_id):
        user, error = self.auth_user(request)
        if error:
            return error
        exam, exam_error = self.get_accessible_exam(user, exam_id)
        if exam_error:
            return exam_error
        exam["builder_meta"] = self.db.exams.list_builder_metadata(exam_id)
        exam["can_manage"] = self.user_manager.user_has_role(user, "examiner") and self.user_can_manage_exam(user, exam)
        exam["can_edit_questions"] = self.user_manager.user_has_role(user, "reviewer") and self.user_can_manage_exam(user, exam)
        exam["can_export_package"] = self.user_manager.user_has_role(user, "examiner") and self.user_can_manage_exam(user, exam)
        return self.ok({"exam": exam})

    def update_exam(self, exam_id):
        user, error = self.auth_user(request, min_role="examiner")
        if error:
            return error
        exam, exam_error = self.get_accessible_exam(user, exam_id)
        if exam_error:
            return exam_error
        if not self.user_can_manage_exam(user, exam):
            return self.error("Forbidden", 403)
        payload = request.get_json() or {}
        required = ["code", "title", "provider"]
        if any(not str(payload.get(field, "")).strip() for field in required):
            return self.error("Code, title, and provider are required.", 400)
        try:
            self.db.exams.update(
                exam_id,
                payload,
                allowed_group_ids=[group["id"] for group in self.list_exam_scope_options_for_user(user)],
                allow_global=self.user_is_administrator(user),
            )
        except ValueError as exc:
            return self.error(str(exc), 400)
        return self.ok({"exam": self.db.exams.get(exam_id)})

    def delete_exam(self, exam_id):
        user, error = self.auth_user(request, min_role="examiner")
        if error:
            return error
        exam, exam_error = self.get_accessible_exam(user, exam_id)
        if exam_error:
            return exam_error
        if not self.user_can_manage_exam(user, exam):
            return self.error("Forbidden", 403)

        questions = self.db.questions.list_for_exam(exam_id, include_answers=True, include_archived=True)
        self.db.exams.delete(exam_id)
        self._delete_exam_assets(exam, questions)
        return self.ok({"status": "deleted"})

    def get_study_mode(self, exam_id):
        user, error = self.auth_user(request)
        if error:
            return error
        exam, exam_error = self.get_accessible_exam(user, exam_id)
        if exam_error:
            return exam_error
        questions = [
            build_public_question(question, include_solution=False)
            for question in self.db.questions.list_for_exam(exam_id, include_answers=False)
        ]
        exam["builder_meta"] = self.db.exams.list_builder_metadata(exam_id)
        exam["can_manage"] = self.user_manager.user_has_role(user, "examiner") and self.user_can_manage_exam(user, exam)
        exam["can_edit_questions"] = self.user_manager.user_has_role(user, "reviewer") and self.user_can_manage_exam(user, exam)
        exam["can_export_package"] = self.user_manager.user_has_role(user, "examiner") and self.user_can_manage_exam(user, exam)
        return self.ok({"exam": exam, "questions": questions})

    def get_builder_meta(self, exam_id):
        user, error = self.auth_user(request)
        if error:
            return error
        exam, exam_error = self.get_accessible_exam(user, exam_id)
        if exam_error:
            return exam_error
        return self.ok({"builder_meta": self.db.exams.list_builder_metadata(exam_id), "exam": exam})

    def build_attempt(self, exam_id):
        user, error = self.auth_user(request)
        if error:
            return error
        _, exam_error = self.get_accessible_exam(user, exam_id)
        if exam_error:
            return exam_error
        criteria = request.get_json() or {}
        try:
            attempt_id = AttemptService(self.db).create_attempt(exam_id, user["id"], criteria)
        except ValueError as exc:
            return self.error(str(exc), 400)
        return self.ok({"attempt_id": attempt_id}, 201)

    def _delete_exam_assets(self, exam, questions):
        app_root = Path(current_app.config["APP_ROOT"]).resolve()
        media_root = Path(current_app.config["MEDIA_ROOT"]).resolve()
        asset_paths = set()

        for question in questions:
            for asset in question.get("assets", []):
                file_path = asset.get("file_path")
                if not file_path:
                    continue
                absolute_path = resolve_stored_path(file_path, media_root=media_root, app_root=app_root)
                if absolute_path and absolute_path.is_file() and self._path_is_within_root(absolute_path, media_root):
                    asset_paths.add(absolute_path)

        for asset_path in asset_paths:
            try:
                asset_path.unlink(missing_ok=True)
            except OSError:
                continue

        cleanup_dirs = [
            media_root / "questions" / str(exam["id"]),
            media_root / "imports" / exam["code"].lower(),
            media_root / "exams" / exam["code"].lower(),
        ]
        for directory in cleanup_dirs:
            if directory.exists():
                shutil.rmtree(directory, ignore_errors=True)

    def _path_is_within_root(self, candidate_path, root_path):
        try:
            candidate_path.relative_to(root_path.resolve())
            return True
        except ValueError:
            return False
