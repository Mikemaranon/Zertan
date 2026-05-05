import io
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.data_m import DBManager
from app.web_server.server import create_app


class AuthAndUserApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-auth-user-api-")
        self.addCleanup(self.temp_dir.cleanup)
        self._set_env("ZERTAN_DATA_DIR", self.temp_dir.name)
        self._set_env("ZERTAN_DB_PATH", str(Path(self.temp_dir.name) / "database" / "test.db"))
        self._set_env("ZERTAN_MEDIA_ROOT", str(Path(self.temp_dir.name) / "assets"))
        self._set_env("ZERTAN_SEED_DEMO_CONTENT", "0")
        self._set_env("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", "auth-user-admin-password")
        self.addCleanup(self._restore_env)

        self.app = create_app(run_server=False)
        self.db = DBManager()
        self.admin = self.db.users.get_by_login_name("admin")
        self.user = self._create_user("api.user", "API User", role="user")
        self.exam_id = self.db.exams.create(
            {
                "code": "USR-100",
                "title": "User Attempts Exam",
                "provider": "Zertan",
                "description": "Exercise user-facing auth endpoints.",
                "difficulty": "intermediate",
                "status": "published",
                "tags": ["auth"],
            },
            self.admin["id"],
            allow_global=True,
        )
        self.question_id = self.db.questions.create(
            self.exam_id,
            {
                "type": "single_select",
                "title": "User attempt question",
                "statement": "Can recent attempts be listed?",
                "explanation": "Yes, once attempt snapshots point to a real question.",
                "difficulty": "intermediate",
                "status": "active",
                "position": 1,
                "tags": ["auth"],
                "topics": ["profile"],
                "options": [
                    {"key": "A", "text": "Yes", "is_correct": True},
                    {"key": "B", "text": "No", "is_correct": False},
                ],
            },
        )
        self._create_recent_attempt(score_percent=75.0, status="submitted")
        self._create_recent_attempt(score_percent=None, status="in_progress")

    def test_login_sets_cookie_and_me_returns_authenticated_user(self):
        with self.app.test_client() as client:
            login_response = client.post(
                "/api/auth/login",
                json={"username": "api.user", "password": "valid-password"},
            )
            me_response = client.get("/api/auth/me")

        self.assertEqual(login_response.status_code, 200)
        self.assertIn("token=", login_response.headers.get("Set-Cookie", ""))
        self.assertEqual(me_response.status_code, 200)
        payload = me_response.get_json()
        self.assertEqual(payload["user"]["login_name"], "api.user")
        self.assertEqual(payload["user"]["display_name"], "API User")

    def test_login_rejects_missing_credentials(self):
        with self.app.test_client() as client:
            response = client.post("/api/auth/login", json={"login_name": "", "password": ""})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Login name and password are required.")

    def test_profile_update_changes_display_name_and_password(self):
        with self.app.test_client() as client:
            self._login(client, "api.user")
            response = client.put(
                "/api/auth/profile",
                json={
                    "display_name": "Updated API User",
                    "current_password": "valid-password",
                    "new_password": "new-valid-password",
                    "confirm_password": "new-valid-password",
                },
            )

        self.assertEqual(response.status_code, 200)
        updated_user = self.db.users.get_by_login_name("api.user")
        self.assertEqual(updated_user["display_name"], "Updated API User")

        with self.app.test_client() as client:
            new_login = client.post(
                "/api/auth/login",
                json={"login_name": "api.user", "password": "new-valid-password"},
            )
        self.assertEqual(new_login.status_code, 200)

    def test_avatar_upload_persists_media_file_and_profile_path(self):
        with self.app.test_client() as client:
            self._login(client, "api.user")
            response = client.post(
                "/api/auth/profile/avatar",
                data={
                    "avatar": (io.BytesIO(b"fake-image-bytes"), "profile.png"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        avatar_path = response.get_json()["user"]["avatar_path"]
        self.assertTrue(avatar_path.startswith("profiles/"))
        stored_path = Path(os.environ["ZERTAN_MEDIA_ROOT"]) / avatar_path
        self.assertTrue(stored_path.exists())

    def test_avatar_upload_rejects_non_image_extension(self):
        with self.app.test_client() as client:
            self._login(client, "api.user")
            response = client.post(
                "/api/auth/profile/avatar",
                data={
                    "avatar": (io.BytesIO(b"not-an-image"), "profile.txt"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Unsupported image format.")

    def test_user_endpoints_return_me_and_recent_attempts(self):
        with self.app.test_client() as client:
            self._login(client, "api.user")
            me_response = client.get("/api/users/me")
            attempts_response = client.get("/api/users/recent-attempts")

        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.get_json()["user"]["id"], self.user["id"])
        self.assertEqual(attempts_response.status_code, 200)
        attempts = attempts_response.get_json()["attempts"]
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[0]["status"], "in_progress")
        self.assertEqual(attempts[1]["status"], "submitted")

    def test_logout_clears_cookie_and_session(self):
        with self.app.test_client() as client:
            self._login(client, "api.user")
            session_count_before = self.db.db.execute(
                "SELECT COUNT(*) AS total FROM sessions WHERE user_id = ?",
                (self.user["id"],),
                fetchone=True,
            )[1]["total"]
            response = client.post("/api/auth/logout")

        self.assertEqual(response.status_code, 200)
        self.assertIn("token=;", response.headers.get("Set-Cookie", ""))
        session_count_after = self.db.db.execute(
            "SELECT COUNT(*) AS total FROM sessions WHERE user_id = ?",
            (self.user["id"],),
            fetchone=True,
        )[1]["total"]
        self.assertGreaterEqual(session_count_before, 1)
        self.assertEqual(session_count_after, 0)

    def _create_recent_attempt(self, *, score_percent, status):
        attempt_id = self.db.attempts.create(self.exam_id, self.user["id"], {}, 1, random_order=False)
        self.db.attempts.add_questions(
            attempt_id,
            [
                {
                    "question_id": self.question_id,
                    "snapshot": self.db.questions.get(self.question_id, include_answers=True),
                }
            ],
        )
        if status == "submitted":
            attempt_question_id = self.db.attempts.get_attempt_questions(attempt_id)[0]["attempt_question_id"]
            self.db.attempts.finalize_answer(attempt_question_id, True, 1, False)
            self.db.attempts.mark_submitted(attempt_id, 1, 0, 0, score_percent)
        return attempt_id

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
