from pathlib import Path

from flask import current_app, make_response, redirect, render_template, url_for


class ProtectedPageRenderer:
    def __init__(self, user_manager, db_manager):
        self.user_manager = user_manager
        self.db_manager = db_manager

    def render(self, request, template_name, page_title, min_role=None, required_feature=None, **page_context):
        user = self.user_manager.check_user(request)
        if not user:
            return redirect(url_for("login"))

        feature_access = self.db_manager.site_features.enabled_map()
        if required_feature and not feature_access.get(required_feature, False):
            return self._render_forbidden(
                user,
                feature_access,
                page_title="Unavailable",
                forbidden_title="Workspace unavailable",
                forbidden_message="This workspace is currently disabled by an administrator.",
            )

        if min_role and not self.user_manager.user_has_role(user, min_role):
            return self._render_forbidden(user, feature_access)

        full_page_context = {
            **page_context,
            "asset_version": self.asset_version(),
        }
        return render_template(
            template_name,
            page_title=page_title,
            current_user=user,
            feature_access=feature_access,
            page_context=full_page_context,
            asset_version=full_page_context["asset_version"],
        )

    def build_logout_response(self, token):
        self.user_manager.logout(token)
        response = make_response(redirect(url_for("login")))
        response.delete_cookie(
            "token",
            secure=bool(current_app.config.get("COOKIE_SECURE", False)),
            samesite=current_app.config.get("COOKIE_SAMESITE", "Lax"),
        )
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    def asset_version(self):
        app_bundle = Path(current_app.root_path).parent / "web_app" / "static" / "JS" / "app.js"
        if not app_bundle.exists():
            return "dev"
        return str(int(app_bundle.stat().st_mtime))

    def _render_forbidden(
        self,
        user,
        feature_access,
        page_title="Forbidden",
        forbidden_title=None,
        forbidden_message=None,
    ):
        return render_template(
            "shared/forbidden.html",
            page_title=page_title,
            current_user=user,
            feature_access=feature_access,
            forbidden_title=forbidden_title,
            forbidden_message=forbidden_message,
        ), 403
