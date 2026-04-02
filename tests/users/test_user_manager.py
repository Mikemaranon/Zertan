import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import jwt
from werkzeug.security import check_password_hash, generate_password_hash


ROOT = Path(__file__).resolve().parents[2]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.user_m.user_manager import UserManager


class _FakeUsersTable:
    def __init__(self, users):
        self._users = {int(user["id"]): dict(user) for user in users}
        self.last_touched_user_id = None
        self.deleted_user_ids = []
        self.next_id = max(self._users) + 1 if self._users else 1

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

    def create(self, login_name, display_name, password_hash, *, role, status):
        user_id = self.next_id
        self.next_id += 1
        self._users[user_id] = {
            "id": user_id,
            "login_name": login_name,
            "display_name": display_name,
            "password_hash": password_hash,
            "role": role,
            "status": status,
            "is_protected": False,
            "avatar_path": None,
            "created_at": "2026-03-19T10:00:00",
            "updated_at": "2026-03-19T10:00:00",
            "last_login_at": None,
        }

    def update(self, user_id, display_name, login_name, role, status):
        user = self._users[int(user_id)]
        user["display_name"] = display_name
        user["login_name"] = login_name
        user["role"] = role
        user["status"] = status

    def delete(self, user_id):
        self.deleted_user_ids.append(int(user_id))
        self._users.pop(int(user_id), None)


class _FakeSessionsTable:
    def __init__(self):
        self.records = {}
        self.deleted_tokens = []
        self.deleted_user_ids = []

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

    def delete_for_user(self, user_id):
        user_id = int(user_id)
        self.deleted_user_ids.append(user_id)
        for token in [token for token, record in self.records.items() if int(record["user_id"]) == user_id]:
            self.records.pop(token, None)


