# web_server/app_routes.py

from pathlib import Path

from flask import abort, current_app, make_response, redirect, render_template, request, send_from_directory, url_for

from data_m import DBManager
from user_m import UserManager


class AppRoutes:
    def __init__(self, app, user_manager: UserManager, DBManager: DBManager):
        self.app = app
        self.user_manager = user_manager
        self.DBManager = DBManager
        self._register_routes()

    def _register_routes(self):
        self.app.add_url_rule("/", "home", self.get_home, methods=["GET"])
        self.app.add_url_rule("/dashboard", "dashboard", self.get_dashboard, methods=["GET"])
        self.app.add_url_rule("/global-stats", "global_stats", self.get_global_stats, methods=["GET"])
        self.app.add_url_rule("/catalog", "catalog", self.get_catalog, methods=["GET"])
        self.app.add_url_rule("/login", "login", self.get_login, methods=["GET"])
        self.app.add_url_rule("/logout", "logout", self.get_logout, methods=["GET", "POST"])
        self.app.add_url_rule("/exams/<int:exam_id>", "exam_detail", self.get_exam_detail, methods=["GET"])
        self.app.add_url_rule("/exams/<int:exam_id>/builder", "exam_builder", self.get_exam_builder, methods=["GET"])
        self.app.add_url_rule("/attempts/<int:attempt_id>/run", "exam_runner", self.get_exam_runner, methods=["GET"])
        self.app.add_url_rule("/attempts/<int:attempt_id>/results", "attempt_results", self.get_attempt_results, methods=["GET"])
        self.app.add_url_rule("/profile", "profile", self.get_profile, methods=["GET"])
        self.app.add_url_rule("/management/exams", "exam_management", self.get_exam_management, methods=["GET"])
        self.app.add_url_rule(
            "/management/exams/<int:exam_id>/questions",
            "exam_question_management",
            self.get_exam_question_management,
            methods=["GET"],
        )
        self.app.add_url_rule("/exams/<int:exam_id>/questions/new", "question_create", self.get_question_create, methods=["GET"])
        self.app.add_url_rule("/questions/<int:question_id>/edit", "question_edit", self.get_question_edit, methods=["GET"])
        self.app.add_url_rule("/admin", "admin", self.get_admin, methods=["GET"])
        self.app.add_url_rule("/media/<path:asset_path>", "media_asset", self.get_media_asset, methods=["GET"])

    def get_home(self):
        user = self.user_manager.check_user(request)
        if user:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    def get_login(self):
        user = self.user_manager.check_user(request)
        if user:
            return redirect(url_for("dashboard"))
        return render_template("auth/login.html", page_title="Login")

    def get_logout(self):
        token = self.user_manager.get_token_from_cookie(request)
        self.user_manager.logout(token)
        response = make_response(redirect(url_for("login")))
        response.delete_cookie("token")
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    def get_dashboard(self):
        return self._render_auth_page("home/dashboard.html", "Dashboard")

    def get_catalog(self):
        return self._render_auth_page("home/catalog.html", "Exam Catalog")

    def get_global_stats(self):
        return self._render_auth_page(
            "home/global_stats.html",
            "Global Stats",
            required_feature="global_stats_page",
        )

    def get_exam_detail(self, exam_id):
        return self._render_auth_page("exam/detail.html", "Study Mode", exam_id=exam_id)

    def get_exam_builder(self, exam_id):
        return self._render_auth_page("exam/builder.html", "Exam Builder", exam_id=exam_id)

    def get_exam_runner(self, attempt_id):
        return self._render_auth_page("exam/runner.html", "Exam Runner", attempt_id=attempt_id)

    def get_attempt_results(self, attempt_id):
        return self._render_auth_page("exam/results.html", "Attempt Results", attempt_id=attempt_id)

    def get_profile(self):
        return redirect(url_for("dashboard"))

    def get_exam_management(self):
        return self._render_auth_page("management/exams.html", "Exam Management", min_role="reviewer")

    def get_question_create(self, exam_id):
        return self._render_auth_page(
            "management/question_editor.html",
            "Create Question",
            min_role="reviewer",
            exam_id=exam_id,
            return_to=self._get_safe_return_to(),
        )

    def get_exam_question_management(self, exam_id):
        return self._render_auth_page(
            "management/questions.html",
            "Question Management",
            min_role="reviewer",
            exam_id=exam_id,
        )

    def get_question_edit(self, question_id):
        return self._render_auth_page(
            "management/question_editor.html",
            "Edit Question",
            min_role="reviewer",
            question_id=question_id,
            return_to=self._get_safe_return_to(),
        )

    def get_admin(self):
        return self._render_auth_page("management/admin.html", "Admin Panel", min_role="administrator")

    def get_media_asset(self, asset_path):
        user = self.user_manager.check_user(request)
        if not user:
            return abort(401)

        media_root = Path(current_app.config["MEDIA_ROOT"]).resolve()
        response = send_from_directory(media_root, asset_path)
        response.headers["Cache-Control"] = "private, max-age=3600"
        return response

    def _render_auth_page(self, template_name, page_title, min_role=None, required_feature=None, **page_context):
        user = self.user_manager.check_user(request)
        if not user:
            return redirect(url_for("login"))
        feature_access = self.DBManager.site_features.enabled_map()
        if required_feature and not feature_access.get(required_feature, False):
            return render_template(
                "shared/forbidden.html",
                page_title="Unavailable",
                current_user=user,
                feature_access=feature_access,
                forbidden_title="Workspace unavailable",
                forbidden_message="This workspace is currently disabled by an administrator.",
            ), 403
        if min_role and not self.user_manager.user_has_role(user, min_role):
            return render_template(
                "shared/forbidden.html",
                page_title="Forbidden",
                current_user=user,
                feature_access=feature_access,
            ), 403
        return render_template(
            template_name,
            page_title=page_title,
            current_user=user,
            feature_access=feature_access,
            page_context=page_context,
        )

    def _get_safe_return_to(self):
        return_to = (request.args.get("return_to") or "").strip()
        if not return_to.startswith("/") or return_to.startswith("//"):
            return ""
        return return_to
