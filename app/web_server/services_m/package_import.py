# services_m/package_import.py

import json
from pathlib import Path
from posixpath import normpath

from .question_logic import normalize_question_payload


class PackageImportScopeResolver:
    def __init__(self, db_manager):
        self.db = db_manager

    def resolve_group_ids(
        self,
        exam_payload,
        explicit_group_ids=None,
        explicit_scope_mode=None,
        allowed_group_ids=None,
        allow_global=True,
    ):
        normalized_explicit_group_ids = self.db.exams._normalize_group_ids(explicit_group_ids)
        normalized_scope_mode = str(explicit_scope_mode or "").strip().lower()
        if normalized_scope_mode == "global":
            return []
        if normalized_scope_mode == "groups":
            if normalized_explicit_group_ids:
                return normalized_explicit_group_ids
            raise ValueError("Select at least one group for this imported exam.")
        if normalized_explicit_group_ids:
            return normalized_explicit_group_ids

        package_group_codes = [
            str(value).strip()
            for value in exam_payload.get("group_codes", [])
            if str(value).strip()
        ]
        if package_group_codes:
            return self._resolve_package_group_codes(package_group_codes)

        if exam_payload.get("scope_mode") == "groups" and not allow_global:
            raise ValueError("Select at least one group for this imported exam.")

        return []

    def _resolve_package_group_codes(self, package_group_codes):
        placeholders = ",".join("?" for _ in package_group_codes)
        rows = self.db.execute(
            f"""
            SELECT id, code
            FROM user_groups
            WHERE lower(code) IN ({placeholders})
            ORDER BY id
            """,
            tuple(code.lower() for code in package_group_codes),
            fetchall=True,
        )
        code_to_id = {row["code"].lower(): row["id"] for row in rows}
        missing_codes = [code for code in package_group_codes if code.lower() not in code_to_id]
        if missing_codes:
            raise ValueError("The imported package references groups that do not exist in this domain.")
        return [code_to_id[code.lower()] for code in package_group_codes]


class PackageArchiveValidator:
    ALLOWED_ASSET_EXTENSIONS = {".png", ".jpg", ".svg"}
    IGNORED_ARCHIVE_NAMES = {"__MACOSX", ".DS_Store", "Thumbs.db"}

    def __init__(self, db_manager):
        self.db = db_manager

    def validate(self, archive):
        members = [info for info in archive.infolist() if info.filename and info.filename != "/"]
        if not members:
            raise ValueError("Exam package is empty.")

        roots = self._collect_relevant_roots(members)
        if not roots:
            raise ValueError("Exam package must contain a valid top-level folder with exam.json and questions/*.json.")

        root_folder, selected_data = self._select_root_folder(roots)
        file_entries = selected_data["file_entries"]
        directory_entries = selected_data["directory_entries"]

        exam_info = file_entries.get("exam.json")
        if not exam_info:
            raise ValueError("Exam package must include an exam.json file in the package root.")

        questions_dir_present = "questions" in directory_entries or any(
            path.startswith("questions/") for path in file_entries
        )
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
        question_documents = self._build_question_documents(archive, question_files, asset_files)
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

    def normalize_archive_name(self, filename):
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

    def validate_question_asset_references(self, question_payload, archive_path, asset_files):
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

    def _collect_relevant_roots(self, members):
        roots = {}
        for info in members:
            entry_name = self.normalize_archive_name(info.filename)
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

        return {
            name: data
            for name, data in roots.items()
            if data["has_relevant_structure"] or data["file_entries"]
        }

    def _select_root_folder(self, relevant_roots):
        for name, data in relevant_roots.items():
            file_entries = data["file_entries"]
            question_files = {
                path: info
                for path, info in file_entries.items()
                if path.startswith("questions/") and path.count("/") == 1
            }
            if file_entries.get("exam.json") and question_files:
                return name, data

        return max(
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

    def _build_question_documents(self, archive, question_files, asset_files):
        question_documents = []
        for path, info in sorted(question_files.items()):
            raw_payload = self._load_json_document(archive, info, path)
            normalized_payload = self._normalize_import_question(raw_payload, path)
            self.validate_question_asset_references(raw_payload, path, asset_files)
            question_documents.append(
                {
                    "archive_path": path,
                    "file_name": Path(path).name,
                    "raw_payload": raw_payload,
                    "normalized_payload": normalized_payload,
                }
            )
        return question_documents

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
        normalized["scope_mode"] = str(payload.get("scope_mode", "global") or "global").strip().lower()
        normalized["group_codes"] = [
            str(value).strip()
            for value in payload.get("group_codes", [])
            if str(value).strip()
        ]
        return normalized

    def _normalize_import_question(self, payload, archive_path):
        try:
            return normalize_question_payload(payload)
        except KeyError as exc:
            field = exc.args[0]
            raise ValueError(f"{archive_path} is missing the required field '{field}'.") from exc
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{archive_path} is invalid: {exc}") from exc
