import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.data_m import DBManager
from app.web_server.server import create_app


class QuestionsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-questions-api-")
        self.addCleanup(self.temp_dir.cleanup)
        self._set_env("ZERTAN_DATA_DIR", self.temp_dir.name)
        self._set_env("ZERTAN_DB_PATH", str(Path(self.temp_dir.name) / "database" / "test.db"))
        self._set_env("ZERTAN_MEDIA_ROOT", str(Path(self.temp_dir.name) / "assets"))
        self._set_env("ZERTAN_SEED_DEMO_CONTENT", "0")
        self._set_env("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", "questions-api-admin-password")
        self.addCleanup(self._restore_env)

        self.app = create_app(run_server=False)
        self.db = DBManager()
        self.admin = self.db.users.get_by_login_name("admin")
        self.reviewer = self._create_user("question.reviewer", "Question Reviewer", role="reviewer")
        self.examiner = self._create_user("question.examiner", "Question Examiner", role="examiner")
        self.student = self._create_user("question.student", "Question Student", role="user")
        self.outsider = self._create_user("question.outsider", "Question Outsider", role="reviewer")

        self.group_alpha = self.db.groups.create(
            "Question Alpha",
            user_ids=[self.reviewer["id"], self.examiner["id"], self.student["id"]],
        )
        self.group_beta = self.db.groups.create(
            "Question Beta",
            user_ids=[self.outsider["id"]],
        )

        self.exam_id = self.db.exams.create(
            {
                "code": "QST-100",
                "title": "Question Management Exam",
                "provider": "Zertan",
                "description": "Scoped question API integration test.",
                "difficulty": "intermediate",
                "status": "published",
                "tags": ["questions"],
                "group_ids": [self.group_alpha["id"]],
            },
            self.admin["id"],
            allowed_group_ids=[self.group_alpha["id"], self.group_beta["id"]],
            allow_global=True,
        )
        self.question_id = self.db.questions.create(
            self.exam_id,
            {
                "type": "single_select",
                "title": "Visibility question",
                "statement": "Who should see the correct answer immediately?",
                "explanation": "Only review-capable roles should receive the stored solution payload.",
                "difficulty": "intermediate",
                "status": "active",
                "position": 1,
                "tags": ["questions"],
                "topics": ["visibility"],
                "options": [
                    {"key": "A", "text": "Reviewer", "is_correct": True},
                    {"key": "B", "text": "Student", "is_correct": False},
                ],
            },
        )
        self.other_exam_id = self.db.exams.create(
            {
                "code": "QST-200",
                "title": "Out of Scope Exam",
                "provider": "Zertan",
                "description": "Used to verify question scope restrictions.",
                "difficulty": "intermediate",
                "status": "published",
                "tags": ["questions"],
                "group_ids": [self.group_beta["id"]],
            },
            self.admin["id"],
            allowed_group_ids=[self.group_alpha["id"], self.group_beta["id"]],
            allow_global=True,
        )
        self.other_question_id = self.db.questions.create(
            self.other_exam_id,
            {
                "type": "single_select",
                "title": "Out of scope question",
                "statement": "Should the outsider reviewer manage this?",
                "explanation": "Only reviewers within scope should manage this question.",
                "difficulty": "intermediate",
                "status": "active",
                "position": 1,
                "tags": ["scope"],
                "topics": ["scope"],
                "options": [
                    {"key": "A", "text": "Yes", "is_correct": True},
                    {"key": "B", "text": "No", "is_correct": False},
                ],
            },
        )

    def test_regular_user_get_question_hides_solution_and_can_check_answer(self):
        with self.app.test_client() as client:
            self._login(client, "question.student")
            get_response = client.get(f"/api/questions/{self.question_id}")
            check_response = client.post(
                f"/api/questions/{self.question_id}/check",
                json={"response": {"selected": "A"}},
            )

        self.assertEqual(get_response.status_code, 200)
        question = get_response.get_json()["question"]
        self.assertTrue(all("is_correct" not in option for option in question["options"]))

        self.assertEqual(check_response.status_code, 200)
        result = check_response.get_json()["result"]
        self.assertTrue(result["is_correct"])
        self.assertFalse(result["omitted"])
        self.assertEqual(result["correct_answer"], "A")
        self.assertEqual(
            result["explanation"],
            "Only review-capable roles should receive the stored solution payload.",
        )

    def test_reviewer_can_list_create_update_and_archive_questions(self):
        with self.app.test_client() as client:
            self._login(client, "question.reviewer")
            list_response = client.get(f"/api/exams/{self.exam_id}/questions")
            create_response = client.post(
                f"/api/exams/{self.exam_id}/questions",
                json={
                    "type": "single_select",
                    "title": "Created question",
                    "statement": "Can a reviewer create a question?",
                    "explanation": "Yes, within the managed scope.",
                    "difficulty": "advanced",
                    "status": "active",
                    "position": 2,
                    "tags": ["created"],
                    "topics": ["workflow"],
                    "options": [
                        {"key": "A", "text": "Yes", "is_correct": True},
                        {"key": "B", "text": "No", "is_correct": False},
                    ],
                },
            )

            self.assertEqual(list_response.status_code, 200)
            self.assertFalse(list_response.get_json()["exam"]["can_delete_questions"])
            self.assertEqual(len(list_response.get_json()["questions"]), 1)

            self.assertEqual(create_response.status_code, 201)
            created_question_id = create_response.get_json()["question"]["id"]

            update_response = client.put(
                f"/api/questions/{created_question_id}",
                json={
                    "type": "single_select",
                    "title": "Created question updated",
                    "statement": "Can a reviewer update a question?",
                    "explanation": "Yes, still within scope.",
                    "difficulty": "intermediate",
                    "status": "active",
                    "position": 2,
                    "tags": ["updated"],
                    "topics": ["workflow"],
                    "options": [
                        {"key": "A", "text": "Yes", "is_correct": True},
                        {"key": "B", "text": "No", "is_correct": False},
                    ],
                },
            )
            archive_response = client.post(f"/api/questions/{created_question_id}/archive")

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(archive_response.status_code, 200)
        updated_question = self.db.questions.get(created_question_id, include_answers=True)
        self.assertEqual(updated_question["title"], "Created question updated")
        self.assertEqual(updated_question["tags"], ["updated"])
        self.assertEqual(updated_question["status"], "archived")

    def test_reviewer_cannot_delete_question_but_examiner_can(self):
        with self.app.test_client() as reviewer_client:
            self._login(reviewer_client, "question.reviewer")
            reviewer_response = reviewer_client.delete(f"/api/questions/{self.question_id}")

        with self.app.test_client() as examiner_client:
            self._login(examiner_client, "question.examiner")
            examiner_response = examiner_client.delete(f"/api/questions/{self.question_id}")

        self.assertEqual(reviewer_response.status_code, 403)
        self.assertEqual(examiner_response.status_code, 200)
        self.assertIsNone(self.db.questions.get(self.question_id, include_answers=True))

    def test_reviewer_receives_solution_payload_when_fetching_question(self):
        with self.app.test_client() as client:
            self._login(client, "question.reviewer")
            response = client.get(f"/api/questions/{self.question_id}")

        self.assertEqual(response.status_code, 200)
        question = response.get_json()["question"]
        self.assertTrue(any(option.get("is_correct") for option in question["options"]))

    def test_reviewer_cannot_manage_questions_outside_scope(self):
        with self.app.test_client() as client:
            self._login(client, "question.reviewer")
            get_response = client.get(f"/api/questions/{self.other_question_id}")
            create_response = client.post(
                f"/api/exams/{self.other_exam_id}/questions",
                json={
                    "type": "single_select",
                    "title": "Should fail",
                    "statement": "This reviewer is outside scope.",
                    "options": [
                        {"key": "A", "text": "Yes", "is_correct": True},
                        {"key": "B", "text": "No", "is_correct": False},
                    ],
                },
            )

        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(create_response.status_code, 403)

    def _create_user(self, login_name, display_name, *, role):
        self.db.users.create(
            login_name,
            display_name,
            self._password_hash(),
            role=role,
            status="active",
        )
        return self.db.users.get_by_login_name(login_name)

    def _login(self, client, login_name, password="valid-password"):
        response = client.post("/api/auth/login", json={"login_name": login_name, "password": password})
        self.assertEqual(response.status_code, 200)

    def _password_hash(self):
        from werkzeug.security import generate_password_hash

        return generate_password_hash("valid-password")

    def _set_env(self, key, value):
        original = os.environ.get(key)
        os.environ[key] = value
        setattr(self, f"_orig_{key}", original)

    def _restore_env(self):
        for key in (
            "ZERTAN_DATA_DIR",
            "ZERTAN_DB_PATH",
            "ZERTAN_MEDIA_ROOT",
            "ZERTAN_SEED_DEMO_CONTENT",
            "ZERTAN_BOOTSTRAP_ADMIN_PASSWORD",
        ):
            original = getattr(self, f"_orig_{key}", None)
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


if __name__ == "__main__":
    unittest.main()
