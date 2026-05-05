import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.services_m.statistics_service import StatisticsService


class _FakeStatisticsTable:
    def user_overview(self, user_id):
        return {"user_id": user_id, "exams_completed": 2}

    def user_success_by_exam(self, user_id):
        return [{"user_id": user_id, "exam_id": 101, "success_rate": 80.0}]

    def user_success_by_question_type(self, user_id):
        return [{"user_id": user_id, "question_type": "single_select", "success_rate": 90.0}]

    def platform_overview(self, group_ids=None):
        return {"summary": {"submitted_attempts": len(group_ids or []) if group_ids is not None else 99}}


class _FakeAttemptsTable:
    def list_recent_for_user(self, user_id, limit=4):
        return [{"user_id": user_id, "attempt_id": 1, "limit_used": limit}]


class _FakeDb:
    def __init__(self):
        self.statistics = _FakeStatisticsTable()
        self.attempts = _FakeAttemptsTable()


class _FakeExamPolicy:
    def user_is_administrator(self, user):
        return user.get("role") == "administrator"

    def list_exam_scope_options_for_user(self, user):
        if user.get("role") == "administrator":
            return [{"id": 10}, {"id": 20}]
        return [{"id": 10}]


class StatisticsServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = StatisticsService(_FakeDb(), user_manager=None, exam_policy=_FakeExamPolicy())

    def test_build_dashboard_payload_reuses_common_kpis_and_recent_attempts(self):
        payload = self.service.build_dashboard_payload(7)

        self.assertEqual(payload["overview"]["kpis"]["exams_completed"], 2)
        self.assertEqual(payload["overview"]["recent_attempts"][0]["limit_used"], 4)
        self.assertEqual(payload["personal"]["by_question_type"][0]["question_type"], "single_select")

    def test_resolve_platform_scope_parses_requested_group_and_limits_non_admin_scope(self):
        admin_scope = self.service.resolve_platform_scope({"id": 1, "role": "administrator"}, "20")
        user_scope = self.service.resolve_platform_scope({"id": 7, "role": "user"}, "")

        self.assertEqual(admin_scope["selected_group_id"], 20)
        self.assertEqual(admin_scope["scope_group_ids"], [20])
        self.assertEqual(user_scope["comparison_groups"], [{"id": 10}])
        self.assertEqual(user_scope["scope_group_ids"], [10])

    def test_resolve_platform_scope_rejects_invalid_or_forbidden_group_ids(self):
        with self.assertRaisesRegex(ValueError, "Group id must be a valid integer."):
            self.service.resolve_platform_scope({"id": 7, "role": "user"}, "abc")

        with self.assertRaisesRegex(PermissionError, "Selected group is not available for this user."):
            self.service.resolve_platform_scope({"id": 7, "role": "user"}, "20")

    def test_build_platform_payload_includes_scope_metadata(self):
        payload = self.service.build_platform_payload({"id": 7, "role": "user"}, "")

        self.assertEqual(payload["current_user_id"], 7)
        self.assertEqual(payload["current_user_role"], "user")
        self.assertEqual(payload["comparison_groups"], [{"id": 10}])
        self.assertEqual(payload["selected_group_id"], None)
        self.assertEqual(payload["platform"]["summary"]["submitted_attempts"], 1)


if __name__ == "__main__":
    unittest.main()
