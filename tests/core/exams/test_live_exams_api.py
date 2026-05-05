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
        self.assignee = self._create_user("live.assignee", "Live Assignee", role="user")
        self.secondary_user = self._create_user("live.secondary", "Live Secondary", role="user")
        self.assignment_group = self.db.groups.create("Live Exam Group", user_ids=[self.assignee["id"]])
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

    def test_admin_can_create_close_and_delete_live_exam(self):
        with self.app.test_client() as client:
            login = client.post(
                "/api/auth/login",
                json={"login_name": "admin", "password": "live-exams-admin-password"},
            )
            self.assertEqual(login.status_code, 200)

            create_response = client.post(
                "/api/live-exams",
                json={
                    "title": "Team live exam",
                    "description": "Assigned through API",
                    "instructions": "Answer all questions.",
                    "exam_id": self.exam_id,
                    "question_count": 1,
                    "group_ids": [self.assignment_group["id"]],
                    "user_ids": [self.secondary_user["id"]],
                    "excluded_user_ids": [self.secondary_user["id"]],
                    "random_order": False,
                },
            )
            self.assertEqual(create_response.status_code, 201)
            live_exam = create_response.get_json()["live_exam"]
            self.assertEqual(live_exam["title"], "Team live exam")
            assignment_user_ids = {assignment["user_id"] for assignment in live_exam["assignments"]}
            self.assertEqual(assignment_user_ids, {self.assignee["id"]})

            list_response = client.get("/api/live-exams")
            close_response = client.post(f"/api/live-exams/{live_exam['id']}/close")
            delete_response = client.delete(f"/api/live-exams/{live_exam['id']}")

        self.assertEqual(list_response.status_code, 200)
        created_ids = {entry["id"] for entry in list_response.get_json()["live_exams"]}
        self.assertIn(live_exam["id"], created_ids)
        self.assertEqual(close_response.status_code, 200)
        self.assertEqual(close_response.get_json()["live_exam"]["status"], "closed")
        self.assertEqual(delete_response.status_code, 200)
        self.assertIsNone(self.db.live_exams.get(live_exam["id"]))

    def test_user_mode_lists_assignments_and_reuses_existing_attempt(self):
        self.db.live_exams.set_assignments(self.live_exam_id, [self.assignee["id"]])

        with self.app.test_client() as client:
            self._login(client, "live.assignee")
            list_response = client.get("/api/live-exams")
            self.assertEqual(list_response.status_code, 200)
            payload = list_response.get_json()
            self.assertEqual(payload["mode"], "user")
            self.assertEqual(len(payload["assignments"]), 1)
            assignment_id = payload["assignments"][0]["assignment_id"]

            first_start = client.post(f"/api/live-exams/assignments/{assignment_id}/start")
            second_start = client.post(f"/api/live-exams/assignments/{assignment_id}/start")

        self.assertEqual(first_start.status_code, 200)
        self.assertEqual(second_start.status_code, 200)
        self.assertEqual(first_start.get_json()["attempt_id"], second_start.get_json()["attempt_id"])

    def test_live_exams_feature_flag_blocks_access(self):
        self.db.site_features.set_enabled("live_exams_page", False)

        with self.app.test_client() as client:
            self._login(client, "admin", "live-exams-admin-password")
            list_response = client.get("/api/live-exams")
            create_response = client.post(
                "/api/live-exams",
                json={
                    "title": "Blocked live exam",
                    "exam_id": self.exam_id,
                    "question_count": 1,
                    "user_ids": [self.assignee["id"]],
                },
            )

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(create_response.status_code, 403)

    def test_start_assignment_rejects_wrong_user_and_closed_live_exam(self):
        self.db.live_exams.set_assignments(self.live_exam_id, [self.assignee["id"]])
        assignment_id = self.db.live_exams.list_for_user(self.assignee["id"])[0]["assignment_id"]

        with self.app.test_client() as client:
            self._login(client, "live.secondary")
            forbidden_response = client.post(f"/api/live-exams/assignments/{assignment_id}/start")

        self.assertEqual(forbidden_response.status_code, 400)
        self.assertEqual(forbidden_response.get_json()["error"], "You do not have access to this live exam.")

        self.db.live_exams.close(self.live_exam_id)
        with self.app.test_client() as client:
            self._login(client, "live.assignee")
            closed_response = client.post(f"/api/live-exams/assignments/{assignment_id}/start")

        self.assertEqual(closed_response.status_code, 400)
        self.assertEqual(closed_response.get_json()["error"], "This live exam is closed.")

    def test_close_and_create_live_exam_validate_payloads(self):
        with self.app.test_client() as client:
            self._login(client, "admin", "live-exams-admin-password")
            missing_assignee_response = client.post(
                "/api/live-exams",
                json={
                    "title": "No assignee exam",
                    "exam_id": self.exam_id,
                    "question_count": 1,
                },
            )
            excessive_count_response = client.post(
                "/api/live-exams",
                json={
                    "title": "Too many questions",
                    "exam_id": self.exam_id,
                    "question_count": 99,
                    "user_ids": [self.assignee["id"]],
                },
            )
            first_close = client.post(f"/api/live-exams/{self.live_exam_id}/close")
            second_close = client.post(f"/api/live-exams/{self.live_exam_id}/close")

        self.assertEqual(missing_assignee_response.status_code, 400)
        self.assertEqual(
            missing_assignee_response.get_json()["error"],
            "Assign at least one user or group to the live exam.",
        )
        self.assertEqual(excessive_count_response.status_code, 400)
        self.assertEqual(
            excessive_count_response.get_json()["error"],
            "Question count exceeds the number of questions that match the selected criteria.",
        )
        self.assertEqual(first_close.status_code, 200)
        self.assertEqual(second_close.status_code, 400)
        self.assertEqual(second_close.get_json()["error"], "Live exam is already closed.")

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
