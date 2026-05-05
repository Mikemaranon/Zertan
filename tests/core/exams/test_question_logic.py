import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.services_m.question_logic_service import (
    build_public_question,
    evaluate_question_response,
    normalize_question_payload,
)


class QuestionLogicTests(unittest.TestCase):
    def test_normalize_single_select_trims_fields_and_keeps_exactly_one_correct_option(self):
        payload = normalize_question_payload(
            {
                "type": "single_select",
                "statement": "  Pick the best answer.  ",
                "difficulty": " advanced ",
                "tags": [" azure ", "ai"],
                "topics": "vision, ai ",
                "options": [
                    {"key": "A", "text": "  Correct answer  ", "is_correct": True},
                    {"key": "B", "text": "Distractor", "is_correct": False},
                    {"key": "", "text": "Ignored option", "is_correct": False},
                ],
            }
        )

        self.assertEqual(payload["statement"], "Pick the best answer.")
        self.assertEqual(payload["difficulty"], "advanced")
        self.assertEqual(payload["tags"], ["azure", "ai"])
        self.assertEqual(payload["topics"], ["vision", "ai"])
        self.assertEqual(len(payload["options"]), 2)
        self.assertEqual(sum(1 for option in payload["options"] if option["is_correct"]), 1)

    def test_build_public_question_hides_choice_solutions_unless_requested(self):
        question = {
            "id": 101,
            "exam_id": 7,
            "type": "multiple_choice",
            "statement": "Select all correct options.",
            "options": [
                {"key": "A", "text": "Correct", "is_correct": True},
                {"key": "B", "text": "Incorrect", "is_correct": False},
            ],
            "tags": [],
            "topics": [],
            "assets": [],
            "config": {},
        }

        public_question = build_public_question(question, include_solution=False)
        solved_question = build_public_question(question, include_solution=True)

        self.assertNotIn("is_correct", public_question["options"][0])
        self.assertTrue(solved_question["options"][0]["is_correct"])

    def test_evaluate_multiple_choice_requires_full_selected_set(self):
        question = {
            "type": "multiple_choice",
            "options": [
                {"key": "A", "text": "One", "is_correct": True},
                {"key": "B", "text": "Two", "is_correct": False},
                {"key": "C", "text": "Three", "is_correct": True},
            ],
        }

        partial = evaluate_question_response(question, {"selected": ["A"]})
        exact = evaluate_question_response(question, {"selected": ["C", "A", "A"]})

        self.assertFalse(partial["is_correct"])
        self.assertTrue(exact["is_correct"])
        self.assertEqual(exact["correct_answer"], ["A", "C"])

    def test_evaluate_multiple_choice_rejects_extra_selected_option(self):
        question = {
            "type": "multiple_choice",
            "options": [
                {"key": "A", "text": "One", "is_correct": True},
                {"key": "B", "text": "Two", "is_correct": False},
                {"key": "C", "text": "Three", "is_correct": True},
            ],
        }

        result = evaluate_question_response(question, {"selected": ["A", "B", "C"]})

        self.assertFalse(result["is_correct"])
        self.assertFalse(result["omitted"])
        self.assertEqual(result["correct_answer"], ["A", "C"])

    def test_normalize_hot_spot_dropdowns_orders_them_and_requires_assets(self):
        payload = normalize_question_payload(
            {
                "type": "hot_spot",
                "statement": "Identify the correct regions.",
                "assets": [{"file_path": "assets/hotspot.png"}],
                "config": {
                    "dropdowns": [
                        {
                            "id": "bottom",
                            "order": 2,
                            "label": "Bottom label",
                            "options": ["A", "B"],
                            "correct_option": "B",
                        },
                        {
                            "id": "top",
                            "order": 1,
                            "label": "Top label",
                            "options": ["Yes", "No"],
                            "correct_option": "Yes",
                        },
                    ]
                },
            }
        )

        self.assertEqual(
            [dropdown["id"] for dropdown in payload["config"]["dropdowns"]],
            ["top", "bottom"],
        )

    def test_evaluate_hot_spot_accepts_boundary_coordinates_and_rejects_points_outside_region(self):
        question = {
            "type": "hot_spot",
            "config": {
                "regions": [
                    {"x": 10, "y": 20, "width": 30, "height": 40},
                ]
            },
        }

        boundary = evaluate_question_response(question, {"x": 40, "y": 60})
        outside = evaluate_question_response(question, {"x": 40.01, "y": 60.01})

        self.assertTrue(boundary["is_correct"])
        self.assertFalse(outside["is_correct"])
        self.assertEqual(boundary["correct_answer"], question["config"]["regions"])

    def test_evaluate_hot_spot_dropdown_requires_every_selection(self):
        question = {
            "type": "hot_spot",
            "config": {
                "dropdowns": [
                    {
                        "id": "region-a",
                        "order": 1,
                        "label": "Region A",
                        "options": ["One", "Two"],
                        "correct_option": "One",
                    },
                    {
                        "id": "region-b",
                        "order": 2,
                        "label": "Region B",
                        "options": ["Left", "Right"],
                        "correct_option": "Right",
                    },
                ]
            },
        }

        partial = evaluate_question_response(
            question,
            {"selections": {"region-a": "One", "region-b": ""}},
        )
        omitted = evaluate_question_response(
            question,
            {"selections": {"region-a": "", "region-b": ""}},
        )

        self.assertFalse(partial["is_correct"])
        self.assertFalse(partial["omitted"])
        self.assertTrue(omitted["omitted"])
        self.assertEqual(
            partial["correct_answer"],
            [
                {"id": "region-a", "order": 1, "label": "Region A", "correct_option": "One"},
                {"id": "region-b", "order": 2, "label": "Region B", "correct_option": "Right"},
            ],
        )

    def test_build_public_question_hides_hot_spot_and_drag_drop_solutions_until_requested(self):
        hot_spot_question = {
            "id": 201,
            "exam_id": 11,
            "type": "hot_spot",
            "statement": "Pick the correct zones.",
            "assets": [{"file_path": "assets/hotspot.png"}],
            "config": {
                "dropdowns": [
                    {
                        "id": "zone-1",
                        "order": 1,
                        "label": "Zone 1",
                        "options": ["A", "B"],
                        "correct_option": "B",
                    }
                ]
            },
        }
        drag_drop_question = {
            "id": 202,
            "exam_id": 11,
            "type": "drag_drop",
            "statement": "Map each item to its destination.",
            "config": {
                "mode": "U",
                "items": [{"id": "item-1", "label": "Item 1"}],
                "destinations": [{"id": "destination-1", "label": "Destination 1"}],
                "mappings": {"destination-1": "item-1"},
            },
        }

        public_hot_spot = build_public_question(hot_spot_question, include_solution=False)
        solved_hot_spot = build_public_question(hot_spot_question, include_solution=True)
        public_drag_drop = build_public_question(drag_drop_question, include_solution=False)
        solved_drag_drop = build_public_question(drag_drop_question, include_solution=True)

        self.assertNotIn("correct_option", public_hot_spot["config"]["dropdowns"][0])
        self.assertEqual(solved_hot_spot["config"]["dropdowns"][0]["correct_option"], "B")
        self.assertNotIn("mappings", public_drag_drop["config"])
        self.assertEqual(solved_drag_drop["config"]["mappings"], {"destination-1": "item-1"})

    def test_evaluate_drag_drop_accepts_item_to_destination_mapping_shape(self):
        question = {
            "type": "drag_drop",
            "config": {
                "mode": "U",
                "items": [{"id": "item-1", "label": "Item 1"}],
                "destinations": [{"id": "destination-1", "label": "Destination 1"}],
                "mappings": {"destination-1": "item-1"},
            },
        }

        result = evaluate_question_response(
            question,
            {"mappings": {"item-1": "destination-1"}},
        )

        self.assertTrue(result["is_correct"])
        self.assertEqual(result["correct_answer"], {"destination-1": "item-1"})

    def test_evaluate_drag_drop_rejects_partial_invalid_and_duplicate_destination_mappings(self):
        question = {
            "type": "drag_drop",
            "config": {
                "mode": "U",
                "items": [
                    {"id": "item-1", "label": "Item 1"},
                    {"id": "item-2", "label": "Item 2"},
                ],
                "destinations": [
                    {"id": "destination-1", "label": "Destination 1"},
                    {"id": "destination-2", "label": "Destination 2"},
                ],
                "mappings": {
                    "destination-1": "item-1",
                    "destination-2": "item-2",
                },
            },
        }

        partial = evaluate_question_response(question, {"mappings": {"item-1": "destination-1"}})
        invalid_destination = evaluate_question_response(question, {"mappings": {"item-1": "unknown-destination"}})
        duplicate_destination = evaluate_question_response(
            question,
            {"mappings": {"item-1": "destination-1", "item-2": "destination-1"}},
        )

        self.assertFalse(partial["is_correct"])
        self.assertFalse(invalid_destination["is_correct"])
        self.assertFalse(duplicate_destination["is_correct"])

    def test_normalize_drag_drop_unique_mode_rejects_reused_items(self):
        with self.assertRaisesRegex(ValueError, "cannot reuse the same item"):
            normalize_question_payload(
                {
                    "type": "drag_drop",
                    "statement": "Map each item exactly once.",
                    "config": {
                        "mode": "U",
                        "items": [
                            {"id": "item-1", "label": "Item 1"},
                            {"id": "item-2", "label": "Item 2"},
                        ],
                        "destinations": [
                            {"id": "destination-1", "label": "Destination 1"},
                            {"id": "destination-2", "label": "Destination 2"},
                        ],
                        "mappings": {
                            "destination-1": "item-1",
                            "destination-2": "item-1",
                        },
                    },
                }
            )


if __name__ == "__main__":
    unittest.main()
