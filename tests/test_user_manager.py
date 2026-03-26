import sys
import unittest
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash


ROOT = Path(__file__).resolve().parents[1]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.user_m.user_manager import UserManager


class _FakeUsersTable:
    def __init__(self, users):
        self._users = {int(user["id"]): dict(user) for user in users}
        self.last_touched_user_id = None

    def get_by_login_name(self, login_name):
        normalized = (login_name or "").strip().lower()
        for user in self._users.values():
            if (user["login_name"] or "").lower() == normalized:
                return dict(user)
        return None

    def get_by_id(self, user_id):
        user = self._users.get(int(user_id))
        return dict(user) if user else None

    def touch_last_login(self, user_id):
        self.last_touched_user_id = int(user_id)
        user = self._users[int(user_id)]
        user["last_login_at"] = "2026-03-19T10:15:00"

    def update_profile(self, user_id, display_name):
        self._users[int(user_id)]["display_name"] = display_name

    def update_password(self, user_id, password_hash):
        self._users[int(user_id)]["password_hash"] = password_hash

    def update_avatar(self, user_id, avatar_path):
        self._users[int(user_id)]["avatar_path"] = avatar_path


class _FakeSessionsTable:
    def __init__(self):
        self.records = {}
        self.deleted_tokens = []

    def create(self, user_id, token, expires_at):
        self.records[token] = {
            "user_id": user_id,
            "expires_at": expires_at,
        }

    def get(self, token):
        return self.records.get(token)

    def delete(self, token):
        self.deleted_tokens.append(token)
        self.records.pop(token, None)


class _FakeGroupsTable:
    def __init__(self, groups=None):
        self._groups = {
            int(user_id): [dict(group) for group in entries]
            for user_id, entries in (groups or {}).items()
        }

    def list_for_user(self, user_id):
        return [dict(group) for group in self._groups.get(int(user_id), [])]

    def set_memberships_for_user(self, user_id, group_ids):
        return None


class _FakeDbManager:
    def __init__(self, users, groups=None):
        self.users = _FakeUsersTable(users)
        self.sessions = _FakeSessionsTable()
        self.groups = _FakeGroupsTable(groups)


class UserManagerTests(unittest.TestCase):
    def setUp(self):
        self.database = _FakeDbManager(
            [
                {
                    "id": 7,
                    "login_name": "reviewer.user",
                    "display_name": "Reviewer User",
                    "password_hash": generate_password_hash("valid-password"),
                    "role": "reviewer",
                    "status": "active",
                    "avatar_path": None,
                    "created_at": "2026-03-19T10:00:00",
                    "updated_at": "2026-03-19T10:00:00",
                    "last_login_at": None,
                },
                {
                    "id": 8,
                    "login_name": "disabled.user",
                    "display_name": "Disabled User",
                    "password_hash": generate_password_hash("valid-password"),
                    "role": "user",
                    "status": "disabled",
                    "avatar_path": None,
                    "created_at": "2026-03-19T10:00:00",
                    "updated_at": "2026-03-19T10:00:00",
                    "last_login_at": None,
                },
            ],
            groups={
                7: [
                    {"id": 3, "code": "grp-review", "name": "Review Team"},
                    {"id": 5, "code": "grp-content", "name": "Content Ops"},
                ],
            },
        )
        self.manager = UserManager(
            db_manager=self.database,
            runtime_config={"secret_key": "test-secret-key-with-32-plus-characters", "jwt_lifetime_hours": 4},
        )

    def test_user_has_role_honors_hierarchy_and_aliases(self):
        reviewer = {"role": "reviewer"}
        administrator = {"role": "admin"}

        self.assertTrue(self.manager.user_has_role(reviewer, "user"))
        self.assertFalse(self.manager.user_has_role(reviewer, "examiner"))
        self.assertTrue(self.manager.user_has_role(administrator, "administrator"))

    def test_login_normalizes_login_name_and_persists_session(self):
        result = self.manager.login("  REVIEWER.USER  ", "valid-password")

        self.assertIsNotNone(result)
        self.assertEqual(result["user"]["login_name"], "reviewer.user")
        self.assertEqual(
            result["user"]["groups"],
            [
                {"id": 3, "code": "grp-review", "name": "Review Team"},
                {"id": 5, "code": "grp-content", "name": "Content Ops"},
            ],
        )
        self.assertEqual(self.database.users.last_touched_user_id, 7)
        self.assertEqual(len(self.database.sessions.records), 1)

    def test_update_profile_rejects_partial_password_change(self):
        with self.assertRaisesRegex(ValueError, "complete current password, new password, and confirm new password"):
            self.manager.update_profile(
                7,
                "Updated Reviewer",
                current_password="valid-password",
                new_password="new-password",
                confirm_password="",
            )

    def test_update_profile_updates_password_when_all_fields_are_valid(self):
        updated = self.manager.update_profile(
            7,
            "Updated Reviewer",
            current_password="valid-password",
            new_password="new-password",
            confirm_password="new-password",
        )

        self.assertEqual(updated["display_name"], "Updated Reviewer")
        self.assertTrue(
            check_password_hash(
                self.database.users.get_by_id(7)["password_hash"],
                "new-password",
            )
        )

    def test_get_user_from_token_drops_session_for_disabled_user(self):
        token, _ = self.manager.generate_token(self.database.users.get_by_id(8))
        self.database.sessions.create(8, token, "2026-03-19T14:00:00")

        resolved_user = self.manager.get_user_from_token(token)

        self.assertIsNone(resolved_user)
        self.assertEqual(self.database.sessions.deleted_tokens, [token])


if __name__ == "__main__":
    unittest.main()
