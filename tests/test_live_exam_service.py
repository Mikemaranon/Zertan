import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.services_m.exam_attempt_service import LiveExamService


class _FakeUsersTable:
    def __init__(self, users):
        self._users = users

    def all(self):
        return list(self._users)


class _FakeGroupsTable:
    def __init__(self, groups):
        self._groups = groups

    def all(self):
        return list(self._groups)


class _FakeExamsTable:
    def get(self, exam_id):
        if exam_id == 7:
            return {"id": 7, "code": "AI-102"}
        return None


class _FakeQuestionsTable:
    def list_filtered_ids(self, exam_id, criteria):
        if exam_id == 7:
            return [101, 102, 103, 104]
        return []


class _FakeLiveExamsTable:
    def __init__(self):
        self.created_payload = None
        self.created_by = None
        self.assigned_user_ids = None

    def create(self, payload, created_by):
        self.created_payload = payload
        self.created_by = created_by
        return 91

    def set_assignments(self, live_exam_id, user_ids):
        self.assigned_user_ids = (live_exam_id, list(user_ids))

    def get(self, live_exam_id):
        return {"id": live_exam_id}


class _FakeDbManager:
    def __init__(self, *, users, groups):
        self.users = _FakeUsersTable(users)
        self.groups = _FakeGroupsTable(groups)
        self.exams = _FakeExamsTable()
        self.questions = _FakeQuestionsTable()
        self.live_exams = _FakeLiveExamsTable()


class LiveExamServiceTests(unittest.TestCase):
    def test_create_live_exam_resolves_groups_and_exclusions(self):
        database = _FakeDbManager(
            users=[
                {"id": 1, "login_name": "usera", "status": "active"},
                {"id": 2, "login_name": "userb", "status": "active"},
                {"id": 3, "login_name": "userc", "status": "active"},
                {"id": 4, "login_name": "userd", "status": "disabled"},
            ],
            groups=[
                {
                    "id": 10,
                    "status": "active",
                    "members": [
                        {"id": 1, "login_name": "usera", "status": "active"},
                        {"id": 2, "login_name": "userb", "status": "active"},
                        {"id": 4, "login_name": "userd", "status": "disabled"},
                    ],
                },
                {
                    "id": 11,
                    "status": "disabled",
                    "members": [
                        {"id": 3, "login_name": "userc", "status": "active"},
                    ],
                },
            ],
        )

        service = LiveExamService(database)
        live_exam = service.create_live_exam(
            {
                "title": "Morning live exam",
                "exam_id": 7,
                "question_count": 3,
                "user_ids": [3, 4],
                "group_ids": [10, 11],
                "excluded_user_ids": [2, 999],
            },
            created_by=5,
        )

        self.assertEqual(live_exam["id"], 91)
        self.assertEqual(database.live_exams.assigned_user_ids, (91, [1, 3]))

    def test_create_live_exam_rejects_empty_result_after_exclusions(self):
        database = _FakeDbManager(
            users=[
                {"id": 1, "login_name": "usera", "status": "active"},
            ],
            groups=[
                {
                    "id": 10,
                    "status": "active",
                    "members": [
                        {"id": 1, "login_name": "usera", "status": "active"},
                    ],
                },
            ],
        )

        service = LiveExamService(database)

        with self.assertRaisesRegex(ValueError, "do not produce any active assignees"):
            service.create_live_exam(
                {
                    "title": "Empty live exam",
                    "exam_id": 7,
                    "question_count": 2,
                    "group_ids": [10],
                    "excluded_user_ids": [1],
                },
                created_by=5,
            )


if __name__ == "__main__":
    unittest.main()
