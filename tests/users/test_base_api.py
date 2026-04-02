import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from flask import Flask

from app.web_server.api_m.domains.base_api import BaseAPI


class _FakeUserManager:
    def __init__(self, checked_user=None):
        self.checked_user = checked_user

    def check_user(self, request):
        return self.checked_user

    def user_has_role(self, user, role):
        order = {"user": 0, "reviewer": 1, "examiner": 2, "administrator": 3}
        normalized = {"admin": "administrator"}
        user_role = normalized.get((user or {}).get("role"), (user or {}).get("role"))
        required_role = normalized.get(role, role)
        return order.get(user_role, -1) >= order.get(required_role, -1)


class _FakeSiteFeatures:
    def __init__(self, enabled_map=None):
        self.enabled_map = dict(enabled_map or {})

    def get(self, feature_key):
        enabled = self.enabled_map.get(feature_key)
        if enabled is None:
            return None
        return {"feature_key": feature_key, "enabled": enabled}


class _FakeGroups:
    def __init__(self):
        self.all_groups = [{"id": 10}, {"id": 20}]
        self.user_groups = {7: [{"id": 10}]}

    def list_scope_options_for_user(self, user_id):
        if user_id is None:
            return [dict(group) for group in self.all_groups]
        return [dict(group) for group in self.user_groups.get(int(user_id), [])]

    def list_ids_for_user(self, user_id):
        return [group["id"] for group in self.user_groups.get(int(user_id), [])]


class _FakeExams:
    def __init__(self):
        self.exams = {
            101: {"id": 101, "group_ids": [10]},
            102: {"id": 102, "group_ids": [20]},
            103: {"id": 103, "group_ids": []},
        }

    def get(self, exam_id):
        exam = self.exams.get(int(exam_id))
        return dict(exam) if exam else None

    def user_can_access(self, exam_id, user_id, *, is_administrator):
        if is_administrator:
            return True
        if int(exam_id) == 101 and int(user_id) == 7:
            return True
        return False


class _FakeDb:
    def __init__(self):
        self.site_features = _FakeSiteFeatures({"global_stats_page": True, "disabled_feature": False})
        self.groups = _FakeGroups()
        self.exams = _FakeExams()


class BaseApiTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.db = _FakeDb()
        self.services = SimpleNamespace()

    def test_auth_user_returns_unauthorized_for_missing_user(self):
        api = BaseAPI(self.app, _FakeUserManager(checked_user=None), self.db, self.services)

        with self.app.app_context():
            user, error = api.auth_user(SimpleNamespace())

        self.assertIsNone(user)
        self.assertEqual(error[1], 401)
        self.assertEqual(error[0].get_json()["error"], "Unauthorized")

    def test_auth_user_enforces_minimum_role(self):
        api = BaseAPI(
            self.app,
            _FakeUserManager(checked_user={"id": 7, "role": "reviewer"}),
            self.db,
            self.services,
        )

        with self.app.app_context():
            user, error = api.auth_user(SimpleNamespace(), min_role="examiner")

        self.assertIsNone(user)
        self.assertEqual(error[1], 403)
        self.assertEqual(error[0].get_json()["error"], "Forbidden")

    def test_auth_user_returns_authenticated_user_when_role_is_sufficient(self):
        checked_user = {"id": 9, "role": "administrator"}
        api = BaseAPI(self.app, _FakeUserManager(checked_user=checked_user), self.db, self.services)

        with self.app.app_context():
            user, error = api.auth_user(SimpleNamespace(), min_role="examiner")

        self.assertEqual(user, checked_user)
        self.assertIsNone(error)

    def test_feature_enabled_and_scope_helpers_respect_admin_status(self):
        api = BaseAPI(
            self.app,
            _FakeUserManager(checked_user={"id": 7, "role": "user"}),
            self.db,
            self.services,
        )

        self.assertTrue(api.feature_enabled("global_stats_page"))
        self.assertFalse(api.feature_enabled("disabled_feature"))
        self.assertFalse(api.feature_enabled("missing_feature"))

        regular_user = {"id": 7, "role": "reviewer"}
        admin_user = {"id": 9, "role": "administrator"}

        self.assertEqual(api.list_exam_scope_options_for_user(regular_user), [{"id": 10}])
        self.assertEqual(api.list_exam_scope_options_for_user(admin_user), [{"id": 10}, {"id": 20}])
        self.assertEqual(api.list_exam_scope_group_ids_for_user(regular_user), [10])
        self.assertEqual(api.list_exam_scope_group_ids_for_user(admin_user), [10, 20])

    def test_user_can_manage_exam_requires_scope_groups_and_role(self):
        api = BaseAPI(self.app, _FakeUserManager(), self.db, self.services)

        admin = {"id": 9, "role": "administrator"}
        reviewer = {"id": 7, "role": "reviewer"}
        regular_user = {"id": 7, "role": "user"}

        self.assertFalse(api.user_can_manage_exam(reviewer, None))
        self.assertTrue(api.user_can_manage_exam(admin, {"id": 102, "group_ids": [20]}))
        self.assertTrue(api.user_can_manage_exam(reviewer, {"id": 101, "group_ids": [10]}))
        self.assertFalse(api.user_can_manage_exam(reviewer, {"id": 102, "group_ids": [20]}))
        self.assertFalse(api.user_can_manage_exam(reviewer, {"id": 103, "group_ids": []}))
        self.assertFalse(api.user_can_manage_exam(regular_user, {"id": 101, "group_ids": [10]}))

    def test_get_accessible_exam_returns_not_found_forbidden_and_success(self):
        api = BaseAPI(self.app, _FakeUserManager(), self.db, self.services)
        reviewer = {"id": 7, "role": "reviewer"}
        outsider = {"id": 8, "role": "reviewer"}

        with self.app.app_context():
            exam, missing_error = api.get_accessible_exam(reviewer, 999)
            forbidden_exam, forbidden_error = api.get_accessible_exam(outsider, 101)
            accessible_exam, success_error = api.get_accessible_exam(reviewer, 101)

        self.assertIsNone(exam)
        self.assertEqual(missing_error[1], 404)
        self.assertEqual(missing_error[0].get_json()["error"], "Exam not found.")

        self.assertIsNone(forbidden_exam)
        self.assertEqual(forbidden_error[1], 403)
        self.assertEqual(forbidden_error[0].get_json()["error"], "Forbidden")

        self.assertEqual(accessible_exam["id"], 101)
        self.assertIsNone(success_error)


if __name__ == "__main__":
    unittest.main()
