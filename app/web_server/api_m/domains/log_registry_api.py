import json
from io import BytesIO

from flask import request, send_file

from .base_api import BaseAPI


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
        return self.ok(self.services.log_registry.build_overview_payload(user))

    def get_exam_detail(self, exam_id):
        user, error = self.auth_user(request, min_role="examiner")
        if error:
            return error
        try:
            return self.ok(self.services.log_registry.build_exam_detail_payload(user, exam_id))
        except LookupError as exc:
            return self.error(str(exc), 404)
        except PermissionError as exc:
            return self.error(str(exc), 403)

    def export_entries(self):
        user, error = self.auth_user(request, min_role="examiner")
        if error:
            return error
        try:
            export_bundle = self.services.log_registry.build_export_bundle(
                user,
                scope=request.args.get("scope"),
                exam_id=request.args.get("exam_id"),
                group_id=request.args.get("group_id"),
                allow_domain=True,
            )
        except ValueError as exc:
            return self.error(str(exc), 400)
        except LookupError as exc:
            return self.error(str(exc), 404)
        except PermissionError as exc:
            return self.error(str(exc), 403)
        raw = json.dumps(export_bundle["payload"], indent=2, ensure_ascii=True).encode("utf-8")
        return send_file(
            BytesIO(raw),
            mimetype="application/json",
            as_attachment=True,
            download_name=export_bundle["download_name"],
        )

    def delete_entries(self):
        user, error = self.auth_user(request, min_role="administrator")
        if error:
            return error
        try:
            payload = self.services.log_registry.delete_entries_for_scope(
                user,
                scope=request.args.get("scope"),
                exam_id=request.args.get("exam_id"),
                group_id=request.args.get("group_id"),
                allow_domain=True,
            )
        except ValueError as exc:
            return self.error(str(exc), 400)
        except LookupError as exc:
            return self.error(str(exc), 404)
        except PermissionError as exc:
            return self.error(str(exc), 403)
        return self.ok(payload)
