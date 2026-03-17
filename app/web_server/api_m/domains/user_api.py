# api_m/domains/user_api.py

from flask import request

from api_m.domains.base_api import BaseAPI


class UserAPI(BaseAPI):
    def register(self):
        self.app.add_url_rule("/api/users/me", endpoint="api_users_me", view_func=self.get_me, methods=["GET"])
        self.app.add_url_rule(
            "/api/users/recent-attempts",
            endpoint="api_users_recent_attempts",
            view_func=self.get_recent_attempts,
            methods=["GET"],
        )

    def get_me(self):
        user, error = self.auth_user(request)
        if error:
            return error
        return self.ok({"user": user})

    def get_recent_attempts(self):
        user, error = self.auth_user(request)
        if error:
            return error
        attempts = self.db.attempts.list_recent_for_user(user["id"], limit=10)
        return self.ok({"attempts": attempts})
