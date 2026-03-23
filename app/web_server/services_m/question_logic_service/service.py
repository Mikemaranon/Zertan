from .evaluation import evaluate_question_response
from .normalization import normalize_question_payload
from .presentation import build_public_question


class QuestionLogicService:
    def normalize_question_payload(self, raw_payload):
        return normalize_question_payload(raw_payload)

    def evaluate_question_response(self, question, response):
        return evaluate_question_response(question, response)

    def build_public_question(self, question, include_solution=False):
        return build_public_question(question, include_solution=include_solution)
