import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4

from support_m import build_media_path, resolve_stored_path

from .archive_validation import PackageArchiveValidator
from .import_scope import PackageImportScopeResolver


class PackageService:
    MAX_PACKAGE_SIZE = 5 * 1024 * 1024

    def __init__(self, db_manager, project_root, media_root=None):
        self.db = db_manager
        self.project_root = Path(project_root)
        self.upload_root = Path(media_root) if media_root else self.project_root / "web_server" / "data_m" / "assets"
        self.archive_validator = PackageArchiveValidator(self.db)
        self.scope_resolver = PackageImportScopeResolver(self.db)

    def export_exam(self, exam_id):
        exam = self.db.exams.get(exam_id)
        if not exam:
            raise ValueError("Exam not found.")

        temp_dir = Path(tempfile.mkdtemp(prefix="zertan-export-"))
        package_root = temp_dir / "exam-package"
        questions_dir = package_root / "questions"
        assets_dir = package_root / "assets"
        questions_dir.mkdir(parents=True, exist_ok=True)
        assets_dir.mkdir(parents=True, exist_ok=True)

        questions = self.db.questions.list_for_exam(exam_id, include_answers=True, include_archived=True)
        exported_assets = {}
        used_asset_names = set()
        for index, question in enumerate(questions, start=1):
            serialized = dict(question)
            for asset in serialized.get("assets", []):
                source_path = resolve_stored_path(
                    asset["file_path"],
                    media_root=self.upload_root,
                    app_root=self.project_root,
                )
                if source_path and source_path.exists():
                    relative_name = exported_assets.get(asset["file_path"])
                    if not relative_name:
                        relative_name = self._build_export_asset_name(Path(asset["file_path"]).name, used_asset_names)
                        exported_assets[asset["file_path"]] = relative_name
                        used_asset_names.add(relative_name.casefold())
                        target_path = assets_dir / relative_name
                        shutil.copy2(source_path, target_path)
                    asset["file_path"] = f"assets/{relative_name}"
            (questions_dir / f"q_{index:04d}.json").write_text(
                json.dumps(serialized, indent=2),
                encoding="utf-8",
            )

        exam_document = {
            "code": exam["code"],
            "title": exam["title"],
            "provider": exam["provider"],
            "description": exam["description"],
            "official_url": exam.get("official_url", ""),
            "difficulty": exam["difficulty"],
            "status": exam["status"],
            "tags": exam["tags"],
            "scope_mode": exam.get("scope_mode", "global"),
            "group_codes": [group["code"] for group in exam.get("scope_groups", [])],
        }
        (package_root / "exam.json").write_text(json.dumps(exam_document, indent=2), encoding="utf-8")

        zip_path = temp_dir / f"{exam['code'].lower()}-package.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in package_root.rglob("*"):
                archive.write(path, path.relative_to(temp_dir))
        return zip_path, temp_dir

    def import_exam(self, uploaded_file, created_by, group_ids=None, scope_mode=None, allowed_group_ids=None, allow_global=True):
        temp_dir = Path(tempfile.mkdtemp(prefix="zertan-import-"))
        exam_id = None
        target_dir = None
        try:
            archive_path = temp_dir / Path(uploaded_file.filename).name
            uploaded_file.save(archive_path)
            if archive_path.stat().st_size > self.MAX_PACKAGE_SIZE:
                raise ValueError("Exam packages must be 5 MB or smaller.")

            try:
                with zipfile.ZipFile(archive_path, "r") as archive:
                    package_data = self._validate_package_archive(archive)
            except zipfile.BadZipFile as exc:
                raise ValueError("Upload a valid .zip exam package.") from exc

            exam_payload = package_data["exam_payload"]
            resolved_group_ids = self._resolve_import_group_ids(
                exam_payload,
                explicit_group_ids=group_ids,
                explicit_scope_mode=scope_mode,
                allowed_group_ids=allowed_group_ids,
                allow_global=allow_global,
            )
            exam_payload["group_ids"] = resolved_group_ids
            existing_exams = self.db.exams.list_all()
            if any(existing["code"].lower() == exam_payload["code"].lower() for existing in existing_exams):
                raise ValueError("An exam with this code already exists.")

            exam_id = self.db.exams.create(
                exam_payload,
                created_by,
                allowed_group_ids=allowed_group_ids,
                allow_global=allow_global,
            )

            target_dir = self.upload_root / "imports" / exam_payload["code"].lower()
            shutil.rmtree(target_dir, ignore_errors=True)
            target_dir.mkdir(parents=True, exist_ok=True)
            stored_asset_paths = self._store_package_assets(package_data["asset_files"], target_dir)

            for question_document in package_data["question_documents"]:
                normalized = dict(question_document["normalized_payload"])
                normalized["assets"] = self._rewrite_question_assets(question_document["raw_payload"], stored_asset_paths)
                normalized["source_json_path"] = f"questions/{question_document['file_name']}"
                self.db.questions.create(exam_id, normalized)

            return exam_id
        except Exception:
            if exam_id is not None:
                self.db.exams.delete(exam_id)
            if target_dir is not None:
                shutil.rmtree(target_dir, ignore_errors=True)
            raise
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _resolve_import_group_ids(
        self,
        exam_payload,
        explicit_group_ids=None,
        explicit_scope_mode=None,
        allowed_group_ids=None,
        allow_global=True,
    ):
        return self.scope_resolver.resolve_group_ids(
            exam_payload,
            explicit_group_ids=explicit_group_ids,
            explicit_scope_mode=explicit_scope_mode,
            allowed_group_ids=allowed_group_ids,
            allow_global=allow_global,
        )

    def _validate_package_archive(self, archive):
        return self.archive_validator.validate(archive)

    def _normalize_archive_name(self, filename):
        return self.archive_validator.normalize_archive_name(filename)

    def _build_export_asset_name(self, original_name, used_asset_names):
        source_name = Path(original_name).name
        stem = Path(source_name).stem or "asset"
        suffix = Path(source_name).suffix.lower()
        candidate = f"{stem}{suffix}"
        counter = 1
        while candidate.casefold() in used_asset_names:
            candidate = f"{stem}_{counter}{suffix}"
            counter += 1
        return candidate

    def _load_json_document(self, archive, info, display_name):
        return self.archive_validator._load_json_document(archive, info, display_name)

    def _load_binary_document(self, archive, info, display_name):
        return self.archive_validator._load_binary_document(archive, info, display_name)

    def _normalize_exam_payload(self, payload):
        return self.archive_validator._normalize_exam_payload(payload)

    def _normalize_import_question(self, payload, archive_path):
        return self.archive_validator._normalize_import_question(payload, archive_path)

    def _validate_question_asset_references(self, question_payload, archive_path, asset_files):
        self.archive_validator.validate_question_asset_references(question_payload, archive_path, asset_files)

    def _store_package_assets(self, asset_files, target_dir):
        stored_paths = {}
        for relative_path, file_bytes in sorted(asset_files.items()):
            extension = Path(relative_path).suffix.lower()
            target_name = f"{uuid4().hex}{extension}"
            target_path = target_dir / target_name
            target_path.write_bytes(file_bytes)
            stored_paths[relative_path] = target_path
        return stored_paths

    def _rewrite_question_assets(self, question_payload, stored_asset_paths):
        assets = []
        for asset in question_payload.get("assets", []):
            normalized_asset = dict(asset)
            asset_path = str(asset.get("file_path") or "").strip()
            stored_path = stored_asset_paths.get(asset_path)
            if stored_path is not None:
                normalized_asset["file_path"] = build_media_path(stored_path.relative_to(self.upload_root))
            assets.append(normalized_asset)
        return assets
