import difflib
import json


class LogRegistryService:
    def __init__(self, db_manager):
        self.db = db_manager

    def record_exam_change(self, *, actor_user, action, before_exam=None, after_exam=None, details=""):
        exam = after_exam or before_exam or {}
        before_snapshot = self._build_exam_snapshot(before_exam)
        after_snapshot = self._build_exam_snapshot(after_exam)
        self.db.log_registry.create(
            action=action,
            entity_type="exam",
            actor_user_id=actor_user.get("id"),
            actor_login_name=actor_user.get("login_name", ""),
            actor_display_name=actor_user.get("display_name", ""),
            actor_role=actor_user.get("role", ""),
            exam_id=exam.get("id"),
            exam_code=exam.get("code", ""),
            exam_title=exam.get("title", ""),
            question_label="Exam metadata",
            details=details or self._default_detail(action, "exam"),
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            before_content_text=self._render_snapshot(before_snapshot),
            after_content_text=self._render_snapshot(after_snapshot),
            diff_text=self._build_diff(before_snapshot, after_snapshot),
            scope_groups=exam.get("scope_groups", []),
        )

    def record_question_change(
        self,
        *,
        actor_user,
        action,
        exam,
        before_question=None,
        after_question=None,
        details="",
    ):
        question = after_question or before_question or {}
        before_snapshot = self._build_question_snapshot(before_question)
        after_snapshot = self._build_question_snapshot(after_question)
        self.db.log_registry.create(
            action=action,
            entity_type="question",
            actor_user_id=actor_user.get("id"),
            actor_login_name=actor_user.get("login_name", ""),
            actor_display_name=actor_user.get("display_name", ""),
            actor_role=actor_user.get("role", ""),
            exam_id=exam.get("id"),
            exam_code=exam.get("code", ""),
            exam_title=exam.get("title", ""),
            question_id=question.get("id"),
            question_label=self._build_question_label(question),
            question_type=question.get("type", ""),
            question_position=question.get("position"),
            details=details or self._default_detail(action, "question"),
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            before_content_text=self._render_snapshot(before_snapshot),
            after_content_text=self._render_snapshot(after_snapshot),
            diff_text=self._build_diff(before_snapshot, after_snapshot),
            scope_groups=exam.get("scope_groups", []),
        )

    def _build_exam_snapshot(self, exam):
        if not exam:
            return None
        return {
            "id": exam.get("id"),
            "code": exam.get("code", ""),
            "title": exam.get("title", ""),
            "provider": exam.get("provider", ""),
            "description": exam.get("description", ""),
            "official_url": exam.get("official_url", ""),
            "difficulty": exam.get("difficulty", ""),
            "status": exam.get("status", ""),
            "tags": sorted(exam.get("tags", [])),
            "scope_groups": [
                {
                    "id": group.get("id"),
                    "code": group.get("code", ""),
                    "name": group.get("name", ""),
                }
                for group in exam.get("scope_groups", [])
            ],
        }

    def _build_question_snapshot(self, question):
        if not question:
            return None
        return {
            "id": question.get("id"),
            "exam_id": question.get("exam_id"),
            "position": question.get("position"),
            "type": question.get("type", ""),
            "title": question.get("title", ""),
            "statement": question.get("statement", ""),
            "explanation": question.get("explanation", ""),
            "difficulty": question.get("difficulty", ""),
            "status": question.get("status", ""),
            "tags": sorted(question.get("tags", [])),
            "topics": sorted(question.get("topics", [])),
            "config": question.get("config", {}),
            "options": [
                {
                    "key": option.get("key", ""),
                    "text": option.get("text", ""),
                    "is_correct": bool(option.get("is_correct")),
                }
                for option in question.get("options", [])
            ],
            "assets": [
                {
                    "asset_type": asset.get("asset_type", ""),
                    "file_path": asset.get("file_path", ""),
                    "meta": asset.get("meta", {}),
                }
                for asset in question.get("assets", [])
            ],
            "source_json_path": question.get("source_json_path"),
        }

    def _build_question_label(self, question):
        if not question:
            return "Question"
        position = question.get("position")
        title = str(question.get("title") or "").strip()
        prefix = f"Question {position}" if position else "Question"
        return f"{prefix} · {title}" if title else prefix

    def _render_snapshot(self, snapshot):
        if snapshot is None:
            return ""
        return json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=True)

    def _build_diff(self, before_snapshot, after_snapshot):
        before_lines = self._render_snapshot(before_snapshot).splitlines()
        after_lines = self._render_snapshot(after_snapshot).splitlines()
        return "\n".join(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile="before",
                tofile="after",
                lineterm="",
            )
        )

    def _default_detail(self, action, entity_type):
        return f"{entity_type.title()} {action}"
