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


class AttemptsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-attempts-api-")
        self.addCleanup(self.temp_dir.cleanup)
        self._set_env("ZERTAN_DATA_DIR", self.temp_dir.name)
        self._set_env("ZERTAN_DB_PATH", str(Path(self.temp_dir.name) / "database" / "test.db"))
        self._set_env("ZERTAN_MEDIA_ROOT", str(Path(self.temp_dir.name) / "assets"))
        self._set_env("ZERTAN_SEED_DEMO_CONTENT", "0")
        self._set_env("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", "attempts-api-admin-password")
        self.addCleanup(self._restore_env)

        self.app = create_app(run_server=False)
        self.db = DBManager()
        self.admin = self.db.users.get_by_login_name("admin")
        self.examiner = self._create_user("attempt.examiner", "Attempt Examiner", role="examiner")
        self.owner = self._create_user("attempt.owner", "Attempt Owner", role="user")
        self.outsider = self._create_user("attempt.outsider", "Attempt Outsider", role="user")

        self.group_alpha = self.db.groups.create(
            "Attempt Alpha",
            user_ids=[self.examiner["id"], self.owner["id"]],
        )
        self.exam_id = self.db.exams.create(
            {
                "code": "ATT-100",
                "title": "Attempt API Exam",
                "provider": "Zertan",
                "description": "Exercise attempt API behavior.",
                "difficulty": "intermediate",
                "status": "published",
                "tags": ["attempts"],
                "group_ids": [self.group_alpha["id"]],
            },
            self.admin["id"],
            allowed_group_ids=[self.group_alpha["id"]],
            allow_global=True,
        )
        self.question_id = self.db.questions.create(
            self.exam_id,
            {
                "type": "single_select",
                "title": "Attempt question",
                "statement": "Should attempts preserve answers?",
                "explanation": "Yes, saved answers should reappear across requests.",
                "difficulty": "intermediate",
                "status": "active",
                "position": 1,
                "tags": ["attempts"],
                "topics": ["runner"],
                "options": [
                    {"key": "A", "text": "Yes", "is_correct": True},
                    {"key": "B", "text": "No", "is_correct": False},
                ],
            },
        )
        self.attempt_id = self.db.attempts.create(self.exam_id, self.owner["id"], {}, 1, random_order=False)
        self.db.attempts.add_questions(
            self.attempt_id,
            [
                {
                    "question_id": self.question_id,
                    "snapshot": self.db.questions.get(self.question_id, include_answers=True),
                }
            ],
        )
        self.attempt_question_id = self.db.attempts.get_attempt_questions(self.attempt_id)[0]["attempt_question_id"]

    def test_owner_can_fetch_save_submit_and_view_result(self):
        with self.app.test_client() as client:
            self._login(client, "attempt.owner")
            get_response = client.get(f"/api/attempts/{self.attempt_id}?page=1")
            save_response = client.post(
                f"/api/attempts/{self.attempt_id}/answers",
                json={
                    "answers": [
                        {
                            "attempt_question_id": self.attempt_question_id,
                            "response": {"selected": "A"},
                        }
                    ]
                },
            )
            submit_response = client.post(f"/api/attempts/{self.attempt_id}/submit", json={})
            result_response = client.get(f"/api/attempts/{self.attempt_id}/result")

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.get_json()["questions"][0]["question"]["statement"], "Should attempts preserve answers?")
        self.assertEqual(save_response.status_code, 200)
        self.assertEqual(submit_response.status_code, 200)
        self.assertEqual(result_response.status_code, 200)

        attempt = self.db.attempts.get_attempt(self.attempt_id)
        self.assertEqual(attempt["status"], "submitted")
        self.assertEqual(attempt["correct_count"], 1)
        self.assertEqual(result_response.get_json()["questions"][0]["result"]["is_correct"], True)

    def test_examiner_with_scope_can_access_other_users_attempt(self):
        with self.app.test_client() as client:
            self._login(client, "attempt.examiner")
            response = client.get(f"/api/attempts/{self.attempt_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["attempt"]["user_id"], self.owner["id"])

    def test_outsider_cannot_access_other_users_attempt(self):
        with self.app.test_client() as client:
            self._login(client, "attempt.outsider")
            response = client.get(f"/api/attempts/{self.attempt_id}")

        self.assertEqual(response.status_code, 403)

    def test_submitted_attempt_rejects_new_saves(self):
        self.db.attempts.mark_submitted(self.attempt_id, 0, 0, 1, 0)

        with self.app.test_client() as client:
            self._login(client, "attempt.owner")
            response = client.post(
                f"/api/attempts/{self.attempt_id}/answers",
                json={"answers": [{"attempt_question_id": self.attempt_question_id, "response": {"selected": "B"}}]},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Attempt is already submitted.")

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
