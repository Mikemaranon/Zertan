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


class LiveExamsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-live-exams-api-")
        self.addCleanup(self.temp_dir.cleanup)
        self._set_env("ZERTAN_DATA_DIR", self.temp_dir.name)
        self._set_env("ZERTAN_DB_PATH", str(Path(self.temp_dir.name) / "database" / "test.db"))
        self._set_env("ZERTAN_MEDIA_ROOT", str(Path(self.temp_dir.name) / "assets"))
        self._set_env("ZERTAN_SEED_DEMO_CONTENT", "0")
        self._set_env("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", "live-exams-admin-password")
        self.addCleanup(self._restore_env)

        self.app = create_app(run_server=False)
        self.db = DBManager()
        self.admin_id = self.db.users.get_by_login_name("admin")["id"]
        self.exam_id = self.db.exams.create(
            {
                "code": "LIV-100",
                "title": "Live Exam Source",
                "provider": "Zertan",
                "description": "Exam used to verify administrator self-assigned live exams.",
                "difficulty": "intermediate",
                "status": "published",
                "tags": ["live-exams"],
            },
            self.admin_id,
            allow_global=True,
        )
        self.db.questions.create(
            self.exam_id,
            {
                "type": "single_select",
                "title": "Live exam question",
                "statement": "Can an administrator start a self-assigned live exam?",
                "explanation": "Yes, if that administrator is an assigned user of the live exam.",
                "difficulty": "intermediate",
                "status": "active",
                "position": 1,
                "tags": ["live-exams"],
                "topics": ["permissions"],
                "options": [
                    {"key": "A", "text": "Yes", "is_correct": True},
                    {"key": "B", "text": "No", "is_correct": False},
                ],
            },
        )
        self.live_exam_id = self.db.live_exams.create(
            {
                "exam_id": self.exam_id,
                "title": "Administrator self-assigned exam",
                "description": "Admin should be able to launch this assignment.",
                "instructions": "Complete the exam normally.",
                "question_count": 1,
                "time_limit_minutes": 20,
                "criteria": {},
            },
            self.admin_id,
        )
        self.db.live_exams.set_assignments(self.live_exam_id, [self.admin_id])

    def test_administrator_sees_and_can_start_self_assigned_live_exam(self):
        with self.app.test_client() as client:
            login = client.post(
                "/api/auth/login",
                json={"login_name": "admin", "password": "live-exams-admin-password"},
            )
            self.assertEqual(login.status_code, 200)

            list_response = client.get("/api/live-exams")
            self.assertEqual(list_response.status_code, 200)
            payload = list_response.get_json()

            self.assertEqual(payload["mode"], "administrator")
            self.assertEqual(len(payload["assignments"]), 1)
            assignment = payload["assignments"][0]
            self.assertEqual(assignment["user_id"], self.admin_id)
            self.assertEqual(assignment["live_exam_id"], self.live_exam_id)
            self.assertEqual(assignment["assignment_status"], "pending")

            start_response = client.post(f"/api/live-exams/assignments/{assignment['assignment_id']}/start")
            self.assertEqual(start_response.status_code, 200)
            attempt_id = start_response.get_json()["attempt_id"]
            self.assertGreater(attempt_id, 0)

            refreshed_response = client.get("/api/live-exams")
            self.assertEqual(refreshed_response.status_code, 200)
            refreshed_assignment = refreshed_response.get_json()["assignments"][0]
            self.assertEqual(refreshed_assignment["assignment_status"], "in_progress")
            self.assertEqual(refreshed_assignment["attempt_id"], attempt_id)

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
