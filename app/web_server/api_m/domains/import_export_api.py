# api_m/domains/import_export_api.py

import shutil
from pathlib import Path

from flask import after_this_request, current_app, request, send_file

from api_m.domains.base_api import BaseAPI
from services_m import PackageService


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
        if not uploaded_file or not uploaded_file.filename.endswith(".zip"):
            return self.error("Upload a .zip exam package.", 400)
        try:
            project_root = Path(current_app.root_path).resolve().parents[0]
            exam_id = PackageService(self.db, project_root).import_exam(uploaded_file, user["id"])
        except ValueError as exc:
            return self.error(str(exc), 400)
        return self.ok({"exam": self.db.exams.get(exam_id)}, 201)

    def export_exam(self, exam_id):
        _, error = self.auth_user(request, min_role="examiner")
        if error:
            return error
        exam = self.db.exams.get(exam_id)
        if not exam:
            return self.error("Exam not found.", 404)
        project_root = Path(current_app.root_path).resolve().parents[0]
        zip_path, temp_dir = PackageService(self.db, project_root).export_exam(exam_id)

        @after_this_request
        def cleanup(response):
            shutil.rmtree(temp_dir, ignore_errors=True)
            return response

        return send_file(zip_path, as_attachment=True, download_name=zip_path.name)
