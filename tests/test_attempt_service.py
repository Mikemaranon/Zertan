import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.services_m.attempt_service import AttemptService


class _FakeAttemptsTable:
    def get_attempt(self, attempt_id):
        if attempt_id != 55:
            return None
        return {
            "id": 55,
            "exam_id": 7,
            "user_id": 3,
            "status": "in_progress",
            "criteria": {},
            "question_count": 12,
            "random_order": True,
            "time_limit_minutes": None,
            "started_at": "2026-03-19 10:00:00",
            "submitted_at": None,
            "duration_seconds": None,
            "score_percent": None,
            "correct_count": None,
            "incorrect_count": None,
            "omitted_count": None,
            "exam_code": "AI-102",
            "exam_title": "Azure AI",
        }

    def get_attempt_questions(self, attempt_id, page_number=None):
        if attempt_id != 55:
            return []
        all_rows = [_build_attempt_question(order) for order in range(1, 13)]
        if page_number is None:
            return all_rows
        return [row for row in all_rows if row["page_number"] == page_number]


class _FakeDbManager:
    def __init__(self):
        self.attempts = _FakeAttemptsTable()


def _build_attempt_question(order):
    return {
        "attempt_question_id": order,
        "question_id": 1000 + order,
        "question_order": order,
        "page_number": ((order - 1) // 5) + 1,
        "snapshot": {
            "id": 1000 + order,
            "exam_id": 7,
            "type": "single_select",
            "title": f"Question {order}",
            "statement": f"Prompt {order}",
            "difficulty": "intermediate",
            "tags": ["azure"],
            "topics": ["ai"],
            "assets": [],
            "options": [
                {"key": "A", "text": "Correct", "is_correct": True},
                {"key": "B", "text": "Incorrect", "is_correct": False},
            ],
            "config": {},
        },
        "response": None,
        "is_correct": None,
        "omitted": True,
        "score": None,
        "answered_at": None,
    }


class AttemptServicePaginationTests(unittest.TestCase):
    def setUp(self):
        self.service = AttemptService(_FakeDbManager())

    def test_returns_only_requested_page_for_attempt_payload(self):
        payload = self.service.get_attempt_payload(55, page_number=2)

        self.assertEqual(payload["current_page"], 2)
        self.assertEqual(payload["total_pages"], 3)
        self.assertEqual([item["question_order"] for item in payload["questions"]], [6, 7, 8, 9, 10])

    def test_clamps_page_number_to_last_page(self):
        payload = self.service.get_attempt_payload(55, page_number=99)

        self.assertEqual(payload["current_page"], 3)
        self.assertEqual([item["question_order"] for item in payload["questions"]], [11, 12])


if __name__ == "__main__":
    unittest.main()
