# api_m/domains/auth_api.py

from pathlib import Path
from uuid import uuid4

from flask import current_app, jsonify, make_response, request
from werkzeug.utils import secure_filename

from api_m.domains.base_api import BaseAPI


class AuthAPI(BaseAPI):
    ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

    def register(self):
        self.app.add_url_rule("/api/auth/login", endpoint="api_auth_login", view_func=self.login, methods=["POST"])
        self.app.add_url_rule("/api/auth/logout", endpoint="api_auth_logout", view_func=self.logout, methods=["POST"])
        self.app.add_url_rule("/api/auth/me", endpoint="api_auth_me", view_func=self.me, methods=["GET"])
        self.app.add_url_rule("/api/auth/profile", endpoint="api_auth_profile_update", view_func=self.update_profile, methods=["PUT"])
        self.app.add_url_rule(
            "/api/auth/profile/avatar",
            endpoint="api_auth_profile_avatar",
            view_func=self.update_avatar,
            methods=["POST"],
        )

    def login(self):
        data = request.get_json() or {}
        login_name = (data.get("login_name") or data.get("username") or "").strip()
        password = data.get("password") or ""

        if not login_name or not password:
            return self.error("Login name and password are required.", 400)

        result = self.user_manager.login(login_name, password)
        if not result:
            return self.error("Invalid credentials.", 401)

        response_payload = dict(result)
        token = response_payload.pop("token")
        response = make_response(jsonify(response_payload))
        response.set_cookie(
            "token",
            token,
            httponly=True,
            samesite="Lax",
            max_age=8 * 60 * 60,
        )
        return response

    def logout(self):
        token = self.user_manager.get_token_from_cookie(request)
        self.user_manager.logout(token)
        response = make_response(jsonify({"status": "ok"}))
        response.delete_cookie("token")
        return response

    def me(self):
        user, error = self.auth_user(request)
        if error:
            return error
        return self.ok({"user": user})

    def update_profile(self):
        user, error = self.auth_user(request)
        if error:
            return error

        payload = request.get_json() or {}
        try:
            updated = self.user_manager.update_profile(
                user["id"],
                payload.get("display_name"),
                current_password=payload.get("current_password", ""),
                new_password=payload.get("new_password", ""),
                confirm_password=payload.get("confirm_password", ""),
            )
        except ValueError as exc:
            return self.error(str(exc), 400)

        return self.ok({"user": self.user_manager.public_user(updated)})

    def update_avatar(self):
        user, error = self.auth_user(request)
        if error:
            return error

        uploaded_file = request.files.get("avatar")
        if not uploaded_file or not uploaded_file.filename:
            return self.error("An image file is required.", 400)

        safe_name = secure_filename(uploaded_file.filename)
        extension = Path(safe_name).suffix.lower()
        if extension not in self.ALLOWED_AVATAR_EXTENSIONS:
            return self.error("Unsupported image format.", 400)
        if not (uploaded_file.mimetype or "").startswith("image/"):
            return self.error("The uploaded file must be an image.", 400)

        project_root = Path(current_app.root_path).resolve().parents[0]
        target_dir = project_root / "web_server" / "data_m" / "assets" / "profiles" / str(user["id"])
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{uuid4().hex}{extension}"
        uploaded_file.save(target_path)

        updated = self.user_manager.update_avatar(user["id"], str(target_path.relative_to(project_root)))
        return self.ok({"user": self.user_manager.public_user(updated)})
