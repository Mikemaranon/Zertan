import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.data_m.database import Database
from app.web_server.data_m.db_methods.t_exams import ExamsTable
from app.web_server.data_m.db_methods.t_questions import QuestionsTable


class _CountingDatabase:
    def __init__(self, inner):
        self.inner = inner
        self.queries = []

    def execute(self, query, params=(), *, fetchone=False, fetchall=False):
        self.queries.append(" ".join(str(query).split()))
        return self.inner.execute(query, params, fetchone=fetchone, fetchall=fetchall)

    def __getattr__(self, name):
        return getattr(self.inner, name)


class DatabaseRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-db-runtime-")
        self.addCleanup(self.temp_dir.cleanup)
        self._set_env("ZERTAN_DATA_DIR", self.temp_dir.name)
        self._set_env("ZERTAN_DB_PATH", str(Path(self.temp_dir.name) / "runtime" / "test.db"))
        self._set_env("ZERTAN_MEDIA_ROOT", str(Path(self.temp_dir.name) / "assets"))
        self._set_env("ZERTAN_SEED_DEMO_CONTENT", "0")
        self.addCleanup(self._restore_env)

    def test_fresh_database_requires_bootstrap_password_when_demo_seed_is_disabled(self):
        os.environ.pop("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", None)

        with self.assertRaisesRegex(RuntimeError, "ZERTAN_BOOTSTRAP_ADMIN_PASSWORD"):
            Database()

    def test_fresh_database_seeds_only_bootstrap_admin_when_password_is_configured(self):
        self._set_env("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", "runtime-admin-password")

        database = Database()

        _, admin_row = database.execute(
            "SELECT login_name, role FROM users WHERE login_name = ?",
            ("admin",),
            fetchone=True,
        )
        _, exam_row = database.execute("SELECT COUNT(*) AS total FROM exams", fetchone=True)

        self.assertEqual(admin_row["login_name"], "admin")
        self.assertEqual(admin_row["role"], "administrator")
        self.assertEqual(exam_row["total"], 0)

    def test_questions_table_lists_exam_with_batched_queries(self):
        database = self._build_seeded_database()
        exam_id, first_question_id, second_question_id = self._create_exam_with_questions(database)

        counting_db = _CountingDatabase(database)
        questions = QuestionsTable(counting_db).list_for_exam(exam_id, include_answers=False)

        self.assertEqual([question["id"] for question in questions], [first_question_id, second_question_id])
        self.assertEqual(len(counting_db.queries), 5)
        self.assertEqual(questions[0]["tags"], ["governance"])
        self.assertEqual(questions[1]["topics"], ["storage"])
        self.assertTrue(all("is_correct" not in option for option in questions[0]["options"]))

    def test_questions_table_get_many_preserves_requested_order(self):
        database = self._build_seeded_database()
        exam_id, first_question_id, second_question_id = self._create_exam_with_questions(database)

        counting_db = _CountingDatabase(database)
        questions = QuestionsTable(counting_db).get_many(
            [second_question_id, first_question_id],
            include_answers=True,
        )

        self.assertEqual(exam_id, questions[0]["exam_id"])
        self.assertEqual([question["id"] for question in questions], [second_question_id, first_question_id])
        self.assertEqual(len(counting_db.queries), 5)
        self.assertIn("is_correct", questions[0]["options"][0])

    def test_schema_creates_indexes_for_hot_paths(self):
        database = self._build_seeded_database()
        expected_indexes = {
            "idx_question_options_question_id_sort_order",
            "idx_question_assets_question_id",
            "idx_question_tags_question_id",
            "idx_question_topics_question_id",
            "idx_exam_tags_exam_id",
            "idx_attempt_questions_attempt_order",
            "idx_attempt_questions_attempt_page_order",
            "idx_answers_question_id",
            "idx_sessions_user_id_expires_at",
            "idx_live_exams_status",
        }

        _, rows = database.execute(
            f"""
            SELECT name
            FROM sqlite_master
            WHERE type = 'index'
            AND name IN ({",".join("?" for _ in expected_indexes)})
            """,
            tuple(sorted(expected_indexes)),
            fetchall=True,
        )

        self.assertEqual({row["name"] for row in rows}, expected_indexes)

    def _build_seeded_database(self):
        self._set_env("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", "runtime-admin-password")
        return Database()

    def _create_exam_with_questions(self, database):
        exams = ExamsTable(database)
        questions = QuestionsTable(database)
        _, admin_row = database.execute(
            "SELECT id FROM users WHERE login_name = ?",
            ("admin",),
            fetchone=True,
        )
        exam_id = exams.create(
            {
                "code": "AI-204",
                "title": "Azure Developer",
                "provider": "Microsoft",
                "description": "Repository integration test exam",
                "difficulty": "advanced",
                "status": "published",
                "tags": ["azure"],
            },
            admin_row["id"],
            allow_global=True,
        )
        first_question_id = questions.create(
            exam_id,
            {
                "type": "single_select",
                "title": "Identity flow",
                "statement": "Which token flow should a confidential client use?",
                "explanation": "Confidential clients authenticate server-side.",
                "difficulty": "intermediate",
                "status": "active",
                "position": 1,
                "tags": ["governance"],
                "topics": ["identity"],
                "options": [
                    {"key": "A", "text": "Authorization code", "is_correct": True},
                    {"key": "B", "text": "Implicit", "is_correct": False},
                ],
                "assets": [
                    {
                        "asset_type": "image",
                        "file_path": "questions/ai-204/identity.png",
                        "meta": {"alt": "Identity diagram"},
                    }
                ],
            },
        )
        second_question_id = questions.create(
            exam_id,
            {
                "type": "multiple_choice",
                "title": "Blob lifecycle",
                "statement": "Which settings affect blob archival behavior?",
                "explanation": "Lifecycle policies and tiers govern archival behavior.",
                "difficulty": "advanced",
                "status": "active",
                "position": 2,
                "tags": ["storage"],
                "topics": ["storage"],
                "options": [
                    {"key": "A", "text": "Lifecycle policies", "is_correct": True},
                    {"key": "B", "text": "Archive tier", "is_correct": True},
                    {"key": "C", "text": "DNS zone", "is_correct": False},
                ],
            },
        )
        return exam_id, first_question_id, second_question_id

    def _set_env(self, key, value):
        marker = f"_orig_{key}"
        if not hasattr(self, marker):
            setattr(self, marker, os.environ.get(key))
        os.environ[key] = value

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
