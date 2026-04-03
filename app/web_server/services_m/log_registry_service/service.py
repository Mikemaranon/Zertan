import difflib
import json
from datetime import UTC, datetime


class LogRegistryService:
    def __init__(self, db_manager, exam_policy=None):
        self.db = db_manager
        self.exam_policy = exam_policy

    def build_overview_payload(self, actor_user):
        is_admin = self._user_is_administrator(actor_user)
        exams = self.db.exams.list_all(user_id=None if is_admin else actor_user["id"], is_administrator=is_admin)
        summaries = self.db.log_registry.summarize_by_exam_ids([exam["id"] for exam in exams])
        items = []
        for exam in exams:
            summary = summaries.get(exam["id"], {})
            items.append(
                {
                    **exam,
                    "log_count": summary.get("log_count", 0),
                    "latest_log_at": summary.get("latest_log_at"),
                }
            )
        return {
            "scope_options": self._list_exam_scope_options_for_user(actor_user),
            "permissions": {
                "can_export_exam": True,
                "can_export_group": True,
                "can_export_domain": is_admin,
                "can_delete_logs": is_admin,
            },
            "exams": items,
        }

    def build_exam_detail_payload(self, actor_user, exam_id):
        exam = self._get_accessible_exam(actor_user, exam_id)
        return {
            "exam": exam,
            "logs": self.db.log_registry.list_entries(exam_id=exam_id),
            "permissions": {
                "can_export_exam": True,
                "can_delete_logs": self._user_is_administrator(actor_user),
            },
        }

    def build_export_bundle(self, actor_user, *, scope, exam_id=None, group_id=None, allow_domain=True):
        resolved_scope, exam, group = self._resolve_scope(
            actor_user,
            scope=scope,
            exam_id=exam_id,
            group_id=group_id,
            allow_domain=allow_domain,
        )
        return {
            "payload": self._build_export_payload(resolved_scope, exam=exam, group=group),
            "download_name": self._build_export_filename(resolved_scope, exam=exam, group=group),
        }

    def delete_entries_for_scope(self, actor_user, *, scope, exam_id=None, group_id=None, allow_domain=True):
        if not self._user_is_administrator(actor_user):
            raise PermissionError("Forbidden")
        resolved_scope, exam, group = self._resolve_scope(
            actor_user,
            scope=scope,
            exam_id=exam_id,
            group_id=group_id,
            allow_domain=allow_domain,
        )
        if resolved_scope == "exam":
            deleted_count = self.db.log_registry.delete_entries(exam_id=exam["id"])
        elif resolved_scope == "group":
            deleted_count = self.db.log_registry.delete_entries(group_id=group["id"])
        else:
            deleted_count = self.db.log_registry.delete_entries()
        return {"status": "deleted", "deleted_count": deleted_count}

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

    def _build_export_payload(self, scope, *, exam=None, group=None):
        if scope == "exam":
            entries = self.db.log_registry.list_entries(exam_id=exam["id"])
            scope_meta = {
                "type": "exam",
                "exam": {
                    "id": exam["id"],
                    "code": exam["code"],
                    "title": exam["title"],
                },
            }
        elif scope == "group":
            entries = self.db.log_registry.list_entries(group_id=group["id"])
            scope_meta = {
                "type": "group",
                "group": group,
            }
        else:
            entries = self.db.log_registry.list_entries()
            scope_meta = {"type": "domain"}

        return {
            "exported_at": datetime.now(UTC).isoformat(),
            "scope": scope_meta,
            "logs": entries,
        }

    def _build_export_filename(self, scope, *, exam=None, group=None):
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        if scope == "exam":
            return f"log-registry-exam-{exam['code'].lower()}-{stamp}.json"
        if scope == "group":
            return f"log-registry-group-{group['code'].lower()}-{stamp}.json"
        return f"log-registry-domain-{stamp}.json"

    def _resolve_scope(self, actor_user, *, scope, exam_id=None, group_id=None, allow_domain=True):
        normalized_scope = str(scope or "").strip().lower()
        if normalized_scope not in {"exam", "group", "domain"}:
            raise ValueError("Scope must be exam, group, or domain.")
        if normalized_scope == "domain":
            if not allow_domain or not self._user_is_administrator(actor_user):
                raise PermissionError("Forbidden")
            return "domain", None, None
        if normalized_scope == "exam":
            return (
                "exam",
                self._get_accessible_exam(
                    actor_user,
                    self._coerce_int(exam_id, "A valid exam_id is required."),
                ),
                None,
            )

        resolved_group_id = self._coerce_int(group_id, "A valid group_id is required.")
        groups = {group["id"]: group for group in self._list_exam_scope_options_for_user(actor_user)}
        group = groups.get(resolved_group_id)
        if not group:
            raise LookupError("Group not found in your allowed scope.")
        return "group", None, group

    def _coerce_int(self, value, error_message):
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(error_message) from exc

    def _get_accessible_exam(self, actor_user, exam_id):
        self._require_exam_policy()
        exam, failure = self.exam_policy.get_accessible_exam(actor_user, exam_id)
        if failure == "not_found":
            raise LookupError("Exam not found.")
        if failure == "forbidden":
            raise PermissionError("Forbidden")
        return exam

    def _list_exam_scope_options_for_user(self, actor_user):
        self._require_exam_policy()
        return self.exam_policy.list_exam_scope_options_for_user(actor_user)

    def _user_is_administrator(self, actor_user):
        self._require_exam_policy()
        return self.exam_policy.user_is_administrator(actor_user)

    def _require_exam_policy(self):
        if not self.exam_policy:
            raise RuntimeError("LogRegistryService requires exam policy support for scoped operations.")
