from flask import request

from api_m.domains.base_api import BaseAPI


class SystemAPI(BaseAPI):
    def register(self):
        self.app.add_url_rule(
            "/api/system/connection-info",
            endpoint="api_system_connection_info",
            view_func=self.get_connection_info,
            methods=["GET"],
        )
        self.app.add_url_rule(
            "/api/system/connection-info/aliases",
            endpoint="api_system_connection_aliases_create",
            view_func=self.create_alias,
            methods=["POST"],
        )
        self.app.add_url_rule(
            "/api/system/connection-info/aliases/<int:alias_id>",
            endpoint="api_system_connection_aliases_delete",
            view_func=self.delete_alias,
            methods=["DELETE"],
        )

    def get_connection_info(self):
        user, error = self.auth_user(request)
        if error:
            return error

        payload = self.services.connection_info.get_connection_info(refresh_aliases=True)
        payload["can_manage_aliases"] = self.user_is_administrator(user)
        return self.ok(payload)

    def create_alias(self):
        _, error = self.auth_user(request, min_role="administrator")
        if error:
            return error

        payload = request.get_json() or {}
        try:
            alias = self.services.connection_info.create_alias(
                host=payload.get("host"),
                label=payload.get("label", ""),
                port=payload.get("port"),
            )
        except ValueError as exc:
            return self.error(str(exc), 400)
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                return self.error("That host already exists in the shared alias list.", 400)
            raise
        return self.ok({"alias": self.services.connection_info._serialize_alias(alias)}, 201)

    def delete_alias(self, alias_id):
        _, error = self.auth_user(request, min_role="administrator")
        if error:
            return error

        existing = self.db.server_aliases.get(alias_id)
        if not existing:
            return self.error("Alias not found.", 404)

        self.services.connection_info.delete_alias(alias_id)
        return self.ok({"status": "deleted"})
