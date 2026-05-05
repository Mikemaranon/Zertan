import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.services_m.exam_policy_service import ExamPolicyService


class _FakeUserManager:
    def user_has_role(self, user, role):
        order = {"user": 0, "reviewer": 1, "examiner": 2, "administrator": 3}
        normalized = {"admin": "administrator"}
        user_role = normalized.get((user or {}).get("role"), (user or {}).get("role"))
        required_role = normalized.get(role, role)
        return order.get(user_role, -1) >= order.get(required_role, -1)


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
        return int(exam_id) == 101 and int(user_id) == 7


class _FakeDb:
    def __init__(self):
        self.groups = _FakeGroups()
        self.exams = _FakeExams()


class ExamPolicyServiceTests(unittest.TestCase):
    def setUp(self):
        self.policy = ExamPolicyService(_FakeDb(), _FakeUserManager())

    def test_scope_helpers_respect_admin_status(self):
        regular_user = {"id": 7, "role": "reviewer"}
        admin_user = {"id": 9, "role": "administrator"}

        self.assertEqual(self.policy.list_exam_scope_options_for_user(regular_user), [{"id": 10}])
        self.assertEqual(self.policy.list_exam_scope_options_for_user(admin_user), [{"id": 10}, {"id": 20}])
        self.assertEqual(self.policy.list_exam_scope_group_ids_for_user(regular_user), [10])
        self.assertEqual(self.policy.list_exam_scope_group_ids_for_user(admin_user), [10, 20])

    def test_user_can_manage_exam_requires_scope_and_role(self):
        admin = {"id": 9, "role": "administrator"}
        reviewer = {"id": 7, "role": "reviewer"}
        regular_user = {"id": 7, "role": "user"}

        self.assertFalse(self.policy.user_can_manage_exam(reviewer, None))
        self.assertTrue(self.policy.user_can_manage_exam(admin, {"id": 102, "group_ids": [20]}))
        self.assertTrue(self.policy.user_can_manage_exam(reviewer, {"id": 101, "group_ids": [10]}))
        self.assertFalse(self.policy.user_can_manage_exam(reviewer, {"id": 102, "group_ids": [20]}))
        self.assertFalse(self.policy.user_can_manage_exam(reviewer, {"id": 103, "group_ids": []}))
        self.assertFalse(self.policy.user_can_manage_exam(regular_user, {"id": 101, "group_ids": [10]}))

    def test_get_accessible_exam_returns_failure_reason_or_exam(self):
        reviewer = {"id": 7, "role": "reviewer"}
        outsider = {"id": 8, "role": "reviewer"}

        missing_exam, missing_failure = self.policy.get_accessible_exam(reviewer, 999)
        forbidden_exam, forbidden_failure = self.policy.get_accessible_exam(outsider, 101)
        accessible_exam, success_failure = self.policy.get_accessible_exam(reviewer, 101)

        self.assertIsNone(missing_exam)
        self.assertEqual(missing_failure, "not_found")
        self.assertIsNone(forbidden_exam)
        self.assertEqual(forbidden_failure, "forbidden")
        self.assertEqual(accessible_exam["id"], 101)
        self.assertIsNone(success_failure)

    def test_build_permission_payloads_for_exam_and_question_workspaces(self):
        reviewer = {"id": 7, "role": "reviewer"}
        examiner = {"id": 7, "role": "examiner"}
        exam = {"id": 101, "group_ids": [10]}

        self.assertEqual(
            self.policy.build_exam_permissions(reviewer, exam),
            {
                "can_manage": False,
                "can_edit_questions": True,
                "can_export_package": False,
            },
        )
        self.assertEqual(
            self.policy.build_question_permissions(examiner, exam),
            {
                "can_edit_questions": True,
                "can_delete_questions": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
