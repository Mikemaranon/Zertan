import sys
import unittest
from contextlib import nullcontext
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.services_m.exam_attempt_service import AttemptService


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


class _SubmittedFakeAttemptsTable(_FakeAttemptsTable):
    def get_attempt(self, attempt_id):
        attempt = super().get_attempt(attempt_id)
        if attempt:
            attempt["status"] = "submitted"
        return attempt


class _SubmittedFakeDbManager:
    def __init__(self):
        self.attempts = _SubmittedFakeAttemptsTable()


class _BuilderFakeAttemptsTable:
    def __init__(self):
        self.created_payload = None
        self.stored_snapshots = []

    def create(self, exam_id, user_id, criteria, question_count, random_order=True, time_limit_minutes=None):
        self.created_payload = {
            "exam_id": exam_id,
            "user_id": user_id,
            "criteria": criteria,
            "question_count": question_count,
            "random_order": random_order,
            "time_limit_minutes": time_limit_minutes,
        }
        return 901

    def add_questions(self, attempt_id, question_snapshots):
        self.stored_snapshots = list(question_snapshots)


class _BuilderFakeQuestionsTable:
    def list_filtered_ids(self, exam_id, filters):
        if filters.get("difficulty") == "advanced":
            return [1002]
        return [1001, 1002, 1003]

    def get_many(self, question_ids, include_answers=True):
        return [
            {
                "id": question_id,
                "exam_id": 7,
                "type": "single_select",
                "title": f"Question {question_id}",
                "statement": f"Prompt {question_id}",
                "difficulty": "intermediate",
                "tags": ["azure"],
                "topics": ["ai"],
                "assets": [],
                "options": [
                    {"key": "A", "text": "Correct", "is_correct": True},
                    {"key": "B", "text": "Incorrect", "is_correct": False},
                ],
                "config": {},
            }
            for question_id in question_ids
        ]


class _BuilderFakeStatisticsTable:
    def user_exam_error_focus_candidates(self, user_id, exam_id, failure_percentage_threshold=40, minimum_failure_count=2, limit=None):
        all_candidates = [
            {
                "question_id": 1002,
                "question_title": "Question 1002",
                "question_statement": "Prompt 1002",
                "failure_count": 3,
                "failure_percentage": 75.0,
            },
            {
                "question_id": 1001,
                "question_title": "Question 1001",
                "question_statement": "Prompt 1001",
                "failure_count": 2,
                "failure_percentage": 50.0,
            },
            {
                "question_id": 1003,
                "question_title": "Question 1003",
                "question_statement": "Prompt 1003",
                "failure_count": 1,
                "failure_percentage": 100.0,
            },
        ]
        candidates = [
            item
            for item in all_candidates
            if item["failure_count"] >= minimum_failure_count and item["failure_percentage"] >= failure_percentage_threshold
        ]
        if limit is None:
            return candidates
        return candidates[:limit]


class _BuilderFakeExamsTable:
    def list_builder_metadata(self, exam_id):
        return {
            "question_types": ["single_select"],
            "tags": ["azure"],
            "topics": ["ai"],
        }


class _BuilderFakeDbManager:
    def __init__(self):
        self.attempts = _BuilderFakeAttemptsTable()
        self.questions = _BuilderFakeQuestionsTable()
        self.statistics = _BuilderFakeStatisticsTable()
        self.exams = _BuilderFakeExamsTable()

    def transaction(self):
        return nullcontext()


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


class AttemptServiceSubmissionTests(unittest.TestCase):
    def test_rejects_resubmitting_a_submitted_attempt(self):
        service = AttemptService(_SubmittedFakeDbManager())

        with self.assertRaisesRegex(ValueError, "Attempt is already submitted."):
            service.submit_attempt(55)


class AttemptServiceErrorFocusTests(unittest.TestCase):
    def setUp(self):
        self.db = _BuilderFakeDbManager()
        self.service = AttemptService(self.db)

    def test_error_focus_attempt_uses_ranked_personalized_candidates(self):
        attempt_id = self.service.create_attempt(
            7,
            3,
            {
                "selection_mode": "error_focus",
                "question_count": 2,
                "random_order": False,
            },
        )

        self.assertEqual(attempt_id, 901)
        self.assertEqual(
            [item["question_id"] for item in self.db.attempts.stored_snapshots],
            [1002, 1001],
        )
        self.assertEqual(self.db.attempts.created_payload["criteria"]["selection_mode"], "error_focus")
        self.assertEqual(
            self.db.attempts.created_payload["criteria"]["error_focus"]["failure_percentage_threshold"],
            40,
        )

    def test_error_focus_respects_existing_filters(self):
        self.service.create_attempt(
            7,
            3,
            {
                "selection_mode": "error_focus",
                "question_count": 1,
                "random_order": False,
                "difficulty": "advanced",
            },
        )

        self.assertEqual(
            [item["question_id"] for item in self.db.attempts.stored_snapshots],
            [1002],
        )

    def test_builder_meta_includes_error_focus_preview(self):
        payload = self.service.build_builder_meta(7, 3)

        self.assertEqual(payload["question_types"], ["single_select"])
        self.assertTrue(payload["error_focus"]["available"])
        self.assertEqual(payload["error_focus"]["available_question_count"], 2)
        self.assertEqual(payload["error_focus"]["failure_percentage_threshold"], 40)
        self.assertEqual(payload["error_focus"]["minimum_failure_count"], 2)
        self.assertEqual(payload["error_focus"]["preview_questions"][0]["question_id"], 1002)

    def test_error_focus_builder_meta_respects_failure_percentage_threshold(self):
        payload = self.service.build_builder_meta(7, 3, failure_percentage_threshold=60)

        self.assertEqual(payload["error_focus"]["failure_percentage_threshold"], 60)
        self.assertEqual(payload["error_focus"]["available_question_count"], 1)
        self.assertEqual(payload["error_focus"]["preview_questions"][0]["question_id"], 1002)

    def test_error_focus_builder_meta_excludes_single_failure_questions(self):
        payload = self.service.build_builder_meta(7, 3)

        self.assertEqual(
            [item["question_id"] for item in payload["error_focus"]["preview_questions"]],
            [1002, 1001],
        )


if __name__ == "__main__":
    unittest.main()
