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


class AdminApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-admin-api-")
        self.addCleanup(self.temp_dir.cleanup)
        self._set_env("ZERTAN_DATA_DIR", self.temp_dir.name)
        self._set_env("ZERTAN_DB_PATH", str(Path(self.temp_dir.name) / "database" / "test.db"))
        self._set_env("ZERTAN_MEDIA_ROOT", str(Path(self.temp_dir.name) / "assets"))
        self._set_env("ZERTAN_SEED_DEMO_CONTENT", "0")
        self._set_env("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", "admin-api-password")
        self.addCleanup(self._restore_env)

        self.app = create_app(run_server=False)
        self.db = DBManager()
        self.bootstrap_admin = self.db.users.get_by_login_name("admin")
        self.other_admin = self._create_user("ops.admin", "Ops Admin", role="administrator")
        self.student = self._create_user("student.one", "Student One", role="user")

        self.exam_id = self.db.exams.create(
            {
                "code": "ADM-100",
                "title": "Admin deletion cascade",
                "provider": "Zertan",
                "description": "Exercise user deletion cleanup.",
                "difficulty": "intermediate",
                "status": "published",
                "tags": ["admin"],
            },
            self.bootstrap_admin["id"],
            allow_global=True,
        )
        self.question_id = self.db.questions.create(
            self.exam_id,
            {
                "type": "single_select",
                "title": "Deletion cleanup",
                "statement": "Does user deletion cascade exam data?",
                "explanation": "Yes, attempts and answers should disappear with the user.",
                "difficulty": "intermediate",
                "status": "active",
                "position": 1,
                "tags": ["admin"],
                "topics": ["cleanup"],
                "options": [
                    {"key": "A", "text": "Yes", "is_correct": True},
                    {"key": "B", "text": "No", "is_correct": False},
                ],
            },
        )

    def test_admin_listing_marks_protected_and_self_deletion_rules(self):
        with self.app.test_client() as client:
            self._login(client, "ops.admin", "valid-password")

            response = client.get("/api/admin/users")

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            users_by_login = {user["login_name"]: user for user in payload["users"]}

            self.assertFalse(users_by_login["ops.admin"]["can_delete"])
            self.assertIn("own user", users_by_login["ops.admin"]["delete_block_reason"])
            self.assertFalse(users_by_login["admin"]["can_delete"])
            self.assertIn("protected admin user", users_by_login["admin"]["delete_block_reason"])
            self.assertTrue(users_by_login["student.one"]["can_delete"])

    def test_administrator_cannot_delete_self_or_protected_admin(self):
        with self.app.test_client() as client:
            self._login(client, "ops.admin", "valid-password")

            self.assertEqual(client.delete(f"/api/admin/users/{self.other_admin['id']}").status_code, 400)
            protected_response = client.delete(f"/api/admin/users/{self.bootstrap_admin['id']}")

            self.assertEqual(protected_response.status_code, 400)
            self.assertEqual(
                protected_response.get_json()["error"],
                "The protected admin user cannot be deleted.",
            )

    def test_protected_admin_can_delete_other_admin_and_their_session_data(self):
        attempt_id = self.db.attempts.create(self.exam_id, self.other_admin["id"], {}, 1)
        self.db.attempts.add_questions(
            attempt_id,
            [
                {
                    "question_id": self.question_id,
                    "snapshot": {
                        "id": self.question_id,
                        "statement": "Does user deletion cascade exam data?",
                    },
                }
            ],
        )

        with self.app.test_client() as target_client:
            self._login(target_client, "ops.admin", "valid-password")
        _, sessions_before = self.db.db.execute(
            "SELECT COUNT(*) AS total FROM sessions WHERE user_id = ?",
            (self.other_admin["id"],),
            fetchone=True,
        )
        self.assertEqual(sessions_before["total"], 1)

        with self.app.test_client() as admin_client:
            self._login(admin_client, "admin", "admin-api-password")
            response = admin_client.delete(f"/api/admin/users/{self.other_admin['id']}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "deleted")
        self.assertIsNone(self.db.users.get_by_id(self.other_admin["id"]))

        _, sessions_after = self.db.db.execute(
            "SELECT COUNT(*) AS total FROM sessions WHERE user_id = ?",
            (self.other_admin["id"],),
            fetchone=True,
        )
        _, attempts_after = self.db.db.execute(
            "SELECT COUNT(*) AS total FROM exam_attempts WHERE user_id = ?",
            (self.other_admin["id"],),
            fetchone=True,
        )
        _, answers_after = self.db.db.execute(
            """
            SELECT COUNT(*) AS total
            FROM exam_answers
            WHERE attempt_id = ?
            """,
            (attempt_id,),
            fetchone=True,
        )

        self.assertEqual(sessions_after["total"], 0)
        self.assertEqual(attempts_after["total"], 0)
        self.assertEqual(answers_after["total"], 0)

    def test_administrator_can_create_and_update_user_with_groups(self):
        existing_group = self.db.groups.create("Operations", user_ids=[self.student["id"]])

        with self.app.test_client() as client:
            self._login(client, "admin", "admin-api-password")
            create_response = client.post(
                "/api/admin/users",
                json={
                    "display_name": "Reviewer User",
                    "login_name": "review.user",
                    "password": "review-password",
                    "role": "reviewer",
                    "group_ids": [existing_group["id"]],
                },
            )
            self.assertEqual(create_response.status_code, 201)
            created_user = create_response.get_json()["user"]
            self.assertEqual(created_user["role"], "reviewer")
            self.assertEqual([group["id"] for group in created_user["groups"]], [existing_group["id"]])

            managed_group = self.db.groups.create("Managed", user_ids=[])
            update_response = client.put(
                f"/api/admin/users/{created_user['id']}",
                json={
                    "display_name": "Updated Reviewer",
                    "login_name": "review.updated",
                    "role": "examiner",
                    "status": "active",
                    "password": "updated-review-password",
                    "group_ids": [managed_group["id"]],
                },
            )

        self.assertEqual(update_response.status_code, 200)
        updated_user = update_response.get_json()["user"]
        self.assertEqual(updated_user["login_name"], "review.updated")
        self.assertEqual(updated_user["role"], "examiner")
        self.assertEqual([group["id"] for group in updated_user["groups"]], [managed_group["id"]])

        with self.app.test_client() as client:
            relogin_response = client.post(
                "/api/auth/login",
                json={"login_name": "review.updated", "password": "updated-review-password"},
            )
        self.assertEqual(relogin_response.status_code, 200)

    def test_administrator_can_manage_groups_and_features(self):
        with self.app.test_client() as client:
            self._login(client, "admin", "admin-api-password")
            create_group_response = client.post(
                "/api/admin/user-groups",
                json={
                    "name": "Content Team",
                    "description": "Review and author content.",
                    "user_ids": [self.student["id"]],
                },
            )
            self.assertEqual(create_group_response.status_code, 201)
            group = create_group_response.get_json()["group"]
            self.assertEqual(group["name"], "Content Team")
            self.assertEqual(len(group["members"]), 1)

            update_group_response = client.put(
                f"/api/admin/user-groups/{group['id']}",
                json={
                    "name": "Updated Content Team",
                    "description": "Updated description",
                    "user_ids": [self.student["id"], self.other_admin["id"]],
                },
            )
            list_groups_response = client.get("/api/admin/user-groups")
            list_features_response = client.get("/api/admin/features")
            update_feature_response = client.put(
                "/api/admin/features/global_stats_page",
                json={"enabled": True},
            )
            delete_group_response = client.delete(f"/api/admin/user-groups/{group['id']}")

        self.assertEqual(update_group_response.status_code, 200)
        updated_group = update_group_response.get_json()["group"]
        self.assertEqual(updated_group["name"], "Updated Content Team")
        self.assertEqual({member["id"] for member in updated_group["members"]}, {self.student["id"], self.other_admin["id"]})

        self.assertEqual(list_groups_response.status_code, 200)
        listed_group_ids = {entry["id"] for entry in list_groups_response.get_json()["groups"]}
        self.assertIn(group["id"], listed_group_ids)

        self.assertEqual(list_features_response.status_code, 200)
        feature_keys = {entry["feature_key"] for entry in list_features_response.get_json()["features"]}
        self.assertIn("global_stats_page", feature_keys)

        self.assertEqual(update_feature_response.status_code, 200)
        self.assertTrue(update_feature_response.get_json()["feature"]["enabled"])

        self.assertEqual(delete_group_response.status_code, 200)
        self.assertIsNone(self.db.groups.get(group["id"]))

    def test_non_admin_cannot_use_admin_endpoints(self):
        with self.app.test_client() as client:
            self._login(client, "student.one", "valid-password")
            users_response = client.get("/api/admin/users")
            create_group_response = client.post("/api/admin/user-groups", json={"name": "Blocked"})

        self.assertEqual(users_response.status_code, 403)
        self.assertEqual(create_group_response.status_code, 403)

    def _create_user(self, login_name, display_name, *, role):
        self.db.users.create(
            login_name,
            display_name,
            self._password_hash(),
            role=role,
            status="active",
        )
        return self.db.users.get_by_login_name(login_name)

    def _login(self, client, login_name, password):
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
