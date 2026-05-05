from pathlib import Path

from flask import current_app, make_response, redirect, render_template, url_for


class LitePageRenderer:
    def __init__(self, user_manager, db_manager):
        self.user_manager = user_manager
        self.db_manager = db_manager

    def render(self, request, template_name, page_title, min_role=None, required_feature=None, **page_context):
        user = self.user_manager.check_user(request)
        if not user:
            return redirect(url_for("login"))

        feature_access = self._lite_feature_access()
        if required_feature and not feature_access.get(required_feature, False):
            return redirect(url_for("home_page"))

        if min_role and not self.user_manager.user_has_role(user, min_role):
            return redirect(url_for("home_page"))

        full_page_context = {
            **page_context,
            "asset_version": self.asset_version(),
            "lite_mode": True,
        }
        return render_template(
            template_name,
            page_title=page_title,
            current_user=user,
            feature_access=feature_access,
            page_context=full_page_context,
            asset_version=full_page_context["asset_version"],
            lite_mode=True,
        )

    def build_logout_response(self):
        response = make_response(redirect(url_for("home_page")))
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
        static_root = Path(current_app.static_folder or "")
        app_bundle = static_root / "JS" / "app.js"
        if not app_bundle.exists():
            return "dev"
        return str(int(app_bundle.stat().st_mtime))

    def _lite_feature_access(self):
        feature_access = dict(self.db_manager.site_features.enabled_map())
        feature_access["global_stats_page"] = False
        feature_access["live_exams_page"] = False
        return feature_access
