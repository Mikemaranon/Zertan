import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.data_m import DBManager
from app.web_server.server import create_app


class ExamsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-exams-api-")
        self.addCleanup(self.temp_dir.cleanup)
        self._set_env("ZERTAN_DATA_DIR", self.temp_dir.name)
        self._set_env("ZERTAN_DB_PATH", str(Path(self.temp_dir.name) / "database" / "test.db"))
        self._set_env("ZERTAN_MEDIA_ROOT", str(Path(self.temp_dir.name) / "assets"))
        self._set_env("ZERTAN_SEED_DEMO_CONTENT", "0")
        self._set_env("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", "exams-api-admin-password")
        self.addCleanup(self._restore_env)

        self.app = create_app(run_server=False)
        self.db = DBManager()
        self.media_root = Path(os.environ["ZERTAN_MEDIA_ROOT"])

        self.admin = self.db.users.get_by_login_name("admin")
        self.examiner = self._create_user("catalog.examiner", "Catalog Examiner", role="examiner")
        self.reviewer = self._create_user("catalog.reviewer", "Catalog Reviewer", role="reviewer")
        self.student = self._create_user("catalog.student", "Catalog Student", role="user")
        self.outsider = self._create_user("catalog.outsider", "Catalog Outsider", role="user")

        self.group_alpha = self.db.groups.create(
            "Alpha Scope",
            user_ids=[self.examiner["id"], self.reviewer["id"], self.student["id"]],
        )
        self.group_beta = self.db.groups.create(
            "Beta Scope",
            user_ids=[self.outsider["id"]],
        )

    def test_exam_list_respects_scope_and_management_flags(self):
        global_exam_id = self._create_exam("GLB-100")
        alpha_exam_id = self._create_exam("ALPHA-100", group_ids=[self.group_alpha["id"]])
        self._create_exam("BETA-100", group_ids=[self.group_beta["id"]])

        with self.app.test_client() as client:
            self._login(client, "catalog.examiner")
            response = client.get("/api/exams")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        exams_by_code = {item["code"]: item for item in payload["exams"]}

        self.assertEqual(set(exams_by_code), {"GLB-100", "ALPHA-100"})
        self.assertFalse(payload["scope_permissions"]["allow_global"])
        self.assertTrue(payload["scope_permissions"]["allow_groups"])
        self.assertEqual([group["id"] for group in payload["scope_options"]], [self.group_alpha["id"]])
        self.assertFalse(exams_by_code["GLB-100"]["can_manage"])
        self.assertTrue(exams_by_code["ALPHA-100"]["can_manage"])
        self.assertEqual(exams_by_code["ALPHA-100"]["id"], alpha_exam_id)
        self.assertEqual(exams_by_code["GLB-100"]["id"], global_exam_id)

    def test_examiner_can_create_and_update_exam_within_scope(self):
        with self.app.test_client() as client:
            self._login(client, "catalog.examiner")
            create_response = client.post(
                "/api/exams",
                json={
                    "code": "EXM-200",
                    "title": "Examiner Managed Exam",
                    "provider": "Zertan",
                    "description": "Scoped exam created through the API.",
                    "difficulty": "advanced",
                    "status": "published",
                    "tags": ["api", "scope"],
                    "group_ids": [self.group_alpha["id"]],
                },
            )

            self.assertEqual(create_response.status_code, 201)
            exam_id = create_response.get_json()["exam"]["id"]

            update_response = client.put(
                f"/api/exams/{exam_id}",
                json={
                    "code": "EXM-200",
                    "title": "Examiner Managed Exam Updated",
                    "provider": "Zertan",
                    "description": "Updated description.",
                    "difficulty": "intermediate",
                    "status": "draft",
                    "tags": ["api", "updated"],
                    "group_ids": [self.group_alpha["id"]],
                },
            )

        self.assertEqual(update_response.status_code, 200)
        updated_exam = self.db.exams.get(exam_id)
        self.assertEqual(updated_exam["title"], "Examiner Managed Exam Updated")
        self.assertEqual(updated_exam["description"], "Updated description.")
        self.assertEqual(updated_exam["status"], "draft")
        self.assertEqual(updated_exam["group_ids"], [self.group_alpha["id"]])
        self.assertEqual(updated_exam["tags"], ["api", "updated"])

    def test_reviewer_cannot_create_exam(self):
        with self.app.test_client() as client:
            self._login(client, "catalog.reviewer")
            response = client.post(
                "/api/exams",
                json={
                    "code": "REV-100",
                    "title": "Reviewer should fail",
                    "provider": "Zertan",
                    "group_ids": [self.group_alpha["id"]],
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "Forbidden")

    def test_study_mode_and_builder_meta_hide_solutions_for_regular_user(self):
        exam_id = self._create_exam("STUDY-100", group_ids=[self.group_alpha["id"]])
        self.db.questions.create(
            exam_id,
            {
                "type": "single_select",
                "title": "Public study question",
                "statement": "Which answer remains hidden in study mode?",
                "explanation": "Correct answers should not be exposed before checking.",
                "difficulty": "intermediate",
                "status": "active",
                "position": 1,
                "tags": ["catalog"],
                "topics": ["visibility"],
                "options": [
                    {"key": "A", "text": "Hidden", "is_correct": True},
                    {"key": "B", "text": "Visible", "is_correct": False},
                ],
            },
        )

        with self.app.test_client() as client:
            self._login(client, "catalog.student")
            study_response = client.get(f"/api/exams/{exam_id}/study")
            meta_response = client.get(f"/api/exams/{exam_id}/builder-meta")

        self.assertEqual(study_response.status_code, 200)
        self.assertEqual(meta_response.status_code, 200)
        study_payload = study_response.get_json()
        public_question = study_payload["questions"][0]

        self.assertFalse(study_payload["exam"]["can_edit_questions"])
        self.assertEqual(meta_response.get_json()["builder_meta"]["question_types"], ["single_select"])
        self.assertEqual(meta_response.get_json()["builder_meta"]["tags"], ["catalog"])
        self.assertEqual(meta_response.get_json()["builder_meta"]["topics"], ["visibility"])
        self.assertTrue(all("is_correct" not in option for option in public_question["options"]))

    def test_build_attempt_creates_fixed_attempt_for_accessible_exam(self):
        exam_id = self._create_exam("BUILD-100", group_ids=[self.group_alpha["id"]])
        for index in range(1, 4):
            self.db.questions.create(
                exam_id,
                {
                    "type": "single_select",
                    "title": f"Attempt question {index}",
                    "statement": f"Prompt {index}",
                    "explanation": f"Explanation {index}",
                    "difficulty": "intermediate",
                    "status": "active",
                    "position": index,
                    "tags": ["attempts"],
                    "topics": ["builder"],
                    "options": [
                        {"key": "A", "text": "Correct", "is_correct": True},
                        {"key": "B", "text": "Incorrect", "is_correct": False},
                    ],
                },
            )

        with self.app.test_client() as client:
            self._login(client, "catalog.student")
            response = client.post(
                f"/api/exams/{exam_id}/builder",
                json={
                    "question_count": 2,
                    "random_order": False,
                    "question_types": {"include": ["single_select"], "exclude": []},
                    "tags": {"include": ["attempts"], "exclude": []},
                    "topics": {"include": ["builder"], "exclude": []},
                },
            )

        self.assertEqual(response.status_code, 201)
        attempt_id = response.get_json()["attempt_id"]
        attempt = self.db.attempts.get_attempt(attempt_id)
        attempt_questions = self.db.attempts.get_attempt_questions(attempt_id)

        self.assertEqual(attempt["user_id"], self.student["id"])
        self.assertEqual(attempt["question_count"], 2)
        self.assertEqual(len(attempt_questions), 2)

    def test_delete_exam_removes_assets_and_cleanup_directories(self):
        exam_id = self._create_exam("DEL-100")
        asset_dir = self.media_root / "questions" / str(exam_id)
        asset_dir.mkdir(parents=True, exist_ok=True)
        asset_path = asset_dir / "diagram.png"
        asset_path.write_bytes(b"fake-image")

        import_dir = self.media_root / "imports" / "del-100"
        export_dir = self.media_root / "exams" / "del-100"
        import_dir.mkdir(parents=True, exist_ok=True)
        export_dir.mkdir(parents=True, exist_ok=True)
        (import_dir / "package.txt").write_text("import data", encoding="utf-8")
        (export_dir / "package.txt").write_text("export data", encoding="utf-8")

        self.db.questions.create(
            exam_id,
            {
                "type": "single_select",
                "title": "Asset cleanup question",
                "statement": "Should exam deletion remove uploaded assets?",
                "explanation": "Yes, exam-owned assets should be deleted.",
                "difficulty": "intermediate",
                "status": "active",
                "position": 1,
                "tags": ["cleanup"],
                "topics": ["assets"],
                "assets": [
                    {
                        "asset_type": "image",
                        "file_path": f"questions/{exam_id}/diagram.png",
                        "meta": {"alt": "Cleanup diagram"},
                    }
                ],
                "options": [
                    {"key": "A", "text": "Yes", "is_correct": True},
                    {"key": "B", "text": "No", "is_correct": False},
                ],
            },
        )

        with self.app.test_client() as client:
            self._login(client, "admin", password="exams-api-admin-password")
            response = client.delete(f"/api/exams/{exam_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.db.exams.get(exam_id))
        self.assertFalse(asset_path.exists())
        self.assertFalse(import_dir.exists())
        self.assertFalse(export_dir.exists())

    def _create_exam(self, code, group_ids=None):
        return self.db.exams.create(
            {
                "code": code,
                "title": f"Exam {code}",
                "provider": "Zertan",
                "description": "Exam API integration test.",
                "difficulty": "intermediate",
                "status": "published",
                "tags": ["catalog"],
                "group_ids": group_ids or [],
            },
            self.admin["id"],
            allowed_group_ids=[self.group_alpha["id"], self.group_beta["id"]],
            allow_global=True,
        )

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
