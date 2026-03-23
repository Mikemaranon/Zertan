# api_m/domains/import_export_api.py

import shutil

from flask import after_this_request, request, send_file

from api_m.domains.base_api import BaseAPI


class ImportExportAPI(BaseAPI):
    def register(self):
        self.app.add_url_rule(
            "/api/import-export/exams/import",
            endpoint="api_import_export_import_exam",
            view_func=self.import_exam,
            methods=["POST"],
        )
        self.app.add_url_rule(
            "/api/import-export/exams/<int:exam_id>/export",
            endpoint="api_import_export_export_exam",
            view_func=self.export_exam,
            methods=["GET"],
        )

    def import_exam(self):
        user, error = self.auth_user(request, min_role="examiner")
        if error:
            return error
        uploaded_file = request.files.get("package")
        if not uploaded_file or not uploaded_file.filename or not uploaded_file.filename.lower().endswith(".zip"):
            return self.error("Upload a .zip exam package.", 400)
        try:
            scope_group_ids = request.form.getlist("group_ids")
            exam_id = self.services.packages.import_exam(
                uploaded_file,
                user["id"],
                group_ids=scope_group_ids,
                scope_mode=request.form.get("scope_mode"),
                allowed_group_ids=[group["id"] for group in self.list_exam_scope_options_for_user(user)],
                allow_global=self.user_is_administrator(user),
            )
        except ValueError as exc:
            return self.error(str(exc), 400)
        return self.ok({"exam": self.db.exams.get(exam_id)}, 201)

    def export_exam(self, exam_id):
        user, error = self.auth_user(request, min_role="examiner")
        if error:
            return error
        exam, exam_error = self.get_accessible_exam(user, exam_id)
        if exam_error:
            return exam_error
        if not self.user_can_manage_exam(user, exam):
            return self.error("Forbidden", 403)
        zip_path, temp_dir = self.services.packages.export_exam(exam_id)

        @after_this_request
        def cleanup(response):
            shutil.rmtree(temp_dir, ignore_errors=True)
            return response

        return send_file(zip_path, as_attachment=True, download_name=zip_path.name)
