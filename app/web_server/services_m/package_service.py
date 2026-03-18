# services_m/package_service.py

import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from .question_logic import normalize_question_payload


class PackageService:
    def __init__(self, db_manager, project_root):
        self.db = db_manager
        self.project_root = Path(project_root)
        self.upload_root = self.project_root / "web_server" / "data_m" / "assets"

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
        for index, question in enumerate(questions, start=1):
            serialized = dict(question)
            for asset in serialized.get("assets", []):
                source_path = self.project_root / asset["file_path"]
                if source_path.exists():
                    relative_name = Path(asset["file_path"]).name
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
                archive.write(path, path.relative_to(package_root))
        return zip_path, temp_dir

    def import_exam(self, uploaded_file, created_by):
        temp_dir = Path(tempfile.mkdtemp(prefix="zertan-import-"))
        try:
            archive_path = temp_dir / uploaded_file.filename
            uploaded_file.save(archive_path)

            with zipfile.ZipFile(archive_path, "r") as archive:
                archive.extractall(temp_dir / "extracted")

            extracted_root = temp_dir / "extracted"
            exam_json = extracted_root / "exam.json"
            if not exam_json.exists():
                raise ValueError("Imported package must include exam.json")

            exam_payload = json.loads(exam_json.read_text(encoding="utf-8"))
            existing_exams = self.db.exams.list_all()
            if any(existing["code"].lower() == exam_payload["code"].lower() for existing in existing_exams):
                raise ValueError("An exam with this code already exists.")

            exam_id = self.db.exams.create(exam_payload, created_by)

            questions_dir = extracted_root / "questions"
            for question_file in sorted(questions_dir.glob("*.json")):
                raw_payload = json.loads(question_file.read_text(encoding="utf-8"))
                normalized = normalize_question_payload(raw_payload)
                assets = []
                for asset in raw_payload.get("assets", []):
                    source_relative = asset["file_path"]
                    source_path = extracted_root / source_relative
                    if source_path.exists():
                        target_dir = self.upload_root / "imports" / exam_payload["code"].lower()
                        target_dir.mkdir(parents=True, exist_ok=True)
                        target_path = target_dir / source_path.name
                        shutil.copy2(source_path, target_path)
                        asset["file_path"] = str(target_path.relative_to(self.project_root))
                    assets.append(asset)
                normalized["assets"] = assets
                normalized["source_json_path"] = f"questions/{question_file.name}"
                self.db.questions.create(exam_id, normalized)

            return exam_id
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