class _FakeGroupsTable:
    def __init__(self, groups=None):
        self._groups = {
            int(user_id): [dict(group) for group in entries]
            for user_id, entries in (groups or {}).items()
        }
        self.membership_updates = []

    def list_for_user(self, user_id):
        return [dict(group) for group in self._groups.get(int(user_id), [])]

    def set_memberships_for_user(self, user_id, group_ids):
        self.membership_updates.append((int(user_id), list(group_ids)))
        self._groups[int(user_id)] = [
            {"id": int(group_id), "code": f"group-{int(group_id)}", "name": f"Group {int(group_id)}"}
            for group_id in group_ids
        ]


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
                    "is_protected": False,
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
                    "is_protected": False,
                    "avatar_path": None,
                    "created_at": "2026-03-19T10:00:00",
                    "updated_at": "2026-03-19T10:00:00",
                    "last_login_at": None,
                },
                {
                    "id": 9,
                    "login_name": "admin",
                    "display_name": "Admin",
                    "password_hash": generate_password_hash("valid-password"),
                    "role": "administrator",
                    "status": "active",
                    "is_protected": True,
                    "avatar_path": None,
                    "created_at": "2026-03-19T10:00:00",
                    "updated_at": "2026-03-19T10:00:00",
                    "last_login_at": None,
                },
                {
                    "id": 10,
                    "login_name": "ops.admin",
                    "display_name": "Ops Admin",
                    "password_hash": generate_password_hash("valid-password"),
                    "role": "administrator",
                    "status": "active",
                    "is_protected": False,
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

    def test_create_user_normalizes_identity_and_assigns_groups(self):
        created = self.manager.create_user(
            "  New Reviewer  ",
            "  NEW.REVIEWER  ",
            "valid-password",
            role="admin",
            group_ids=[11, 12],
        )

        self.assertIsNotNone(created)
        self.assertEqual(created["login_name"], "new.reviewer")
        self.assertEqual(created["display_name"], "New Reviewer")
        self.assertEqual(created["role"], "administrator")
        self.assertEqual(self.database.groups.membership_updates[-1], (created["id"], [11, 12]))

    def test_create_user_rejects_conflicting_or_blank_login_names(self):
        conflict = self.manager.create_user("Another Reviewer", "reviewer.user", "valid-password")
        blank = self.manager.create_user("   ", "   ", "valid-password")

        self.assertIsNone(conflict)
        self.assertIsNone(blank)

    def test_update_user_rejects_conflict_and_updates_password_and_groups(self):
        conflict = self.manager.update_user(
            7,
            "Reviewer User",
            "ops.admin",
            "reviewer",
            "active",
        )

        self.assertIsNone(conflict)

        updated = self.manager.update_user(
            7,
            "Updated Reviewer",
            "updated.reviewer",
            "examiner",
            "disabled",
            password="replacement-password",
            group_ids=[21],
        )

        self.assertEqual(updated["login_name"], "updated.reviewer")
        self.assertEqual(updated["display_name"], "Updated Reviewer")
        self.assertEqual(updated["role"], "examiner")
        self.assertEqual(updated["status"], "disabled")
        self.assertTrue(check_password_hash(self.database.users.get_by_id(7)["password_hash"], "replacement-password"))
        self.assertEqual(self.database.groups.membership_updates[-1], (7, [21]))

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

    def test_update_profile_rejects_wrong_password_confirmation_and_unknown_user(self):
        with self.assertRaisesRegex(ValueError, "Current password is incorrect"):
            self.manager.update_profile(
                7,
                "Updated Reviewer",
                current_password="wrong-password",
                new_password="new-password",
                confirm_password="new-password",
            )

        with self.assertRaisesRegex(ValueError, "do not match"):
            self.manager.update_profile(
                7,
                "Updated Reviewer",
                current_password="valid-password",
                new_password="new-password",
                confirm_password="other-password",
            )

        with self.assertRaisesRegex(ValueError, "User not found"):
            self.manager.update_profile(999, "Nobody")

    def test_get_user_from_token_drops_session_for_disabled_user(self):
        token, _ = self.manager.generate_token(self.database.users.get_by_id(8))
        self.database.sessions.create(8, token, "2026-03-19T14:00:00")

        resolved_user = self.manager.get_user_from_token(token)

        self.assertIsNone(resolved_user)
        self.assertEqual(self.database.sessions.deleted_tokens, [token])

    def test_validate_token_drops_invalid_and_expired_sessions(self):
        valid_user = self.database.users.get_by_id(7)
        valid_token, _ = self.manager.generate_token(valid_user)
        self.database.sessions.create(7, valid_token, "2026-03-19T14:00:00")
        self.assertTrue(self.manager.validate_token(valid_token))

        invalid_token = f"{valid_token}broken"
        self.database.sessions.create(7, invalid_token, "2026-03-19T14:00:00")
        self.assertFalse(self.manager.validate_token(invalid_token))
        self.assertIn(invalid_token, self.database.sessions.deleted_tokens)

        expired_token = jwt.encode(
            {
                "user_id": 7,
                "login_name": "reviewer.user",
                "display_name": "Reviewer User",
                "role": "reviewer",
                "exp": 1,
            },
            self.manager.secret_key,
            algorithm="HS256",
        )
        self.database.sessions.create(7, expired_token, "2026-03-19T14:00:00")
        self.assertFalse(self.manager.validate_token(expired_token))
        self.assertIn(expired_token, self.database.sessions.deleted_tokens)

    def test_check_user_reads_token_from_cookie(self):
        token, _ = self.manager.generate_token(self.database.users.get_by_id(7))
        self.database.sessions.create(7, token, "2026-03-19T14:00:00")

        request = SimpleNamespace(cookies={"token": token})
        resolved = self.manager.check_user(request)

        self.assertEqual(resolved["id"], 7)
        self.assertIsNone(self.manager.check_user(SimpleNamespace(cookies={})))

    def test_can_delete_user_requires_admin_non_self_and_non_protected_target(self):
        admin = self.manager.public_user(self.database.users.get_by_id(10))
        protected_admin = self.database.users.get_by_id(9)
        reviewer = self.manager.public_user(self.database.users.get_by_id(7))

        self.assertTrue(self.manager.can_delete_user(admin, reviewer))
        self.assertFalse(self.manager.can_delete_user(reviewer, admin))
        self.assertFalse(self.manager.can_delete_user(admin, admin))
        self.assertFalse(self.manager.can_delete_user(admin, protected_admin))

    def test_delete_user_rejects_self_deletion(self):
        actor = self.manager.public_user(self.database.users.get_by_id(10))

        with self.assertRaisesRegex(ValueError, "cannot delete their own user"):
            self.manager.delete_user(actor, 10)

    def test_delete_user_rejects_protected_admin(self):
        actor = self.manager.public_user(self.database.users.get_by_id(10))

        with self.assertRaisesRegex(ValueError, "protected admin user"):
            self.manager.delete_user(actor, 9)

    def test_delete_user_clears_sessions_and_removes_target(self):
        actor = self.manager.public_user(self.database.users.get_by_id(9))
        token, _ = self.manager.generate_token(self.database.users.get_by_id(7))
        self.database.sessions.create(7, token, "2026-03-19T14:00:00")

        deleted = self.manager.delete_user(actor, 7)

        self.assertEqual(deleted["id"], 7)
        self.assertEqual(self.database.sessions.deleted_user_ids, [7])
        self.assertEqual(self.database.users.deleted_user_ids, [7])
        self.assertIsNone(self.database.users.get_by_id(7))


if __name__ == "__main__":
    unittest.main()
