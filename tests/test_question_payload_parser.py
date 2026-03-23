import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, request


ROOT = Path(__file__).resolve().parents[1]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.api_m.question_payload_parser import QuestionPayloadParser


class QuestionPayloadParserTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-question-payload-")
        self.addCleanup(self.temp_dir.cleanup)
        self.app = Flask(__name__)
        self.media_root = Path(self.temp_dir.name)
        self.parser = QuestionPayloadParser(
            self.media_root,
            SimpleNamespace(question_logic=SimpleNamespace(normalize_question_payload=lambda payload: payload)),
        )

    def test_json_payload_reuses_existing_assets_when_no_upload_is_sent(self):
        current_question = {
            "type": "single_select",
            "assets": [{"asset_type": "image", "file_path": "questions/9/existing.png", "meta": {"alt": "Existing"}}],
        }

        with self.app.test_request_context(
            "/api/questions/10",
            method="PUT",
            json={
                "statement": "Which option is correct?",
                "options": [
                    {"key": "A", "text": "Correct", "is_correct": True},
                    {"key": "B", "text": "Incorrect", "is_correct": False},
                ],
            },
        ):
            payload = self.parser.parse(request, 9, current_question=current_question)

        self.assertEqual(payload["assets"], current_question["assets"])

    def test_multipart_hotspot_upload_saves_asset_and_uses_form_metadata(self):
        with self.app.test_request_context(
            "/api/exams/7/questions",
            method="POST",
            data={
                "payload": json.dumps(
                    {
                        "type": "hot_spot",
                        "statement": "Identify the service.",
                        "config": {
                            "dropdowns": [
                                {
                                    "order": 1,
                                    "label": "Region",
                                    "options": ["A", "B"],
                                    "correct_option": "A",
                                }
                            ]
                        },
                    }
                ),
                "asset_type": "image",
                "asset_alt": "Architecture diagram",
                "asset_file": (io.BytesIO(b"png-bytes"), "diagram.png", "image/png"),
            },
        ):
            payload = self.parser.parse(request, 7)

        self.assertEqual(len(payload["assets"]), 1)
        asset = payload["assets"][0]
        self.assertEqual(asset["asset_type"], "image")
        self.assertEqual(asset["meta"]["alt"], "Architecture diagram")
        self.assertTrue(asset["file_path"].startswith("questions/7/"))
        stored_path = self.media_root / asset["file_path"]
        self.assertTrue(stored_path.exists())

    def test_hotspot_upload_rejects_invalid_mimetype(self):
        with self.app.test_request_context(
            "/api/exams/7/questions",
            method="POST",
            data={
                "payload": json.dumps(
                    {
                        "type": "hot_spot",
                        "statement": "Identify the service.",
                        "config": {
                            "dropdowns": [
                                {
                                    "order": 1,
                                    "label": "Region",
                                    "options": ["A", "B"],
                                    "correct_option": "A",
                                }
                            ]
                        },
                    }
                ),
                "asset_file": (io.BytesIO(b"not-an-image"), "diagram.png", "text/plain"),
            },
        ):
            with self.assertRaisesRegex(ValueError, "valid PNG, JPG, or SVG uploads"):
                self.parser.parse(request, 7)


if __name__ == "__main__":
    unittest.main()
