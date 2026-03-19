# services_m/package_service.py

import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from posixpath import normpath
from uuid import uuid4

from storage_paths import build_media_path, resolve_stored_path

from .question_logic import normalize_question_payload


class PackageService:
    MAX_PACKAGE_SIZE = 5 * 1024 * 1024
    ALLOWED_ARCHIVE_EXTENSIONS = {".json", ".png", ".jpg", ".svg"}
    ALLOWED_ASSET_EXTENSIONS = {".png", ".jpg", ".svg"}
    IGNORED_ARCHIVE_NAMES = {"__MACOSX", ".DS_Store", "Thumbs.db"}

    def __init__(self, db_manager, project_root, media_root=None):
        self.db = db_manager
        self.project_root = Path(project_root)
        self.upload_root = Path(media_root) if media_root else self.project_root / "web_server" / "data_m" / "assets"

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
        }
        (package_root / "exam.json").write_text(json.dumps(exam_document, indent=2), encoding="utf-8")

        zip_path = temp_dir / f"{exam['code'].lower()}-package.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in package_root.rglob("*"):
                archive.write(path, path.relative_to(temp_dir))
        return zip_path, temp_dir

    def import_exam(self, uploaded_file, created_by):
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
            existing_exams = self.db.exams.list_all()
            if any(existing["code"].lower() == exam_payload["code"].lower() for existing in existing_exams):
                raise ValueError("An exam with this code already exists.")

            exam_id = self.db.exams.create(exam_payload, created_by)

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

    def _validate_package_archive(self, archive):
        members = [info for info in archive.infolist() if info.filename and info.filename != "/"]
        if not members:
            raise ValueError("Exam package is empty.")

        root_folder = None
        roots = {}

        for info in members:
            entry_name = self._normalize_archive_name(info.filename)
            parts = entry_name.split("/")
            if any(
                part in self.IGNORED_ARCHIVE_NAMES
                or part.startswith(".")
                or part.startswith("._")
                for part in parts
            ):
                continue

            root_name = parts[0]
            root_data = roots.setdefault(
                root_name,
                {
                    "file_entries": {},
                    "directory_entries": set(),
                    "casefold_entries": set(),
                    "has_relevant_structure": False,
                },
            )

            if len(parts) == 1:
                if info.is_dir():
                    root_data["directory_entries"].add(parts[0])
                continue

            relative_path = "/".join(parts[1:])
            relative_casefold = relative_path.casefold()
            if info.is_dir():
                if relative_path in {"questions", "assets"}:
                    root_data["has_relevant_structure"] = True
                    root_data["directory_entries"].add(relative_path.rstrip("/"))
                continue

            is_exam_file = relative_path == "exam.json"
            is_question_file = (
                relative_path.startswith("questions/")
                and relative_path.count("/") == 1
                and Path(relative_path).suffix.lower() == ".json"
            )
            is_asset_file = (
                relative_path.startswith("assets/")
                and relative_path.count("/") == 1
                and Path(relative_path).suffix.lower() in self.ALLOWED_ASSET_EXTENSIONS
            )
            if not any((is_exam_file, is_question_file, is_asset_file)):
                continue

            root_data["has_relevant_structure"] = True
            if relative_casefold in root_data["casefold_entries"]:
                raise ValueError(f"Exam package contains duplicate entries for {relative_path}.")
            root_data["casefold_entries"].add(relative_casefold)
            root_data["file_entries"][relative_path] = info

        relevant_roots = {
            name: data
            for name, data in roots.items()
            if data["has_relevant_structure"] or data["file_entries"]
        }
        if not relevant_roots:
            raise ValueError("Exam package must contain a valid top-level folder with exam.json and questions/*.json.")

        selected_root = None
        selected_data = None
        for name, data in relevant_roots.items():
            file_entries = data["file_entries"]
            question_files = {
                path: info
                for path, info in file_entries.items()
                if path.startswith("questions/") and path.count("/") == 1
            }
            if file_entries.get("exam.json") and question_files:
                selected_root = name
                selected_data = data
                break

        if selected_data is None:
            selected_root, selected_data = max(
                relevant_roots.items(),
                key=lambda item: (
                    1 if item[1]["file_entries"].get("exam.json") else 0,
                    sum(
                        1
                        for path in item[1]["file_entries"]
                        if path.startswith("questions/") and path.count("/") == 1
                    ),
                    len(item[1]["file_entries"]),
                ),
            )

        root_folder = selected_root
        file_entries = selected_data["file_entries"]
        directory_entries = selected_data["directory_entries"]

        exam_info = file_entries.get("exam.json")
        if not exam_info:
            raise ValueError("Exam package must include an exam.json file in the package root.")

        questions_dir_present = "questions" in directory_entries or any(path.startswith("questions/") for path in file_entries)
        if not questions_dir_present:
            raise ValueError("Exam package must include a questions/ directory in the package root.")

        question_files = {
            path: info
            for path, info in file_entries.items()
            if path.startswith("questions/") and path.count("/") == 1
        }
        if not question_files:
            raise ValueError("Exam package must include at least one questions/*.json file.")

        asset_files = {
            path: info
            for path, info in file_entries.items()
            if path.startswith("assets/") and path.count("/") == 1
        }

        exam_payload = self._normalize_exam_payload(self._load_json_document(archive, exam_info, "exam.json"))

        question_documents = []
        for path, info in sorted(question_files.items()):
            raw_payload = self._load_json_document(archive, info, path)
            normalized_payload = self._normalize_import_question(raw_payload, path)
            self._validate_question_asset_references(raw_payload, path, asset_files)
            question_documents.append(
                {
                    "archive_path": path,
                    "file_name": Path(path).name,
                    "raw_payload": raw_payload,
                    "normalized_payload": normalized_payload,
                }
            )

        asset_documents = {
            path: self._load_binary_document(archive, info, path)
            for path, info in sorted(asset_files.items())
        }

        return {
            "root_folder": root_folder,
            "exam_payload": exam_payload,
            "question_documents": question_documents,
            "asset_files": asset_documents,
        }

    def _normalize_archive_name(self, filename):
        normalized = filename.replace("\\", "/").strip()
        if not normalized:
            raise ValueError("Exam package contains an empty entry name.")
        if normalized.startswith("/") or normalized.startswith("../") or "/../" in f"/{normalized}":
            raise ValueError("Exam package contains an invalid path.")
        normalized_path = normpath(normalized)
        if normalized_path in {".", ""}:
            raise ValueError("Exam package contains an invalid path.")
        if normalized_path.startswith("../") or normalized_path == "..":
            raise ValueError("Exam package contains an invalid path.")
        return normalized_path.rstrip("/")

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
        try:
            raw_bytes = archive.read(info)
        except KeyError as exc:
            raise ValueError(f"Unable to read {display_name} from the package.") from exc
        try:
            payload = json.loads(raw_bytes.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise ValueError(f"{display_name} must be UTF-8 encoded JSON.") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"{display_name} is not valid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{display_name} must contain a JSON object.")
        return payload

    def _load_binary_document(self, archive, info, display_name):
        try:
            return archive.read(info)
        except KeyError as exc:
            raise ValueError(f"Unable to read {display_name} from the package.") from exc

    def _normalize_exam_payload(self, payload):
        try:
            normalized = self.db.exams._normalize_payload(payload)
        except KeyError as exc:
            field = exc.args[0]
            raise ValueError(f"exam.json is missing the required field '{field}'.") from exc
        except ValueError as exc:
            raise ValueError(f"exam.json is invalid: {exc}") from exc

        for field in ("code", "title", "provider"):
            if not normalized[field]:
                raise ValueError(f"exam.json requires a non-empty '{field}' field.")
        return normalized

    def _normalize_import_question(self, payload, archive_path):
        try:
            return normalize_question_payload(payload)
        except KeyError as exc:
            field = exc.args[0]
            raise ValueError(f"{archive_path} is missing the required field '{field}'.") from exc
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{archive_path} is invalid: {exc}") from exc

    def _validate_question_asset_references(self, question_payload, archive_path, asset_files):
        for asset in question_payload.get("assets", []):
            asset_path = str(asset.get("file_path") or "").strip()
            if not asset_path:
                raise ValueError(f"{archive_path} contains an asset without a file_path.")
            if asset_path.startswith("/") or ".." in Path(asset_path).parts:
                raise ValueError(f"{archive_path} contains an invalid asset path: {asset_path}")
            if asset_path not in asset_files:
                raise ValueError(f"{archive_path} references a missing asset: {asset_path}")
            if Path(asset_path).suffix.lower() not in self.ALLOWED_ASSET_EXTENSIONS:
                raise ValueError(f"{archive_path} references an unsupported asset type: {asset_path}")

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
