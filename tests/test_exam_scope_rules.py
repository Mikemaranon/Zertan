import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.data_m.db_methods.t_exams import ExamsTable
from app.web_server.data_m.db_methods.t_groups import GroupsTable
from app.web_server.data_m.db_methods.t_users import UsersTable
from app.web_server.data_m.utils.database import Database


class ExamScopeRulesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-scope-tests-")
        self.addCleanup(self.temp_dir.cleanup)
        self._set_env("ZERTAN_DATA_DIR", self.temp_dir.name)
        self._set_env("ZERTAN_DB_PATH", str(Path(self.temp_dir.name) / "utils" / "test.db"))
        self._set_env("ZERTAN_MEDIA_ROOT", str(Path(self.temp_dir.name) / "assets"))
        self.addCleanup(self._restore_env)

        self.database = Database()
        self.exams = ExamsTable(self.database)
        self.groups = GroupsTable(self.database)
        self.users = UsersTable(self.database)

        self.database.execute("DELETE FROM exams WHERE code = ?", ("ZT-100",))

        self.admin_id = self.database.execute(
            "SELECT id FROM users WHERE login_name = ?",
            ("admin",),
            fetchone=True,
        )[1]["id"]
        self.examiner_id = self._create_user("scope.examiner", "Scope Examiner", role="examiner")
        self.user_a_id = self._create_user("scope.usera", "Scope User A")
        self.user_b_id = self._create_user("scope.userb", "Scope User B")

        self.group_a = self.groups.create("Scope Group A", user_ids=[self.examiner_id, self.user_a_id])
        self.group_b = self.groups.create("Scope Group B", user_ids=[self.user_b_id])

    def test_administrator_can_create_global_exam(self):
        exam_id = self.exams.create(
            self._exam_payload("ADM-100"),
            self.admin_id,
            allowed_group_ids=[self.group_a["id"], self.group_b["id"]],
            allow_global=True,
        )

        exam = self.exams.get(exam_id)
        self.assertTrue(exam["is_global_scope"])
        self.assertEqual([], exam["group_ids"])
        self.assertEqual("global", exam["scope_mode"])

    def test_examiner_cannot_create_global_exam(self):
        with self.assertRaisesRegex(ValueError, "Select at least one group"):
            self.exams.create(
                self._exam_payload("EXM-100"),
                self.examiner_id,
                allowed_group_ids=[self.group_a["id"]],
                allow_global=False,
            )

    def test_examiner_cannot_assign_exam_to_group_outside_scope(self):
        with self.assertRaisesRegex(ValueError, "outside your allowed scope"):
            self.exams.create(
                {
                    **self._exam_payload("EXM-101"),
                    "group_ids": [self.group_b["id"]],
                },
                self.examiner_id,
                allowed_group_ids=[self.group_a["id"]],
                allow_global=False,
            )

    def test_exam_listing_only_returns_global_and_matching_groups_for_non_admin(self):
        self.exams.create(
            self._exam_payload("GLB-100"),
            self.admin_id,
            allowed_group_ids=[self.group_a["id"], self.group_b["id"]],
            allow_global=True,
        )
        self.exams.create(
            {
                **self._exam_payload("GRP-A-100"),
                "group_ids": [self.group_a["id"]],
            },
            self.admin_id,
            allowed_group_ids=[self.group_a["id"], self.group_b["id"]],
            allow_global=True,
        )
        self.exams.create(
            {
                **self._exam_payload("GRP-B-100"),
                "group_ids": [self.group_b["id"]],
            },
            self.admin_id,
            allowed_group_ids=[self.group_a["id"], self.group_b["id"]],
            allow_global=True,
        )

        visible_codes = {
            exam["code"]
            for exam in self.exams.list_all(user_id=self.examiner_id, is_administrator=False)
        }

        self.assertIn("GLB-100", visible_codes)
        self.assertIn("GRP-A-100", visible_codes)
        self.assertNotIn("GRP-B-100", visible_codes)

    def _create_user(self, login_name, display_name, role="user"):
        self.users.create(
            login_name,
            display_name,
            "test-password-hash",
            role=role,
            status="active",
        )
        return self.users.get_by_login_name(login_name)["id"]

    def _exam_payload(self, code):
        return {
            "code": code,
            "title": f"Exam {code}",
            "provider": "Zertan",
            "description": "Scope validation exam",
            "difficulty": "intermediate",
            "status": "published",
            "tags": ["scope"],
        }

    def _set_env(self, key, value):
        original = os.environ.get(key)
        os.environ[key] = value
        setattr(self, f"_orig_{key}", original)

    def _restore_env(self):
        for key in ("ZERTAN_DATA_DIR", "ZERTAN_DB_PATH", "ZERTAN_MEDIA_ROOT"):
            original = getattr(self, f"_orig_{key}", None)
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


if __name__ == "__main__":
    unittest.main()
