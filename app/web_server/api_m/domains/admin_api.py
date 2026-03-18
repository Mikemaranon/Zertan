# api_m/domains/admin_api.py

from flask import request

from api_m.domains.base_api import BaseAPI


class AdminAPI(BaseAPI):
    def register(self):
        self.app.add_url_rule("/api/admin/users", endpoint="api_admin_users_list", view_func=self.list_users, methods=["GET"])
        self.app.add_url_rule("/api/admin/users", endpoint="api_admin_users_create", view_func=self.create_user, methods=["POST"])
        self.app.add_url_rule("/api/admin/users/<int:user_id>", endpoint="api_admin_users_update", view_func=self.update_user, methods=["PUT"])
        self.app.add_url_rule("/api/admin/users/<int:user_id>", endpoint="api_admin_users_delete", view_func=self.delete_user, methods=["DELETE"])

    def list_users(self):
        _, error = self.auth_user(request, min_role="administrator")
        if error:
            return error
        return self.ok({"users": self.db.users.all()})

    def create_user(self):
        _, error = self.auth_user(request, min_role="administrator")
        if error:
            return error
        payload = request.get_json() or {}
        required = ["display_name", "login_name", "password", "role"]
        if any(not str(payload.get(field, "")).strip() for field in required):
            return self.error("Name, login name, password, and role are required.", 400)
        user = self.user_manager.create_user(
            payload["display_name"],
            payload["login_name"],
            payload["password"],
            role=payload["role"],
            status=payload.get("status", "active"),
        )
        if not user:
            return self.error("Login name already exists or the payload is invalid.", 400)
        return self.ok({"user": self.user_manager.public_user(user)}, 201)

    def update_user(self, user_id):
        _, error = self.auth_user(request, min_role="administrator")
        if error:
            return error
        existing = self.db.users.get_by_id(user_id)
        if not existing:
            return self.error("User not found.", 404)
        payload = request.get_json() or {}
        updated = self.user_manager.update_user(
            user_id=user_id,
            display_name=payload.get("display_name", existing["display_name"]),
            login_name=payload.get("login_name", existing["login_name"]),
            role=payload.get("role", existing["role"]),
            status=payload.get("status", existing["status"]),
            password=payload.get("password"),
        )
        if not updated:
            return self.error("Login name already exists or the user could not be updated.", 400)
        return self.ok({"user": self.user_manager.public_user(updated)})

    def delete_user(self, user_id):
        _, error = self.auth_user(request, min_role="administrator")
        if error:
            return error
        existing = self.db.users.get_by_id(user_id)
        if not existing:
            return self.error("User not found.", 404)
        self.db.users.delete(user_id)
        return self.ok({"status": "deleted"})
