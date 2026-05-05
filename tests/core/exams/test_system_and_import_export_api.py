import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.data_m import DBManager
from app.web_server.server import create_app


class SystemAndImportExportApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-system-import-api-")
        self.addCleanup(self.temp_dir.cleanup)
        self._set_env("ZERTAN_DATA_DIR", self.temp_dir.name)
        self._set_env("ZERTAN_DB_PATH", str(Path(self.temp_dir.name) / "database" / "test.db"))
        self._set_env("ZERTAN_MEDIA_ROOT", str(Path(self.temp_dir.name) / "assets"))
        self._set_env("ZERTAN_SEED_DEMO_CONTENT", "0")
        self._set_env("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", "system-import-admin-password")
        self.addCleanup(self._restore_env)

        self.app = create_app(run_server=False)
        self.db = DBManager()
        self.admin = self.db.users.get_by_login_name("admin")
        self.examiner = self._create_user("system.examiner", "System Examiner", role="examiner")
        self.outside_examiner = self._create_user("system.outside", "Outside Examiner", role="examiner")
        self.user = self._create_user("system.user", "System User", role="user")
        self.group_alpha = self.db.groups.create(
            "System Alpha",
            user_ids=[self.examiner["id"], self.user["id"]],
        )
        self.group_beta = self.db.groups.create(
            "System Beta",
            user_ids=[self.outside_examiner["id"]],
        )
        self.exam_id = self.db.exams.create(
            {
                "code": "IMP-100",
                "title": "Import Export Exam",
                "provider": "Zertan",
                "description": "Import/export API integration test.",
                "difficulty": "intermediate",
                "status": "published",
                "tags": ["packages"],
                "group_ids": [self.group_alpha["id"]],
            },
            self.admin["id"],
            allowed_group_ids=[self.group_alpha["id"]],
            allow_global=True,
        )
        self.db.questions.create(
            self.exam_id,
            {
                "type": "single_select",
                "title": "Export question",
                "statement": "Can the package be exported?",
                "explanation": "Yes, by authorized roles.",
                "difficulty": "intermediate",
                "status": "active",
                "position": 1,
                "tags": ["packages"],
                "topics": ["export"],
                "options": [
                    {"key": "A", "text": "Yes", "is_correct": True},
                    {"key": "B", "text": "No", "is_correct": False},
                ],
            },
        )

    def test_system_connection_info_and_alias_management(self):
        with patch(
            "app.web_server.services_m.connection_info_service.ConnectionInfoService.get_connection_info",
            return_value={
                "connection": {"listen_host": "0.0.0.0", "listen_port": 5050},
                "primary_endpoint": {"url": "http://127.0.0.1:5050"},
                "aliases": [],
            },
        ), patch(
            "app.web_server.services_m.connection_info_service.ConnectionInfoService._verify_endpoint",
            return_value={"status": "verified", "message": "Confirmed", "resolved_ips": ["127.0.0.1"]},
        ):
            with self.app.test_client() as client:
                self._login(client, "admin", password="system-import-admin-password")
                info_response = client.get("/api/system/connection-info")
                create_alias_response = client.post(
                    "/api/system/connection-info/aliases",
                    json={"host": "127.0.0.1", "label": "Loopback", "port": 5050},
                )
                alias_id = create_alias_response.get_json()["alias"]["id"]
                delete_alias_response = client.delete(f"/api/system/connection-info/aliases/{alias_id}")

        self.assertEqual(info_response.status_code, 200)
        self.assertTrue(info_response.get_json()["can_manage_aliases"])
        self.assertEqual(create_alias_response.status_code, 201)
        self.assertEqual(create_alias_response.get_json()["alias"]["verification_status"], "verified")
        self.assertEqual(delete_alias_response.status_code, 200)

    def test_regular_user_cannot_manage_aliases(self):
        with self.app.test_client() as client:
            self._login(client, "system.user")
            response = client.post(
                "/api/system/connection-info/aliases",
                json={"host": "127.0.0.1", "label": "Blocked", "port": 5050},
            )

        self.assertEqual(response.status_code, 403)

    def test_alias_management_validates_input_duplicates_and_missing_aliases(self):
        with patch(
            "app.web_server.services_m.connection_info_service.ConnectionInfoService._verify_endpoint",
            return_value={"status": "verified", "message": "Confirmed", "resolved_ips": ["127.0.0.1"]},
        ):
            with self.app.test_client() as client:
                self._login(client, "admin", password="system-import-admin-password")
                invalid_host_response = client.post(
                    "/api/system/connection-info/aliases",
                    json={"host": "http://bad-host/path", "label": "Invalid", "port": 5050},
                )
                invalid_port_response = client.post(
                    "/api/system/connection-info/aliases",
                    json={"host": "127.0.0.1", "label": "Invalid Port", "port": "nope"},
                )
                first_create = client.post(
                    "/api/system/connection-info/aliases",
                    json={"host": "127.0.0.1", "label": "Loopback", "port": 5050},
                )
                duplicate_response = client.post(
                    "/api/system/connection-info/aliases",
                    json={"host": "127.0.0.1", "label": "Loopback Duplicate", "port": 5050},
                )
                missing_delete_response = client.delete("/api/system/connection-info/aliases/99999")

        self.assertEqual(invalid_host_response.status_code, 400)
        self.assertEqual(
            invalid_host_response.get_json()["error"],
            "Host must be a bare IPv4 address or DNS name without protocol or path.",
        )
        self.assertEqual(invalid_port_response.status_code, 400)
        self.assertEqual(invalid_port_response.get_json()["error"], "Port must be a valid integer.")
        self.assertEqual(first_create.status_code, 201)
        self.assertEqual(duplicate_response.status_code, 400)
        self.assertEqual(
            duplicate_response.get_json()["error"],
            "That host already exists in the shared alias list.",
        )
        self.assertEqual(missing_delete_response.status_code, 404)
        self.assertEqual(missing_delete_response.get_json()["error"], "Alias not found.")

    def test_export_exam_returns_zip_for_authorized_examiner(self):
        with self.app.test_client() as client:
            self._login(client, "system.examiner")
            response = client.get(f"/api/import-export/exams/{self.exam_id}/export")

        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "application/zip")
            self.assertIn("imp-100-package.zip", response.headers.get("Content-Disposition", "").lower())
            with zipfile.ZipFile(io.BytesIO(response.data), "r") as archive:
                names = set(archive.namelist())
            self.assertIn("exam-package/exam.json", names)
            self.assertIn("exam-package/questions/q_0001.json", names)
        finally:
            response.close()

    def test_export_exam_rejects_users_without_management_scope(self):
        global_exam_id = self.db.exams.create(
            {
                "code": "IMP-150",
                "title": "Global Export Exam",
                "provider": "Zertan",
                "description": "Global exam should require admin for export management.",
                "difficulty": "intermediate",
                "status": "published",
                "tags": ["packages"],
            },
            self.admin["id"],
            allow_global=True,
        )
        self.db.questions.create(
            global_exam_id,
            {
                "type": "single_select",
                "title": "Global export question",
                "statement": "Can this exam be exported by non-admin users?",
                "explanation": "No, not when it has no group management scope.",
                "difficulty": "intermediate",
                "status": "active",
                "position": 1,
                "tags": ["packages"],
                "topics": ["export"],
                "options": [
                    {"key": "A", "text": "No", "is_correct": True},
                    {"key": "B", "text": "Yes", "is_correct": False},
                ],
            },
        )

        with self.app.test_client() as client:
            self._login(client, "system.user")
            regular_user_response = client.get(f"/api/import-export/exams/{self.exam_id}/export")

        with self.app.test_client() as client:
            self._login(client, "system.outside")
            outside_examiner_response = client.get(f"/api/import-export/exams/{self.exam_id}/export")

        with self.app.test_client() as client:
            self._login(client, "system.examiner")
            no_manage_scope_response = client.get(f"/api/import-export/exams/{global_exam_id}/export")

        self.assertEqual(regular_user_response.status_code, 403)
        self.assertEqual(outside_examiner_response.status_code, 403)
        self.assertEqual(no_manage_scope_response.status_code, 403)

    def test_import_exam_rejects_invalid_upload_and_accepts_valid_package(self):
        with self.app.test_client() as client:
            self._login(client, "system.examiner")
            invalid_response = client.post(
                "/api/import-export/exams/import",
                data={"package": (io.BytesIO(b"not-a-zip"), "broken.txt")},
                content_type="multipart/form-data",
            )
            valid_response = client.post(
                "/api/import-export/exams/import",
                data={
                    "scope_mode": "groups",
                    "group_ids": str(self.group_alpha["id"]),
                    "package": (self._build_import_package(), "import-package.zip"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(valid_response.status_code, 201)
        imported_exam = valid_response.get_json()["exam"]
        self.assertEqual(imported_exam["code"], "IMP-200")
        self.assertEqual(imported_exam["group_ids"], [self.group_alpha["id"]])
        stored_questions = self.db.questions.list_for_exam(imported_exam["id"], include_answers=True)
        self.assertEqual(len(stored_questions), 1)

    def test_import_exam_rejects_missing_groups_duplicate_code_and_unknown_group_codes(self):
        with self.app.test_client() as client:
            self._login(client, "system.examiner")
            missing_groups_response = client.post(
                "/api/import-export/exams/import",
                data={
                    "scope_mode": "groups",
                    "package": (self._build_import_package(code="IMP-300"), "missing-groups.zip"),
                },
                content_type="multipart/form-data",
            )
            duplicate_code_response = client.post(
                "/api/import-export/exams/import",
                data={
                    "scope_mode": "groups",
                    "group_ids": [str(self.group_alpha["id"])],
                    "package": (self._build_import_package(code="IMP-100"), "duplicate-code.zip"),
                },
                content_type="multipart/form-data",
            )
            unknown_group_code_response = client.post(
                "/api/import-export/exams/import",
                data={
                    "package": (
                        self._build_import_package(code="IMP-301", scope_mode="groups", group_codes=["missing-group"]),
                        "unknown-groups.zip",
                    ),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(missing_groups_response.status_code, 400)
        self.assertEqual(missing_groups_response.get_json()["error"], "Select at least one group for this imported exam.")
        self.assertEqual(duplicate_code_response.status_code, 400)
        self.assertEqual(duplicate_code_response.get_json()["error"], "An exam with this code already exists.")
        self.assertEqual(unknown_group_code_response.status_code, 400)
        self.assertEqual(
            unknown_group_code_response.get_json()["error"],
            "The imported package references groups that do not exist in this domain.",
        )

    def test_import_exam_requires_examiner_role(self):
        with self.app.test_client() as client:
            self._login(client, "system.user")
            response = client.post(
                "/api/import-export/exams/import",
                data={
                    "scope_mode": "groups",
                    "group_ids": [str(self.group_alpha["id"])],
                    "package": (self._build_import_package(code="IMP-302"), "blocked-import.zip"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 403)

    def _build_import_package(self, *, code="IMP-200", scope_mode=None, group_codes=None):
        buffer = io.BytesIO()
        exam_document = {
            "code": code,
            "title": "Imported Package Exam",
            "provider": "Zertan",
            "description": "Imported through API integration test.",
            "difficulty": "intermediate",
            "status": "published",
            "tags": ["packages"],
        }
        if scope_mode is not None:
            exam_document["scope_mode"] = scope_mode
        if group_codes is not None:
            exam_document["group_codes"] = group_codes
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "exam-package/exam.json",
                json.dumps(exam_document),
            )
            archive.writestr(
                "exam-package/questions/q_0001.json",
                json.dumps(
                    {
                        "type": "single_select",
                        "statement": "Which endpoint imports packages?",
                        "explanation": "The import/export API endpoint handles package import.",
                        "difficulty": "intermediate",
                        "status": "active",
                        "tags": ["packages"],
                        "topics": ["import"],
                        "options": [
                            {"key": "A", "text": "Import/export API", "is_correct": True},
                            {"key": "B", "text": "Statistics API", "is_correct": False},
                        ],
                    }
                ),
            )
        buffer.seek(0)
        return buffer

    def _create_user(self, login_name, display_name, *, role):
        self.db.users.create(
            login_name,
            display_name,
            self._password_hash(),
            role=role,
            status="active",
        )
        return self.db.users.get_by_login_name(login_name)

    def _login(self, client, login_name, password="valid-password"):
        response = client.post("/api/auth/login", json={"login_name": login_name, "password": password})
        self.assertEqual(response.status_code, 200)

    def _password_hash(self):
        from werkzeug.security import generate_password_hash

        return generate_password_hash("valid-password")

    def _set_env(self, key, value):
        original = os.environ.get(key)
        os.environ[key] = value
        setattr(self, f"_orig_{key}", original)

    def _restore_env(self):
        for key in (
            "ZERTAN_DATA_DIR",
            "ZERTAN_DB_PATH",
            "ZERTAN_MEDIA_ROOT",
            "ZERTAN_SEED_DEMO_CONTENT",
            "ZERTAN_BOOTSTRAP_ADMIN_PASSWORD",
        ):
            original = getattr(self, f"_orig_{key}", None)
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


if __name__ == "__main__":
    unittest.main()
