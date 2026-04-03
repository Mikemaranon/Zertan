import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.data_m import DBManager
from app.web_server.services_m.exam_definition_service import (
    normalize_exam_group_ids,
    normalize_exam_payload,
    validate_exam_scope_group_ids,
)


class ExamDefinitionServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-exam-definition-tests-")
        self.addCleanup(self.temp_dir.cleanup)
        self._set_env("ZERTAN_DATA_DIR", self.temp_dir.name)
        self._set_env("ZERTAN_DB_PATH", str(Path(self.temp_dir.name) / "database" / "test.db"))
        self._set_env("ZERTAN_MEDIA_ROOT", str(Path(self.temp_dir.name) / "assets"))
        self._set_env("ZERTAN_SEED_DEMO_CONTENT", "0")
        self._set_env("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", "exam-definition-admin-password")
        self.addCleanup(self._restore_env)

        self.database = DBManager()
        self.groups = self.database.groups
        self.group_a = self.groups.create("Definition Group A")
        self.group_b = self.groups.create("Definition Group B")

    def test_normalize_exam_group_ids_filters_invalid_values_and_duplicates(self):
        self.assertEqual(
            normalize_exam_group_ids(["1", "x", 2, 2, 0, -1, None, "3"]),
            [1, 2, 3],
        )

    def test_normalize_exam_payload_trims_exam_fields_and_validates_url(self):
        normalized = normalize_exam_payload(
            {
                "code": " AI-102 ",
                "title": " Azure AI ",
                "provider": " Microsoft ",
                "description": "  Sample exam  ",
                "official_url": " https://learn.microsoft.com/certifications/ai-102 ",
                "difficulty": " advanced ",
                "status": " published ",
                "tags": [" azure ", "", "ai"],
                "group_ids": ["1", "1", "2"],
            }
        )

        self.assertEqual(normalized["code"], "AI-102")
        self.assertEqual(normalized["title"], "Azure AI")
        self.assertEqual(normalized["provider"], "Microsoft")
        self.assertEqual(normalized["description"], "Sample exam")
        self.assertEqual(
            normalized["official_url"],
            "https://learn.microsoft.com/certifications/ai-102",
        )
        self.assertEqual(normalized["difficulty"], "advanced")
        self.assertEqual(normalized["status"], "published")
        self.assertEqual(normalized["tags"], ["azure", "ai"])
        self.assertEqual(normalized["group_ids"], [1, 2])

    def test_validate_exam_scope_group_ids_enforces_existing_groups_and_scope(self):
        validated = validate_exam_scope_group_ids(
            self.database,
            [str(self.group_a["id"]), str(self.group_b["id"])],
            allowed_group_ids=[self.group_a["id"], self.group_b["id"]],
            allow_global=False,
        )

        self.assertEqual(validated, [self.group_a["id"], self.group_b["id"]])

        with self.assertRaisesRegex(ValueError, "outside your allowed scope"):
            validate_exam_scope_group_ids(
                self.database,
                [self.group_b["id"]],
                allowed_group_ids=[self.group_a["id"]],
                allow_global=False,
            )

        with self.assertRaisesRegex(ValueError, "do not exist"):
            validate_exam_scope_group_ids(
                self.database,
                [9999],
                allowed_group_ids=[self.group_a["id"], self.group_b["id"]],
                allow_global=False,
            )

        with self.assertRaisesRegex(ValueError, "Select at least one group"):
            validate_exam_scope_group_ids(
                self.database,
                [],
                allowed_group_ids=[self.group_a["id"]],
                allow_global=False,
            )

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
