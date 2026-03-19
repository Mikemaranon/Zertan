from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_SERVER_ROOT = PROJECT_ROOT / "app" / "web_server"

if str(WEB_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_SERVER_ROOT))

from data_m.db_manager import DBManager  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a synthetic exam with a fixed number of questions.")
    parser.add_argument("--code", default="ZT-300", help="Unique exam code to create.")
    parser.add_argument("--title", default="Synthetic 300 Question Pagination Test", help="Exam title.")
    parser.add_argument("--provider", default="Zertan", help="Provider label shown in the catalog.")
    parser.add_argument("--count", type=int, default=300, help="Number of questions to generate.")
    parser.add_argument("--created-by", type=int, default=1, help="User id used as exam creator.")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete an existing exam with the same code before recreating it.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.count < 1:
        raise SystemExit("Question count must be greater than zero.")

    db_manager = DBManager()
    existing_exam = get_exam_by_code(db_manager, args.code)
    if existing_exam:
        if not args.replace:
            raise SystemExit(f"Exam code {args.code} already exists (id={existing_exam['id']}). Use --replace to recreate it.")
        db_manager.exams.delete(existing_exam["id"])

    exam_id = db_manager.exams.create(
        {
            "code": args.code,
            "title": args.title,
            "provider": args.provider,
            "description": f"Synthetic bank generated for pagination testing with {args.count} questions.",
            "difficulty": "intermediate",
            "status": "published",
            "tags": ["synthetic", "pagination"],
        },
        args.created_by,
    )

    for index in range(1, args.count + 1):
        code = f"Q-{index:03d}"
        db_manager.questions.create(
            exam_id,
            {
                "type": "single_select",
                "title": code,
                "statement": f"{code}. Synthetic pagination test question {index}.",
                "explanation": "Synthetic question generated for pagination and bulk-flow validation.",
                "difficulty": "intermediate",
                "status": "active",
                "position": index,
                "tags": ["synthetic", "pagination"],
                "topics": ["bulk-generation"],
                "options": [
                    {"key": "A", "text": "Option A", "is_correct": True},
                    {"key": "B", "text": "Option B", "is_correct": False},
                ],
                "config": {},
                "assets": [],
            },
        )

    exam = db_manager.exams.get(exam_id)
    print(f"Created exam {exam['code']} (id={exam_id}) with {exam['question_count']} questions.")


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
