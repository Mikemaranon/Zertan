import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.data_m import DBManager
from app.web_server.server import create_app
from app.web_server.user_m import UserManager


class GlobalExamPermissionsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-global-exam-permissions-")
        self.addCleanup(self.temp_dir.cleanup)
        self._set_env("ZERTAN_DATA_DIR", self.temp_dir.name)
        self._set_env("ZERTAN_DB_PATH", str(Path(self.temp_dir.name) / "database" / "test.db"))
        self._set_env("ZERTAN_MEDIA_ROOT", str(Path(self.temp_dir.name) / "assets"))
        self._set_env("ZERTAN_SEED_DEMO_CONTENT", "0")
        self._set_env("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", "global-admin-password")
        self.addCleanup(self._restore_env)

        self.app = create_app(run_server=False)
        self.db = DBManager()
        self.user_manager = UserManager(db_manager=self.db)

        admin = self.db.users.get_by_login_name("admin")
        self.admin = self.user_manager.public_user(admin)
        self.examiner = self.user_manager.create_user(
            "Global Examiner",
            "global.examiner",
            "examiner-password",
            role="examiner",
            status="active",
        )
        self.exam_id = self.db.exams.create(
            {
                "code": "GLB-200",
                "title": "Global Scope Exam",
                "provider": "Zertan",
                "description": "Global exam used to verify domain-only editing permissions.",
                "difficulty": "intermediate",
                "status": "published",
                "tags": ["global"],
            },
            self.admin["id"],
            allow_global=True,
        )
        self.question_id = self.db.questions.create(
            self.exam_id,
            {
                "type": "single_select",
                "title": "Global question",
                "statement": "Which role can edit a global exam?",
                "explanation": "Only the domain administrator should manage global scope content.",
                "difficulty": "intermediate",
                "status": "active",
                "position": 1,
                "tags": ["permissions"],
                "topics": ["authorization"],
                "options": [
                    {"key": "A", "text": "Administrator", "is_correct": True},
                    {"key": "B", "text": "Examiner", "is_correct": False},
                ],
            },
        )

    def test_examiner_can_view_global_exam_but_cannot_edit_questions(self):
        with self.app.test_client() as client:
            login = client.post(
                "/api/auth/login",
                json={"login_name": "global.examiner", "password": "examiner-password"},
            )
            self.assertEqual(login.status_code, 200)

            exam_response = client.get(f"/api/exams/{self.exam_id}")
            question_workspace_response = client.get(f"/api/exams/{self.exam_id}/questions")
            create_response = client.post(
                f"/api/exams/{self.exam_id}/questions",
                json={
                    "type": "single_select",
                    "title": "Examiner should fail",
                    "statement": "Should be forbidden",
                    "options": [
                        {"key": "A", "text": "Yes", "is_correct": True},
                        {"key": "B", "text": "No", "is_correct": False},
                    ],
                },
            )

        self.assertEqual(exam_response.status_code, 200)
        self.assertFalse(exam_response.get_json()["exam"]["can_edit_questions"])
        self.assertEqual(question_workspace_response.status_code, 403)
        self.assertEqual(create_response.status_code, 403)

    def test_administrator_can_edit_global_exam_questions(self):
        with self.app.test_client() as client:
            login = client.post(
                "/api/auth/login",
                json={"login_name": "admin", "password": "global-admin-password"},
            )
            self.assertEqual(login.status_code, 200)

            exam_response = client.get(f"/api/exams/{self.exam_id}")
            question_workspace_response = client.get(f"/api/exams/{self.exam_id}/questions")

        self.assertEqual(exam_response.status_code, 200)
        self.assertTrue(exam_response.get_json()["exam"]["can_edit_questions"])
        self.assertEqual(question_workspace_response.status_code, 200)
        self.assertEqual(question_workspace_response.get_json()["questions"][0]["id"], self.question_id)

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
