from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_SERVER_ROOT = PROJECT_ROOT / "app" / "web_server"
HOTSPOT_ASSET_PATH = "web_app/static/assets/zt-100-hotspot.svg"
QUESTION_TYPES = ("single_select", "multiple_choice", "hot_spot", "drag_drop")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(WEB_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.data_m.db_manager import DBManager


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a synthetic mixed-type exam for manual pagination and workflow testing."
    )
    parser.add_argument("--code", default="ZT-400", help="Unique exam code to create.")
    parser.add_argument("--title", default="Synthetic 400 Mixed Question Type Test", help="Exam title.")
    parser.add_argument("--provider", default="Zertan", help="Provider label shown in the catalog.")
    parser.add_argument(
        "--count-per-type",
        type=int,
        default=100,
        help="Number of questions to generate for each supported question type.",
    )
    parser.add_argument("--created-by", type=int, default=1, help="User id used as exam creator.")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete an existing exam with the same code before recreating it.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.count_per_type < 1:
        raise SystemExit("Question count per type must be greater than zero.")

    db_manager = DBManager()
    existing_exam = get_exam_by_code(db_manager, args.code)
    if existing_exam:
        if not args.replace:
            raise SystemExit(
                f"Exam code {args.code} already exists (id={existing_exam['id']}). Use --replace to recreate it."
            )
        db_manager.exams.delete(existing_exam["id"])

    total_questions = args.count_per_type * len(QUESTION_TYPES)
    exam_id = db_manager.exams.create(
        {
            "code": args.code,
            "title": args.title,
            "provider": args.provider,
            "description": (
                "Synthetic bank generated for pagination and mixed question-type validation "
                f"with {total_questions} questions."
            ),
            "difficulty": "intermediate",
            "status": "published",
            "tags": ["synthetic", "pagination", "mixed-types"],
        },
        args.created_by,
    )

    question_number = 1
    for question_type in QUESTION_TYPES:
        for index_within_type in range(1, args.count_per_type + 1):
            payload = build_question_payload(question_number, question_type, index_within_type)
            db_manager.questions.create(exam_id, payload)
            question_number += 1

    exam = db_manager.exams.get(exam_id)
    print(
        f"Created exam {exam['code']} (id={exam_id}) with {exam['question_count']} questions "
        f"across {len(QUESTION_TYPES)} types."
    )


def build_question_payload(question_number, question_type, index_within_type):
    code = f"Q-{question_number:03d}"
    base_payload = {
        "title": code,
        "difficulty": "intermediate",
        "status": "active",
        "position": question_number,
        "tags": ["synthetic", "pagination", question_type],
        "topics": [question_type],
        "assets": [],
        "config": {},
        "options": [],
    }

    if question_type == "single_select":
        return {
            **base_payload,
            "type": "single_select",
            "statement": f"{code}. Synthetic single select question {index_within_type}.",
            "explanation": "Synthetic single select question generated for bulk pagination validation.",
            "options": [
                {"key": "A", "text": "Correct option", "is_correct": True},
                {"key": "B", "text": "Distractor option", "is_correct": False},
                {"key": "C", "text": "Distractor option", "is_correct": False},
                {"key": "D", "text": "Distractor option", "is_correct": False},
            ],
        }

    if question_type == "multiple_choice":
        return {
            **base_payload,
            "type": "multiple_choice",
            "statement": f"{code}. Synthetic multiple choice question {index_within_type}.",
            "explanation": "Synthetic multiple choice question generated for bulk pagination validation.",
            "options": [
                {"key": "A", "text": "Correct option A", "is_correct": True},
                {"key": "B", "text": "Distractor option B", "is_correct": False},
                {"key": "C", "text": "Correct option C", "is_correct": True},
                {"key": "D", "text": "Distractor option D", "is_correct": False},
            ],
        }

    if question_type == "hot_spot":
        return {
            **base_payload,
            "type": "hot_spot",
            "statement": f"{code}. Synthetic hot spot question {index_within_type}.",
            "explanation": "Synthetic hot spot question generated for bulk pagination validation.",
            "assets": [
                {
                    "asset_type": "image",
                    "file_path": HOTSPOT_ASSET_PATH,
                    "meta": {"alt": f"{code} synthetic hot spot diagram"},
                }
            ],
            "config": {
                "dropdowns": [
                    {
                        "id": "dropdown-1",
                        "order": 1,
                        "label": "Marker 1",
                        "options": ["Study mode", "Exam mode", "Admin panel"],
                        "correct_option": "Study mode",
                    },
                    {
                        "id": "dropdown-2",
                        "order": 2,
                        "label": "Marker 2",
                        "options": ["Study mode", "Exam mode", "Import package"],
                        "correct_option": "Exam mode",
                    },
                ]
            },
        }

    if question_type == "drag_drop":
        is_reusable = index_within_type % 2 == 0
        return {
            **base_payload,
            "type": "drag_drop",
            "statement": f"{code}. Synthetic drag and drop question {index_within_type}.",
            "explanation": "Synthetic drag and drop question generated for bulk pagination validation.",
            "config": build_drag_drop_config(is_reusable),
        }

    raise ValueError(f"Unsupported question type: {question_type}")


def build_drag_drop_config(is_reusable):
    if is_reusable:
        return {
            "mode": "R",
            "items": [
                {"id": "item-study", "label": "Study mode"},
                {"id": "item-exam", "label": "Exam mode"},
            ],
            "destinations": [
                {"id": "dest-correction", "label": "Immediate answer correction"},
                {"id": "dest-kpi", "label": "Official KPI storage"},
                {"id": "dest-filters", "label": "Flexible filtering while reviewing content"},
            ],
            "mappings": {
                "dest-correction": "item-study",
                "dest-kpi": "item-exam",
                "dest-filters": "item-study",
            },
        }

    return {
        "mode": "U",
        "items": [
            {"id": "item-admin", "label": "Administrator"},
            {"id": "item-reviewer", "label": "Reviewer"},
            {"id": "item-user", "label": "User"},
        ],
        "destinations": [
            {"id": "dest-users", "label": "Manage users and assign roles"},
            {"id": "dest-content", "label": "Maintain question content"},
            {"id": "dest-attempts", "label": "Run exams and view personal results"},
        ],
        "mappings": {
            "dest-users": "item-admin",
            "dest-content": "item-reviewer",
            "dest-attempts": "item-user",
        },
    }


def get_exam_by_code(db_manager, code):
    _, row = db_manager.db.execute(
        """
        SELECT id, code, title
        FROM exams
        WHERE lower(code) = lower(?)
        """,
        (code,),
        fetchone=True,
    )
    if not row:
        return None
    return {
        "id": row["id"],
        "code": row["code"],
        "title": row["title"],
    }


if __name__ == "__main__":
    main()
