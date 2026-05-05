import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage


ROOT = Path(__file__).resolve().parents[3]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.data_m import DBManager
from app.web_server.services_m.package_service import PackageService


class _FakeDbManager:
    def __init__(self, group_rows=None):
        self._group_rows = list(group_rows or [])
        self.groups = _FakeGroupsTable(self._group_rows)


class _FakeGroupsTable:
    def __init__(self, group_rows):
        self._group_rows = list(group_rows)

    def list_existing_ids(self, group_ids):
        requested_ids = {int(value) for value in group_ids}
        return [row["id"] for row in self._group_rows if row["id"] in requested_ids]

    def list_by_codes(self, group_codes):
        requested_codes = {str(value).lower() for value in group_codes}
        return [
            {"id": row["id"], "code": row["code"]}
            for row in self._group_rows
            if row["code"].lower() in requested_codes
        ]


class PackageServiceValidationTests(unittest.TestCase):
    def setUp(self):
        self.service = PackageService(
            _FakeDbManager(
                group_rows=[
                    {"id": 10, "code": "alpha-team"},
                    {"id": 11, "code": "beta-team"},
                ]
            ),
            ROOT / "app",
        )
        self.root_name = "ai102-package"

    def test_accepts_valid_package_even_with_extra_files(self):
        archive = self._build_archive(
            {
                f"{self.root_name}/exam.json": self._exam_payload(),
                f"{self.root_name}/questions/q_0001.json": self._question_payload(),
                f"{self.root_name}/assets/diagram.png": b"fake-image",
                "__MACOSX/._q_0001.json": b"",
                f"{self.root_name}/.DS_Store": b"",
                f"{self.root_name}/questions/.DS_Store": b"",
                f"{self.root_name}/questions/notes.txt": "ignore me",
                f"{self.root_name}/questions/nested/q_9999.json": self._question_payload(statement="Ignored nested"),
                f"{self.root_name}/assets/README.md": "ignore me too",
                f"{self.root_name}/assets/nested/diagram.png": b"ignored-image",
                f"{self.root_name}/docs/readme.txt": "not part of the package",
                "random-folder/anything.bin": b"outside root",
            }
        )

        with zipfile.ZipFile(archive, "r") as zip_archive:
            package_data = self.service._validate_package_archive(zip_archive)

        self.assertEqual(package_data["root_folder"], self.root_name)
        self.assertEqual(package_data["exam_payload"]["code"], "AI-102")
        self.assertEqual(
            [document["archive_path"] for document in package_data["question_documents"]],
            ["questions/q_0001.json"],
        )
        self.assertEqual(sorted(package_data["asset_files"].keys()), ["assets/diagram.png"])

    def test_rejects_package_without_exam_json(self):
        archive = self._build_archive(
            {
                f"{self.root_name}/questions/q_0001.json": self._question_payload(),
                f"{self.root_name}/notes.txt": "ignored extra",
            }
        )

        with zipfile.ZipFile(archive, "r") as zip_archive:
            with self.assertRaisesRegex(ValueError, "exam.json file in the package root"):
                self.service._validate_package_archive(zip_archive)

    def test_rejects_package_without_direct_question_json_files(self):
        archive = self._build_archive(
            {
                f"{self.root_name}/exam.json": self._exam_payload(),
                f"{self.root_name}/questions/": b"",
                f"{self.root_name}/questions/nested/q_0001.json": self._question_payload(),
                f"{self.root_name}/questions/notes.txt": "ignored extra",
            }
        )

        with zipfile.ZipFile(archive, "r") as zip_archive:
            with self.assertRaisesRegex(ValueError, r"questions/\*\.json"):
                self.service._validate_package_archive(zip_archive)

    def test_resolve_import_group_ids_returns_explicit_groups_for_group_scope(self):
        resolved = self.service._resolve_import_group_ids(
            self._exam_payload(),
            explicit_group_ids=["10", "11"],
            explicit_scope_mode="groups",
        )

        self.assertEqual(resolved, [10, 11])

    def test_resolve_import_group_ids_maps_package_group_codes(self):
        service = PackageService(
            _FakeDbManager(
                group_rows=[
                    {"id": 3, "code": "ai-team"},
                    {"id": 5, "code": "sec-team"},
                ]
            ),
            ROOT / "app",
        )

        resolved = service._resolve_import_group_ids(
            {
                **self._exam_payload(),
                "group_codes": ["SEC-TEAM", "ai-team"],
            },
        )

        self.assertEqual(resolved, [5, 3])

    def test_resolve_import_group_ids_rejects_missing_package_group_codes(self):
        service = PackageService(
            _FakeDbManager(group_rows=[{"id": 3, "code": "ai-team"}]),
            ROOT / "app",
        )

        with self.assertRaisesRegex(ValueError, "references groups that do not exist"):
            service._resolve_import_group_ids(
                {
                    **self._exam_payload(),
                    "group_codes": ["ai-team", "missing-team"],
                },
            )

    def test_resolve_import_group_ids_rejects_groups_outside_allowed_scope(self):
        with self.assertRaisesRegex(ValueError, "outside your allowed scope"):
            self.service._resolve_import_group_ids(
                self._exam_payload(),
                explicit_group_ids=["10", "11"],
                allowed_group_ids=[10],
            )

    def test_validate_package_archive_rejects_missing_question_assets(self):
        archive = self._build_archive(
            {
                f"{self.root_name}/exam.json": self._exam_payload(),
                f"{self.root_name}/questions/q_0001.json": {
                    **self._question_payload(),
                    "assets": [{"file_path": "assets/missing-image.png"}],
                },
            }
        )

        with zipfile.ZipFile(archive, "r") as zip_archive:
            with self.assertRaisesRegex(ValueError, "references a missing asset"):
                self.service._validate_package_archive(zip_archive)

    def test_validate_package_archive_rejects_invalid_paths(self):
        archive = self._build_archive(
            {
                f"{self.root_name}/exam.json": self._exam_payload(),
                f"{self.root_name}/questions/q_0001.json": self._question_payload(),
                f"{self.root_name}/../escape.json": {"ignored": True},
            }
        )

        with zipfile.ZipFile(archive, "r") as zip_archive:
            with self.assertRaisesRegex(ValueError, "contains an invalid path"):
                self.service._validate_package_archive(zip_archive)

    def test_validate_package_archive_rejects_malformed_json_documents(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{self.root_name}/exam.json", b"{not valid json")
            archive.writestr(
                f"{self.root_name}/questions/q_0001.json",
                json.dumps(self._question_payload()).encode("utf-8"),
            )
        buffer.seek(0)

        with zipfile.ZipFile(buffer, "r") as zip_archive:
            with self.assertRaisesRegex(ValueError, "exam.json is not valid JSON"):
                self.service._validate_package_archive(zip_archive)

    def test_validate_question_asset_references_rejects_unsupported_asset_type(self):
        with self.assertRaisesRegex(ValueError, "unsupported asset type"):
            self.service._validate_question_asset_references(
                {
                    "assets": [{"file_path": "assets/diagram.gif"}],
                },
                "questions/q_0001.json",
                {"assets/diagram.gif": b"gif-bytes"},
            )

    def _build_archive(self, entries):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path, content in entries.items():
                if path.endswith("/"):
                    archive.writestr(path, b"")
                    continue
                data = content if isinstance(content, bytes) else json.dumps(content).encode("utf-8") if isinstance(content, dict) else str(content).encode("utf-8")
                archive.writestr(path, data)
        buffer.seek(0)
        return buffer

    def _exam_payload(self):
        return {
            "code": "AI-102",
            "title": "Designing and Implementing an Azure AI Solution",
            "provider": "Microsoft",
            "description": "Sample import package",
            "difficulty": "advanced",
            "status": "published",
            "tags": ["azure", "ai"],
        }

    def _question_payload(self, statement="Which service should you use?"):
        return {
            "type": "single_select",
            "statement": statement,
            "explanation": "Use the managed service that matches the requirement.",
            "difficulty": "intermediate",
            "status": "active",
            "tags": ["azure"],
            "topics": ["services"],
            "options": [
                {"key": "A", "text": "Azure AI Search", "is_correct": True},
                {"key": "B", "text": "Azure Load Testing", "is_correct": False},
            ],
        }


class PackageServiceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-package-service-")
        self.addCleanup(self.temp_dir.cleanup)
        self._set_env("ZERTAN_DATA_DIR", self.temp_dir.name)
        self._set_env("ZERTAN_DB_PATH", str(Path(self.temp_dir.name) / "database" / "test.db"))
        self._set_env("ZERTAN_MEDIA_ROOT", str(Path(self.temp_dir.name) / "assets"))
        self._set_env("ZERTAN_SEED_DEMO_CONTENT", "0")
        self._set_env("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", "package-service-admin-password")
        self.addCleanup(self._restore_env)

        self.db = DBManager()
        self.media_root = Path(os.environ["ZERTAN_MEDIA_ROOT"])
        self.project_root = ROOT / "app"
        self.service = PackageService(self.db, self.project_root, media_root=self.media_root)
        self.admin = self.db.users.get_by_login_name("admin")

    def test_export_exam_deduplicates_reused_assets_and_renames_collisions(self):
        exam_id = self.db.exams.create(
            {
                "code": "PKG-100",
                "title": "Package Export Exam",
                "provider": "Zertan",
                "description": "Export collision coverage.",
                "difficulty": "intermediate",
                "status": "published",
                "tags": ["packages"],
            },
            self.admin["id"],
            allow_global=True,
        )

        reused_path = self._create_asset("questions/pkg/reused/diagram.png", b"reused-image")
        collision_a = self._create_asset("questions/pkg/collision-a/diagram.png", b"collision-a")
        collision_b = self._create_asset("questions/pkg/collision-b/diagram.png", b"collision-b")

        self.db.questions.create(
            exam_id,
            self._question_payload(
                "Question 1",
                assets=[{"asset_type": "image", "file_path": reused_path}],
            ),
        )
        self.db.questions.create(
            exam_id,
            self._question_payload(
                "Question 2",
                assets=[{"asset_type": "image", "file_path": collision_a}],
            ),
        )
        self.db.questions.create(
            exam_id,
            self._question_payload(
                "Question 3",
                assets=[
                    {"asset_type": "image", "file_path": reused_path},
                    {"asset_type": "image", "file_path": collision_b},
                ],
            ),
        )

        zip_path, temp_dir = self.service.export_exam(exam_id)
        self.addCleanup(lambda: zip_path.exists() and zip_path.unlink())
        self.addCleanup(lambda: temp_dir.exists() and shutil.rmtree(temp_dir, ignore_errors=True))

        with zipfile.ZipFile(zip_path, "r") as archive:
            names = set(archive.namelist())
            question_one = json.loads(archive.read("exam-package/questions/q_0001.json").decode("utf-8"))
            question_two = json.loads(archive.read("exam-package/questions/q_0002.json").decode("utf-8"))
            question_three = json.loads(archive.read("exam-package/questions/q_0003.json").decode("utf-8"))

        self.assertEqual(
            {
                "exam-package/assets/diagram.png",
                "exam-package/assets/diagram_1.png",
                "exam-package/assets/diagram_2.png",
            },
            {name for name in names if name.startswith("exam-package/assets/") and name.endswith(".png")},
        )
        self.assertEqual(question_one["assets"][0]["file_path"], "assets/diagram.png")
        self.assertEqual(question_two["assets"][0]["file_path"], "assets/diagram_1.png")
        self.assertEqual(question_three["assets"][0]["file_path"], "assets/diagram.png")
        self.assertEqual(question_three["assets"][1]["file_path"], "assets/diagram_2.png")

    def test_import_exam_rolls_back_exam_questions_and_assets_when_question_create_fails(self):
        uploaded = FileStorage(
            stream=self._build_import_archive(
                code="PKG-200",
                questions=[
                    self._import_question_payload("Imported question 1"),
                    self._import_question_payload("Imported question 2"),
                ],
                assets={
                    "assets/diagram.png": b"package-image",
                },
            ),
            filename="pkg-200.zip",
            content_type="application/zip",
        )

        original_create = self.db.questions.create
        call_count = {"total": 0}

        def failing_create(exam_id, payload):
            call_count["total"] += 1
            if call_count["total"] == 2:
                raise RuntimeError("Simulated question create failure")
            return original_create(exam_id, payload)

        with patch.object(self.db.questions, "create", side_effect=failing_create):
            with self.assertRaisesRegex(RuntimeError, "Simulated question create failure"):
                self.service.import_exam(
                    uploaded,
                    self.admin["id"],
                    allowed_group_ids=[],
                    allow_global=True,
                )

        self.assertEqual(call_count["total"], 2)
        self.assertEqual(
            [exam["code"] for exam in self.db.exams.list_all()],
            [],
        )
        self.assertFalse((self.media_root / "imports" / "pkg-200").exists())

    def _question_payload(self, statement, *, assets=None):
        return {
            "type": "single_select",
            "statement": statement,
            "explanation": f"Explanation for {statement}",
            "difficulty": "intermediate",
            "status": "active",
            "tags": ["packages"],
            "topics": ["service"],
            "assets": assets or [],
            "options": [
                {"key": "A", "text": "Correct", "is_correct": True},
                {"key": "B", "text": "Incorrect", "is_correct": False},
            ],
        }

    def _import_question_payload(self, statement):
        payload = self._question_payload(statement, assets=[{"asset_type": "image", "file_path": "assets/diagram.png"}])
        payload["title"] = statement
        return payload

    def _create_asset(self, relative_path, content):
        asset_path = self.media_root / Path(relative_path)
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        asset_path.write_bytes(content)
        return str(Path(relative_path))

    def _build_import_archive(self, *, code, questions, assets):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "exam-package/exam.json",
                json.dumps(
                    {
                        "code": code,
                        "title": f"Exam {code}",
                        "provider": "Zertan",
                        "description": "Import rollback coverage.",
                        "difficulty": "intermediate",
                        "status": "published",
                        "tags": ["packages"],
                    }
                ).encode("utf-8"),
            )
            for index, question in enumerate(questions, start=1):
                archive.writestr(
                    f"exam-package/questions/q_{index:04d}.json",
                    json.dumps(question).encode("utf-8"),
                )
            for path, content in assets.items():
                archive.writestr(f"exam-package/{path}", content)
        buffer.seek(0)
        return buffer

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
