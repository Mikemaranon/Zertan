import random

from ..question_logic_service import QuestionLogicService
from .constants import QUESTIONS_PER_PAGE


class AttemptService:
    def __init__(self, db_manager, question_logic=None):
        self.db = db_manager
        self.question_logic = question_logic or QuestionLogicService()

    def create_attempt(self, exam_id, user_id, criteria):
        filters = {
            "tags": criteria.get("tags", {"include": [], "exclude": []}),
            "topics": criteria.get("topics", {"include": [], "exclude": []}),
            "question_types": criteria.get("question_types", {"include": [], "exclude": []}),
            "difficulty": criteria.get("difficulty"),
        }
        question_ids = self.db.questions.list_filtered_ids(exam_id, filters)
        if not question_ids:
            raise ValueError("No questions match the selected criteria.")

        requested_count = int(criteria.get("question_count") or len(question_ids))
        if requested_count < 1:
            raise ValueError("Question count must be greater than zero.")
        if requested_count > len(question_ids):
            raise ValueError("Requested question count exceeds matching questions.")

        random_order = bool(criteria.get("random_order", True))
        if random_order:
            random.shuffle(question_ids)

        selected_ids = question_ids[:requested_count]
        attempt_id = self.db.attempts.create(
            exam_id=exam_id,
            user_id=user_id,
            criteria=criteria,
            question_count=requested_count,
            random_order=random_order,
            time_limit_minutes=criteria.get("time_limit_minutes"),
        )
        snapshots = []
        for full_question in self.db.questions.get_many(selected_ids, include_answers=True):
            snapshots.append(
                {
                    "question_id": full_question["id"],
                    "snapshot": self.question_logic.build_public_question(full_question, include_solution=True),
                }
            )
        self.db.attempts.add_questions(attempt_id, snapshots)
        return attempt_id

    def get_attempt_payload(self, attempt_id, page_number=None):
        attempt = self.db.attempts.get_attempt(attempt_id)
        if not attempt:
            return None
        total_pages = max(1, (int(attempt["question_count"] or 0) + QUESTIONS_PER_PAGE - 1) // QUESTIONS_PER_PAGE)
        current_page = min(max(int(page_number or 1), 1), total_pages)
        questions = self.db.attempts.get_attempt_questions(attempt_id, page_number=current_page)
        public_questions = []
        for item in questions:
            question = item["snapshot"]
            if question["type"] in {"single_select", "multiple_choice"}:
                question["options"] = [
                    {"key": option["key"], "text": option["text"]} for option in question.get("options", [])
                ]
            if question["type"] == "hot_spot":
                dropdowns = question.get("config", {}).get("dropdowns") or []
                if dropdowns:
                    question["config"] = {
                        "dropdowns": [
                            {
                                "id": dropdown["id"],
                                "order": dropdown["order"],
                                "label": dropdown.get("label") or f"Dropdown {dropdown['order']}",
                                "options": dropdown.get("options", []),
                            }
                            for dropdown in dropdowns
                        ]
                    }
                else:
                    question["config"] = {}
            if question["type"] == "drag_drop":
                question["config"] = {
                    "mode": question.get("config", {}).get("mode", "U"),
                    "items": question.get("config", {}).get("items", []),
                    "destinations": question.get("config", {}).get("destinations", []),
                }
            public_questions.append(
                {
                    "attempt_question_id": item["attempt_question_id"],
                    "question_id": item["question_id"],
                    "question_order": item["question_order"],
                    "page_number": item["page_number"],
                    "question": question,
                    "response": item["response"],
                    "is_correct": item["is_correct"],
                    "omitted": item["omitted"],
                }
            )
        return {
            "attempt": attempt,
            "questions": public_questions,
            "current_page": current_page,
            "page_size": QUESTIONS_PER_PAGE,
            "total_pages": total_pages,
        }

    def save_answers(self, attempt_id, answers):
        stored_questions = {
            item["attempt_question_id"]: item for item in self.db.attempts.get_attempt_questions(attempt_id)
        }
        for answer in answers:
            attempt_question_id = int(answer["attempt_question_id"])
            question = stored_questions.get(attempt_question_id)
            if not question:
                continue
            response = answer.get("response")
            omitted = response in (None, {}, [])
            self.db.attempts.save_response(
                attempt_question_id=attempt_question_id,
                attempt_id=attempt_id,
                question_id=question["question_id"],
                response=response,
                omitted=omitted,
            )

    def submit_attempt(self, attempt_id):
        questions = self.db.attempts.get_attempt_questions(attempt_id)
        correct_count = 0
        incorrect_count = 0
        omitted_count = 0

        for item in questions:
            evaluation = self.question_logic.evaluate_question_response(item["snapshot"], item["response"])
            self.db.attempts.finalize_answer(
                attempt_question_id=item["attempt_question_id"],
                is_correct=evaluation["is_correct"],
                score=evaluation["score"],
                omitted=evaluation["omitted"],
            )
            if evaluation["omitted"]:
                omitted_count += 1
            elif evaluation["is_correct"]:
                correct_count += 1
            else:
                incorrect_count += 1

        total = len(questions) or 1
        score_percent = round((correct_count / total) * 100, 2)
        self.db.attempts.mark_submitted(attempt_id, correct_count, incorrect_count, omitted_count, score_percent)
        return self.get_result_payload(attempt_id)

    def get_result_payload(self, attempt_id):
        attempt = self.db.attempts.get_attempt(attempt_id)
        if not attempt:
            return None
        questions = self.db.attempts.get_attempt_questions(attempt_id)
        detailed = []
        for item in questions:
            evaluation = self.question_logic.evaluate_question_response(item["snapshot"], item["response"])
            detailed.append(
                {
                    "attempt_question_id": item["attempt_question_id"],
                    "question_order": item["question_order"],
                    "response": item["response"],
                    "question": item["snapshot"],
                    "result": evaluation,
                }
            )
        return {
            "attempt": attempt,
            "questions": detailed,
        }
