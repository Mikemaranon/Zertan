import json
from datetime import datetime, UTC
from io import BytesIO

from flask import request, send_file

from api_m.domains.base_api import BaseAPI


class LogRegistryAPI(BaseAPI):
    def register(self):
        self.app.add_url_rule("/api/log-registry", endpoint="api_log_registry_overview", view_func=self.get_overview, methods=["GET"])
        self.app.add_url_rule(
            "/api/log-registry",
            endpoint="api_log_registry_delete",
            view_func=self.delete_entries,
            methods=["DELETE"],
        )
        self.app.add_url_rule(
            "/api/log-registry/exams/<int:exam_id>",
            endpoint="api_log_registry_exam_detail",
            view_func=self.get_exam_detail,
            methods=["GET"],
        )
        self.app.add_url_rule(
            "/api/log-registry/export",
            endpoint="api_log_registry_export",
            view_func=self.export_entries,
            methods=["GET"],
        )

    def get_overview(self):
        user, error = self.auth_user(request, min_role="examiner")
        if error:
            return error
        is_admin = self.user_is_administrator(user)
        exams = self.db.exams.list_all(user_id=user["id"], is_administrator=is_admin)
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
        return self.ok(
            {
                "scope_options": self.list_exam_scope_options_for_user(user),
                "permissions": {
                    "can_export_exam": True,
                    "can_export_group": True,
                    "can_export_domain": is_admin,
                    "can_delete_logs": is_admin,
                },
                "exams": items,
            }
        )

    def get_exam_detail(self, exam_id):
        user, error = self.auth_user(request, min_role="examiner")
        if error:
            return error
        exam, exam_error = self.get_accessible_exam(user, exam_id)
        if exam_error:
            return exam_error
        return self.ok(
            {
                "exam": exam,
                "logs": self.db.log_registry.list_entries(exam_id=exam_id),
                "permissions": {
                    "can_export_exam": True,
                    "can_delete_logs": self.user_is_administrator(user),
                },
            }
        )

    def export_entries(self):
        user, error = self.auth_user(request, min_role="examiner")
        if error:
            return error
        scope, exam, group, scope_error = self._resolve_scope(request, user, allow_domain=True)
        if scope_error:
            return scope_error
        payload = self._build_export_payload(scope, exam=exam, group=group)
        raw = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
        return send_file(
            BytesIO(raw),
            mimetype="application/json",
            as_attachment=True,
            download_name=self._build_export_filename(scope, exam=exam, group=group),
        )

    def delete_entries(self):
        user, error = self.auth_user(request, min_role="administrator")
        if error:
            return error
        scope, exam, group, scope_error = self._resolve_scope(request, user, allow_domain=True)
        if scope_error:
            return scope_error
        if scope == "exam":
            deleted_count = self.db.log_registry.delete_entries(exam_id=exam["id"])
        elif scope == "group":
            deleted_count = self.db.log_registry.delete_entries(group_id=group["id"])
        else:
            deleted_count = self.db.log_registry.delete_entries()
        return self.ok({"status": "deleted", "deleted_count": deleted_count})

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

    def _resolve_scope(self, request_obj, user, *, allow_domain):
        scope = (request_obj.args.get("scope") or "").strip().lower()
        if scope not in {"exam", "group", "domain"}:
            return None, None, None, self.error("Scope must be exam, group, or domain.", 400)
        if scope == "domain":
            if not allow_domain or not self.user_is_administrator(user):
                return None, None, None, self.error("Forbidden", 403)
            return "domain", None, None, None
        if scope == "exam":
            try:
                exam_id = int(request_obj.args.get("exam_id"))
            except (TypeError, ValueError):
                return None, None, None, self.error("A valid exam_id is required.", 400)
            exam, exam_error = self.get_accessible_exam(user, exam_id)
            if exam_error:
                return None, None, None, exam_error
            return "exam", exam, None, None

        try:
            group_id = int(request_obj.args.get("group_id"))
        except (TypeError, ValueError):
            return None, None, None, self.error("A valid group_id is required.", 400)
        groups = {group["id"]: group for group in self.list_exam_scope_options_for_user(user)}
        group = groups.get(group_id)
        if not group:
            return None, None, None, self.error("Group not found in your allowed scope.", 404)
        return "group", None, group, None
