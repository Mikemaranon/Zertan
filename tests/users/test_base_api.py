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


class _FakeExamPolicy:
    def __init__(self, db, user_manager):
        self.db = db
        self.user_manager = user_manager

    def user_is_administrator(self, user):
        return self.user_manager.user_has_role(user, "administrator")

    def list_exam_scope_options_for_user(self, user):
        user_id = None if self.user_is_administrator(user) else user["id"]
        return self.db.groups.list_scope_options_for_user(user_id)

    def list_exam_scope_group_ids_for_user(self, user):
        if self.user_is_administrator(user):
            return [group["id"] for group in self.db.groups.list_scope_options_for_user(None)]
        return self.db.groups.list_ids_for_user(user["id"])

    def user_can_access_exam(self, user, exam_id):
        return self.db.exams.user_can_access(
            exam_id,
            None if self.user_is_administrator(user) else user["id"],
            is_administrator=self.user_is_administrator(user),
        )

    def user_can_manage_exam(self, user, exam):
        if not exam:
            return False
        if self.user_is_administrator(user):
            return True
        if not exam.get("group_ids") or not self.user_manager.user_has_role(user, "reviewer"):
            return False
        allowed_group_ids = set(self.list_exam_scope_group_ids_for_user(user))
        return set(exam.get("group_ids", [])).issubset(allowed_group_ids)

    def get_accessible_exam(self, user, exam_id):
        exam = self.db.exams.get(exam_id)
        if not exam:
            return None, "not_found"
        if not self.user_can_access_exam(user, exam_id):
            return None, "forbidden"
        return exam, None

    def build_exam_permissions(self, user, exam):
        can_manage = self.user_manager.user_has_role(user, "examiner") and self.user_can_manage_exam(user, exam)
        return {
            "can_manage": can_manage,
            "can_edit_questions": self.user_manager.user_has_role(user, "reviewer") and self.user_can_manage_exam(user, exam),
            "can_export_package": can_manage,
        }

    def build_question_permissions(self, user, exam):
        return {
            "can_edit_questions": self.user_manager.user_has_role(user, "reviewer") and self.user_can_manage_exam(user, exam),
            "can_delete_questions": self.user_manager.user_has_role(user, "examiner") and self.user_can_manage_exam(user, exam),
        }


class BaseApiTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.db = _FakeDb()
        self.user_manager = _FakeUserManager()
        self.services = SimpleNamespace(exam_policy=_FakeExamPolicy(self.db, self.user_manager))

    def test_auth_user_returns_unauthorized_for_missing_user(self):
        user_manager = _FakeUserManager(checked_user=None)
        api = BaseAPI(
            self.app,
            user_manager,
            self.db,
            SimpleNamespace(exam_policy=_FakeExamPolicy(self.db, user_manager)),
        )

        with self.app.app_context():
            user, error = api.auth_user(SimpleNamespace())

        self.assertIsNone(user)
        self.assertEqual(error[1], 401)
        self.assertEqual(error[0].get_json()["error"], "Unauthorized")

    def test_auth_user_enforces_minimum_role(self):
        user_manager = _FakeUserManager(checked_user={"id": 7, "role": "reviewer"})
        api = BaseAPI(
            self.app,
            user_manager,
            self.db,
            SimpleNamespace(exam_policy=_FakeExamPolicy(self.db, user_manager)),
        )

        with self.app.app_context():
            user, error = api.auth_user(SimpleNamespace(), min_role="examiner")

        self.assertIsNone(user)
        self.assertEqual(error[1], 403)
        self.assertEqual(error[0].get_json()["error"], "Forbidden")

    def test_auth_user_returns_authenticated_user_when_role_is_sufficient(self):
        checked_user = {"id": 9, "role": "administrator"}
        user_manager = _FakeUserManager(checked_user=checked_user)
        api = BaseAPI(
            self.app,
            user_manager,
            self.db,
            SimpleNamespace(exam_policy=_FakeExamPolicy(self.db, user_manager)),
        )

        with self.app.app_context():
            user, error = api.auth_user(SimpleNamespace(), min_role="examiner")

        self.assertEqual(user, checked_user)
        self.assertIsNone(error)

    def test_feature_enabled_and_scope_helpers_respect_admin_status(self):
        user_manager = _FakeUserManager(checked_user={"id": 7, "role": "user"})
        api = BaseAPI(
            self.app,
            user_manager,
            self.db,
            SimpleNamespace(exam_policy=_FakeExamPolicy(self.db, user_manager)),
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
