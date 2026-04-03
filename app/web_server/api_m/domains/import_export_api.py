# api_m/domains/import_export_api.py

import shutil

from flask import after_this_request, request, send_file

from .base_api import BaseAPI


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
            payload = self.services.packages.import_exam_for_user(
                uploaded_file,
                actor_user=user,
                explicit_group_ids=request.form.getlist("group_ids"),
                explicit_scope_mode=request.form.get("scope_mode"),
            )
        except ValueError as exc:
            return self.error(str(exc), 400)
        return self.ok(payload, 201)

    def export_exam(self, exam_id):
        user, error = self.auth_user(request, min_role="examiner")
        if error:
            return error
        try:
            export_bundle = self.services.packages.export_exam_for_user(exam_id, actor_user=user)
        except LookupError as exc:
            return self.error(str(exc), 404)
        except PermissionError as exc:
            return self.error(str(exc), 403)

        @after_this_request
        def cleanup(response):
            shutil.rmtree(export_bundle["temp_dir"], ignore_errors=True)
            return response

        return send_file(
            export_bundle["zip_path"],
            as_attachment=True,
            download_name=export_bundle["download_name"],
        )
