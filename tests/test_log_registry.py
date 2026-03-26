import json
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
from app.web_server.services_m.log_registry_service import LogRegistryService
from app.web_server.user_m import UserManager


class LogRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-log-registry-")
        self.addCleanup(self.temp_dir.cleanup)
        self._set_env("ZERTAN_DATA_DIR", self.temp_dir.name)
        self._set_env("ZERTAN_DB_PATH", str(Path(self.temp_dir.name) / "database" / "test.db"))
        self._set_env("ZERTAN_MEDIA_ROOT", str(Path(self.temp_dir.name) / "assets"))
        self._set_env("ZERTAN_SEED_DEMO_CONTENT", "0")
        self._set_env("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", "registry-admin-password")
        self.addCleanup(self._restore_env)

        self.app = create_app(run_server=False)
        self.db = DBManager()
        self.user_manager = UserManager(db_manager=self.db)
        self.log_registry = LogRegistryService(self.db)

        admin = self.db.users.get_by_login_name("admin")
        self.admin = self.user_manager.public_user(admin)
        self.examiner = self.user_manager.create_user(
            "Registry Examiner",
            "registry.examiner",
            "examiner-password",
            role="examiner",
            status="active",
        )
        self.group_a = self.db.groups.create("Registry Group A", user_ids=[self.examiner["id"]])
        self.group_b = self.db.groups.create("Registry Group B", user_ids=[])

        self.exam_a = self.db.exams.get(
            self.db.exams.create(
                self._exam_payload("LOG-A-100", [self.group_a["id"]]),
                self.admin["id"],
                allowed_group_ids=[self.group_a["id"], self.group_b["id"]],
                allow_global=True,
            )
        )
        self.exam_b = self.db.exams.get(
            self.db.exams.create(
                self._exam_payload("LOG-B-100", [self.group_b["id"]]),
                self.admin["id"],
                allowed_group_ids=[self.group_a["id"], self.group_b["id"]],
                allow_global=True,
            )
        )
        self.question_a = self.db.questions.get(
            self.db.questions.create(self.exam_a["id"], self._question_payload("Question A"))
        )
        self.question_b = self.db.questions.get(
            self.db.questions.create(self.exam_b["id"], self._question_payload("Question B"))
        )

    def test_question_delete_api_creates_detailed_log_entry(self):
        with self.app.test_client() as client:
            login_response = client.post(
                "/api/auth/login",
                json={"login_name": "registry.examiner", "password": "examiner-password"},
            )
            self.assertEqual(login_response.status_code, 200)

            response = client.delete(f"/api/questions/{self.question_a['id']}")

        self.assertEqual(response.status_code, 200)
        entries = self.db.log_registry.list_entries(exam_id=self.exam_a["id"])
        self.assertEqual(1, len(entries))
        entry = entries[0]
        self.assertEqual("delete", entry["action"])
        self.assertEqual("registry.examiner", entry["actor"]["login_name"])
        self.assertEqual(self.exam_a["code"], entry["exam"]["code"])
        self.assertEqual(self.question_a["id"], entry["question"]["id"])
        self.assertIn("Question", entry["question"]["label"])
        self.assertIn("Question A", entry["diff_text"])

    def test_examiner_overview_and_group_export_respect_scope(self):
        self.log_registry.record_question_change(
            actor_user=self.admin,
            action="create",
            exam=self.exam_a,
            after_question=self.question_a,
            details="Seeded log for group A",
        )
        self.log_registry.record_question_change(
            actor_user=self.admin,
            action="create",
            exam=self.exam_b,
            after_question=self.question_b,
            details="Seeded log for group B",
        )

        with self.app.test_client() as client:
            login_response = client.post(
                "/api/auth/login",
                json={"login_name": "registry.examiner", "password": "examiner-password"},
            )
            self.assertEqual(login_response.status_code, 200)

            overview = client.get("/api/log-registry")
            export_group = client.get(f"/api/log-registry/export?scope=group&group_id={self.group_a['id']}")
            export_domain = client.get("/api/log-registry/export?scope=domain")

        self.assertEqual(overview.status_code, 200)
        overview_payload = overview.get_json()
        visible_codes = {exam["code"] for exam in overview_payload["exams"]}
        self.assertIn(self.exam_a["code"], visible_codes)
        self.assertNotIn(self.exam_b["code"], visible_codes)

        self.assertEqual(export_group.status_code, 200)
        export_payload = json.loads(export_group.data.decode("utf-8"))
        exported_codes = {entry["exam"]["code"] for entry in export_payload["logs"]}
        self.assertIn(self.exam_a["code"], exported_codes)
        self.assertNotIn(self.exam_b["code"], exported_codes)

        self.assertEqual(export_domain.status_code, 403)

    def test_administrator_can_delete_group_logs_without_touching_other_groups(self):
        self.log_registry.record_question_change(
            actor_user=self.admin,
            action="create",
            exam=self.exam_a,
            after_question=self.question_a,
            details="Seeded log for deletion",
        )
        self.log_registry.record_question_change(
            actor_user=self.admin,
            action="create",
            exam=self.exam_b,
            after_question=self.question_b,
            details="Seeded log for retention",
        )

        with self.app.test_client() as client:
            login_response = client.post(
                "/api/auth/login",
                json={"login_name": "admin", "password": "registry-admin-password"},
            )
            self.assertEqual(login_response.status_code, 200)

            response = client.delete(f"/api/log-registry?scope=group&group_id={self.group_a['id']}")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual("deleted", payload["status"])
        self.assertGreater(payload["deleted_count"], 0)
        self.assertEqual([], self.db.log_registry.list_entries(exam_id=self.exam_a["id"]))
        self.assertEqual(1, len(self.db.log_registry.list_entries(exam_id=self.exam_b["id"])))

    def _exam_payload(self, code, group_ids):
        return {
            "code": code,
            "title": f"Exam {code}",
            "provider": "Zertan",
            "description": "Log registry scope test exam",
            "difficulty": "intermediate",
            "status": "published",
            "tags": ["logs"],
            "group_ids": group_ids,
        }

    def _question_payload(self, title):
        return {
            "type": "single_select",
            "title": title,
            "statement": f"{title} statement",
            "explanation": f"{title} explanation",
            "difficulty": "intermediate",
            "status": "active",
            "position": 1,
            "config": {},
            "options": [
                {"key": "a", "text": "Option A", "is_correct": True},
                {"key": "b", "text": "Option B", "is_correct": False},
            ],
            "tags": ["audit"],
            "topics": ["registry"],
            "assets": [],
        }

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
