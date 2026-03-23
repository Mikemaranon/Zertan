import json
from pathlib import Path
from uuid import uuid4

from werkzeug.utils import secure_filename

from support_m import build_media_path


class QuestionPayloadParser:
    ALLOWED_HOTSPOT_IMAGE_EXTENSIONS = {".png", ".jpg", ".svg"}
    ALLOWED_HOTSPOT_IMAGE_MIMETYPES = {
        ".png": {"image/png"},
        ".jpg": {"image/jpeg"},
        ".svg": {"image/svg+xml"},
    }

    def __init__(self, media_root, services):
        self.media_root = Path(media_root).resolve()
        self.services = services

    def parse(self, request, exam_id, current_question=None):
        payload = self._load_payload(request)
        if "type" not in payload and current_question and current_question.get("type"):
            payload["type"] = current_question["type"]
        question_type = (payload.get("type") or (current_question.get("type") if current_question else "")).strip()
        existing_assets = payload.get("assets") or (current_question.get("assets", []) if current_question else [])
        uploaded_asset = request.files.get("asset_file")
        if uploaded_asset and uploaded_asset.filename:
            existing_assets = [
                self._build_uploaded_asset(
                    request,
                    exam_id,
                    question_type,
                    payload,
                    uploaded_asset,
                )
            ]
        payload["assets"] = existing_assets
        return self.services.question_logic.normalize_question_payload(payload)

    def validate_hotspot_asset_file(self, file_storage):
        safe_name = secure_filename(file_storage.filename or "")
        extension = Path(safe_name).suffix.lower()
        if extension not in self.ALLOWED_HOTSPOT_IMAGE_EXTENSIONS:
            raise ValueError("Hot spot images must use .png, .jpg, or .svg files.")

        mimetype = (file_storage.mimetype or "").lower()
        allowed_mimetypes = self.ALLOWED_HOTSPOT_IMAGE_MIMETYPES.get(extension, set())
        if mimetype and mimetype not in allowed_mimetypes:
            raise ValueError("Hot spot images must be valid PNG, JPG, or SVG uploads.")

    def save_asset_file(self, exam_id, file_storage):
        safe_name = secure_filename(file_storage.filename)
        extension = Path(safe_name).suffix.lower()
        target_dir = self.media_root / "questions" / str(exam_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_name = f"{uuid4().hex}{extension}"
        target_path = target_dir / target_name
        file_storage.save(target_path)
        return build_media_path("questions", exam_id, target_name)

    def _build_uploaded_asset(self, request, exam_id, question_type, payload, uploaded_asset):
        if question_type == "hot_spot":
            self.validate_hotspot_asset_file(uploaded_asset)
        relative_path = self.save_asset_file(exam_id, uploaded_asset)
        return {
            "asset_type": request.form.get("asset_type") or payload.get("asset_type", "image"),
            "file_path": relative_path,
            "meta": {
                "alt": request.form.get("asset_alt") or payload.get("asset_alt") or uploaded_asset.filename,
            },
        }

    def _load_payload(self, request):
        if request.content_type and "multipart/form-data" in request.content_type:
            return json.loads(request.form.get("payload", "{}"))
        return request.get_json() or {}
