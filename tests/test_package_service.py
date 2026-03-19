import io
import json
import sys
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.services_m.package_service import PackageService


class _FakeExamsTable:
    def _normalize_payload(self, payload):
        return {
            "code": str(payload["code"]).strip(),
            "title": str(payload["title"]).strip(),
            "provider": str(payload["provider"]).strip(),
            "description": str(payload.get("description", "") or "").strip(),
            "official_url": str(payload.get("official_url", "") or "").strip(),
            "difficulty": str(payload.get("difficulty", "intermediate") or "intermediate").strip(),
            "status": str(payload.get("status", "draft") or "draft").strip(),
            "tags": [str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip()],
        }


class _FakeDbManager:
    def __init__(self):
        self.exams = _FakeExamsTable()


class PackageServiceValidationTests(unittest.TestCase):
    def setUp(self):
        self.service = PackageService(_FakeDbManager(), ROOT / "app")
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


if __name__ == "__main__":
    unittest.main()
