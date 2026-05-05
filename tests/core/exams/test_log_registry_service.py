import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.services_m.log_registry_service import LogRegistryService


class _FakeLogRegistryTable:
    def __init__(self):
        self.entries = []

    def create(self, **payload):
        self.entries.append(payload)


class _FakeDbManager:
    def __init__(self):
        self.log_registry = _FakeLogRegistryTable()


class LogRegistryServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = _FakeDbManager()
        self.service = LogRegistryService(self.db)
        self.actor = {
            "id": 7,
            "login_name": "reviewer.user",
            "display_name": "Reviewer User",
            "role": "reviewer",
        }
        self.exam = {
            "id": 21,
            "code": "AI-102",
            "title": "Azure AI",
            "provider": "Microsoft",
            "description": "Study exam",
            "official_url": "https://example.com/ai-102",
            "difficulty": "advanced",
            "status": "published",
            "tags": ["ai", "azure"],
            "scope_groups": [{"id": 3, "code": "grp-review", "name": "Review Team"}],
        }

    def test_record_exam_change_builds_snapshots_sorted_tags_and_default_detail(self):
        before_exam = {**self.exam, "title": "Old title", "tags": ["azure", "ai"]}
        after_exam = {**self.exam, "title": "New title", "tags": ["ai", "azure"]}

        self.service.record_exam_change(
            actor_user=self.actor,
            action="update",
            before_exam=before_exam,
            after_exam=after_exam,
        )

        entry = self.db.log_registry.entries[0]
        self.assertEqual(entry["entity_type"], "exam")
        self.assertEqual(entry["details"], "Exam update")
        self.assertEqual(entry["exam_code"], "AI-102")
        self.assertEqual(entry["before_snapshot"]["tags"], ["ai", "azure"])
        self.assertEqual(entry["after_snapshot"]["title"], "New title")
        self.assertIn('"title": "Old title"', entry["before_content_text"])
        self.assertIn('"title": "New title"', entry["after_content_text"])
        self.assertIn("--- before", entry["diff_text"])
        self.assertIn("+++ after", entry["diff_text"])

    def test_record_question_change_builds_label_default_detail_and_asset_snapshot(self):
        question = {
            "id": 101,
            "exam_id": self.exam["id"],
            "position": 4,
            "type": "single_select",
            "title": "Choose the right service",
            "statement": "Which service fits best?",
            "explanation": "Use the managed service.",
            "difficulty": "intermediate",
            "status": "active",
            "tags": ["cloud", "ai"],
            "topics": ["vision", "search"],
            "config": {},
            "options": [
                {"key": "A", "text": "Correct", "is_correct": True},
                {"key": "B", "text": "Wrong", "is_correct": False},
            ],
            "assets": [
                {"asset_type": "image", "file_path": "questions/21/diagram.png", "meta": {"alt": "Diagram"}},
            ],
            "source_json_path": "questions/q_0004.json",
        }

        self.service.record_question_change(
            actor_user=self.actor,
            action="create",
            exam=self.exam,
            after_question=question,
        )

        entry = self.db.log_registry.entries[0]
        self.assertEqual(entry["entity_type"], "question")
        self.assertEqual(entry["details"], "Question create")
        self.assertEqual(entry["question_label"], "Question 4 · Choose the right service")
        self.assertEqual(entry["question_type"], "single_select")
        self.assertEqual(entry["after_snapshot"]["tags"], ["ai", "cloud"])
        self.assertEqual(entry["after_snapshot"]["topics"], ["search", "vision"])
        self.assertEqual(entry["after_snapshot"]["assets"][0]["file_path"], "questions/21/diagram.png")
        self.assertIn('"asset_type": "image"', entry["after_content_text"])

    def test_build_question_label_and_render_snapshot_cover_empty_values(self):
        self.assertEqual(self.service._build_question_label(None), "Question")
        self.assertEqual(self.service._build_question_label({"position": 2, "title": ""}), "Question 2")
        self.assertEqual(self.service._render_snapshot(None), "")
        self.assertEqual(self.service._default_detail("delete", "question"), "Question delete")


if __name__ == "__main__":
    unittest.main()
