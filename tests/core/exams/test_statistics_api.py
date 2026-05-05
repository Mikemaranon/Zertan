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


class StatisticsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-statistics-api-")
        self.addCleanup(self.temp_dir.cleanup)
        self._set_env("ZERTAN_DATA_DIR", self.temp_dir.name)
        self._set_env("ZERTAN_DB_PATH", str(Path(self.temp_dir.name) / "database" / "test.db"))
        self._set_env("ZERTAN_MEDIA_ROOT", str(Path(self.temp_dir.name) / "assets"))
        self._set_env("ZERTAN_SEED_DEMO_CONTENT", "0")
        self._set_env("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", "statistics-api-admin-password")
        self.addCleanup(self._restore_env)

        self.app = create_app(run_server=False)
        self.db = DBManager()
        self.admin = self.db.users.get_by_login_name("admin")
        self.user_alpha = self._create_user("stats.alpha", "Stats Alpha", role="user")
        self.user_beta = self._create_user("stats.beta", "Stats Beta", role="user")

        self.group_alpha = self.db.groups.create("Stats Alpha Group", user_ids=[self.user_alpha["id"]])
        self.group_beta = self.db.groups.create("Stats Beta Group", user_ids=[self.user_beta["id"]])

        self.exam_alpha = self._create_exam("STA-100", group_ids=[self.group_alpha["id"]])
        self.exam_beta = self._create_exam("STA-200", group_ids=[self.group_beta["id"]])
        self.question_alpha = self._create_question(self.exam_alpha, position=1)
        self.question_beta = self._create_question(self.exam_beta, position=1)

        self._create_submitted_attempt(self.user_alpha["id"], self.exam_alpha, self.question_alpha, True)
        self._create_submitted_attempt(self.user_beta["id"], self.exam_beta, self.question_beta, False)

    def test_user_overview_and_personal_statistics(self):
        with self.app.test_client() as client:
            self._login(client, "stats.alpha")
            overview_response = client.get("/api/statistics/overview")
            personal_response = client.get("/api/statistics/me")

        self.assertEqual(overview_response.status_code, 200)
        self.assertEqual(personal_response.status_code, 200)
        overview = overview_response.get_json()
        personal = personal_response.get_json()

        self.assertEqual(overview["kpis"]["exams_completed"], 1)
        self.assertEqual(overview["kpis"]["total_correct"], 1)
        self.assertEqual(personal["by_question_type"][0]["question_type"], "single_select")
        self.assertEqual(personal["by_question_type"][0]["success_rate"], 100.0)

    def test_administrator_can_fetch_user_statistics(self):
        with self.app.test_client() as client:
            self._login(client, "admin", password="statistics-api-admin-password")
            response = client.get(f"/api/statistics/users/{self.user_alpha['id']}")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["user"]["login_name"], "stats.alpha")
        self.assertEqual(payload["overview"]["kpis"]["exams_completed"], 1)

    def test_user_statistics_requires_administrator_and_existing_user(self):
        with self.app.test_client() as client:
            self._login(client, "stats.alpha")
            forbidden_response = client.get(f"/api/statistics/users/{self.user_beta['id']}")

        self.assertEqual(forbidden_response.status_code, 403)

        with self.app.test_client() as client:
            self._login(client, "admin", password="statistics-api-admin-password")
            not_found_response = client.get("/api/statistics/users/99999")

        self.assertEqual(not_found_response.status_code, 404)
        self.assertEqual(not_found_response.get_json()["error"], "User not found.")

    def test_exam_statistics_requires_accessible_exam(self):
        with self.app.test_client() as client:
            self._login(client, "stats.alpha")
            own_exam_response = client.get(f"/api/statistics/exams/{self.exam_alpha}")
            other_exam_response = client.get(f"/api/statistics/exams/{self.exam_beta}")

        self.assertEqual(own_exam_response.status_code, 200)
        self.assertEqual(other_exam_response.status_code, 403)
        self.assertEqual(own_exam_response.get_json()["statistics"]["attempts"], 1)

    def test_exam_statistics_returns_not_found_for_missing_exam(self):
        with self.app.test_client() as client:
            self._login(client, "stats.alpha")
            response = client.get("/api/statistics/exams/99999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Exam not found.")

    def test_platform_statistics_honors_feature_flag_and_group_scope(self):
        self.db.site_features.set_enabled("global_stats_page", True)

        with self.app.test_client() as client:
            self._login(client, "admin", password="statistics-api-admin-password")
            admin_response = client.get(f"/api/statistics/platform?group_id={self.group_alpha['id']}")

        self.assertEqual(admin_response.status_code, 200)
        admin_payload = admin_response.get_json()
        self.assertEqual(admin_payload["selected_group_id"], self.group_alpha["id"])
        self.assertEqual(admin_payload["platform"]["summary"]["submitted_attempts"], 1)
        self.assertEqual(len(admin_payload["platform"]["users"]), 1)
        self.assertEqual(admin_payload["platform"]["users"][0]["login_name"], "stats.alpha")

        self.db.site_features.set_enabled("global_stats_page", False)
        with self.app.test_client() as client:
            self._login(client, "stats.alpha")
            disabled_response = client.get("/api/statistics/platform")

        self.assertEqual(disabled_response.status_code, 403)

    def test_platform_statistics_rejects_invalid_or_forbidden_group_filters(self):
        self.db.site_features.set_enabled("global_stats_page", True)

        with self.app.test_client() as client:
            self._login(client, "stats.alpha")
            invalid_group_response = client.get("/api/statistics/platform?group_id=not-a-number")
            forbidden_group_response = client.get(f"/api/statistics/platform?group_id={self.group_beta['id']}")
            own_scope_response = client.get("/api/statistics/platform")

        self.assertEqual(invalid_group_response.status_code, 400)
        self.assertEqual(invalid_group_response.get_json()["error"], "Group id must be a valid integer.")
        self.assertEqual(forbidden_group_response.status_code, 403)
        self.assertEqual(forbidden_group_response.get_json()["error"], "Selected group is not available for this user.")
        self.assertEqual(own_scope_response.status_code, 200)
        own_scope_payload = own_scope_response.get_json()
        self.assertEqual(own_scope_payload["current_user_role"], "user")
        self.assertEqual(len(own_scope_payload["comparison_groups"]), 1)
        self.assertEqual(own_scope_payload["comparison_groups"][0]["id"], self.group_alpha["id"])
        self.assertEqual(own_scope_payload["platform"]["summary"]["submitted_attempts"], 1)
        self.assertEqual(len(own_scope_payload["platform"]["users"]), 1)
        self.assertEqual(own_scope_payload["platform"]["users"][0]["login_name"], "stats.alpha")

    def _create_submitted_attempt(self, user_id, exam_id, question_id, is_correct):
        attempt_id = self.db.attempts.create(exam_id, user_id, {}, 1, random_order=False)
        self.db.attempts.add_questions(
            attempt_id,
            [
                {
                    "question_id": question_id,
                    "snapshot": self.db.questions.get(question_id, include_answers=True),
                }
            ],
        )
        attempt_question_id = self.db.attempts.get_attempt_questions(attempt_id)[0]["attempt_question_id"]
        self.db.attempts.finalize_answer(attempt_question_id, is_correct, 1 if is_correct else 0, False)
        self.db.attempts.mark_submitted(
            attempt_id,
            1 if is_correct else 0,
            0 if is_correct else 1,
            0,
            100.0 if is_correct else 0.0,
        )
        return attempt_id

    def _create_exam(self, code, *, group_ids):
        return self.db.exams.create(
            {
                "code": code,
                "title": f"Exam {code}",
                "provider": "Zertan",
                "description": "Statistics API integration test.",
                "difficulty": "intermediate",
                "status": "published",
                "tags": ["statistics"],
                "group_ids": group_ids,
            },
            self.admin["id"],
            allowed_group_ids=[self.group_alpha["id"], self.group_beta["id"]],
            allow_global=True,
        )

    def _create_question(self, exam_id, *, position):
        return self.db.questions.create(
            exam_id,
            {
                "type": "single_select",
                "title": f"Question {position}",
                "statement": f"Statistics prompt {position}",
                "explanation": f"Statistics explanation {position}",
                "difficulty": "intermediate",
                "status": "active",
                "position": position,
                "tags": ["statistics"],
                "topics": ["reporting"],
                "options": [
                    {"key": "A", "text": "Correct", "is_correct": True},
                    {"key": "B", "text": "Wrong", "is_correct": False},
                ],
            },
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
