# api_m/domains/auth_api.py

from flask import jsonify, make_response, request

from api_m.domains.base_api import BaseAPI


class AuthAPI(BaseAPI):
    def register(self):
        self.app.add_url_rule("/api/auth/login", endpoint="api_auth_login", view_func=self.login, methods=["POST"])
        self.app.add_url_rule("/api/auth/logout", endpoint="api_auth_logout", view_func=self.logout, methods=["POST"])
        self.app.add_url_rule("/api/auth/me", endpoint="api_auth_me", view_func=self.me, methods=["GET"])

    def login(self):
        data = request.get_json() or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""

        if not username or not password:
            return self.error("Username and password are required.", 400)

        result = self.user_manager.login(username, password)
        if not result:
            return self.error("Invalid credentials.", 401)

        response = make_response(jsonify(result))
        response.set_cookie(
            "token",
            result["token"],
            httponly=True,
            samesite="Lax",
            max_age=8 * 60 * 60,
        )
        return response

    def logout(self):
        token = self.user_manager.get_token_from_cookie(request) or self.user_manager.get_request_token(request)
        self.user_manager.logout(token)
        response = make_response(jsonify({"status": "ok"}))
        response.delete_cookie("token")
        return response

    def me(self):
        user, error = self.auth_user(request)
        if error:
            return error
        return self.ok({"user": user})
