# web_server/app_routes.py

from pathlib import Path

from flask import abort, current_app, jsonify, redirect, render_template, request, send_from_directory, url_for

from support_m import ProtectedPageRenderer


ROUTE_DEFINITIONS = (
    ("/", "home", "get_home", ["GET"]),
    ("/home", "home_page", "get_home_page", ["GET"]),
    ("/dashboard", "dashboard", "get_dashboard", ["GET"]),
    ("/global-stats", "global_stats", "get_global_stats", ["GET"]),
    ("/access-info", "access_info", "get_access_info", ["GET"]),
    ("/catalog", "catalog", "get_catalog", ["GET"]),
    ("/live-exams", "live_exams", "get_live_exams", ["GET"]),
    ("/login", "login", "get_login", ["GET"]),
    ("/healthz", "healthz", "get_healthz", ["GET"]),
    ("/logout", "logout", "get_logout", ["GET", "POST"]),
    ("/exams/<int:exam_id>", "exam_detail", "get_exam_detail", ["GET"]),
    ("/exams/<int:exam_id>/builder", "exam_builder", "get_exam_builder", ["GET"]),
    ("/attempts/<int:attempt_id>/run", "exam_runner", "get_exam_runner", ["GET"]),
    ("/attempts/<int:attempt_id>/results", "attempt_results", "get_attempt_results", ["GET"]),
    ("/profile", "profile", "get_profile", ["GET"]),
    ("/management/exams", "exam_management", "get_exam_management", ["GET"]),
    (
        "/management/exams/<int:exam_id>/questions",
        "exam_question_management",
        "get_exam_question_management",
        ["GET"],
    ),
    ("/exams/<int:exam_id>/questions/new", "question_create", "get_question_create", ["GET"]),
    ("/questions/<int:question_id>/edit", "question_edit", "get_question_edit", ["GET"]),
    ("/admin", "admin", "get_admin", ["GET"]),
    ("/log-registry", "log_registry", "get_log_registry", ["GET"]),
    ("/log-registry/exams/<int:exam_id>", "log_registry_exam", "get_log_registry_exam", ["GET"]),
    ("/media/<path:asset_path>", "media_asset", "get_media_asset", ["GET"]),
)


class AppRoutes:
    def __init__(self, app, user_manager, db_manager):
        self.app = app
        self.user_manager = user_manager
        self.db_manager = db_manager
        self.page_renderer = ProtectedPageRenderer(user_manager, db_manager)
        self._register_routes()

    def _register_routes(self):
        for rule, endpoint, handler_name, methods in ROUTE_DEFINITIONS:
            self.app.add_url_rule(rule, endpoint, getattr(self, handler_name), methods=methods)

    def get_home(self):
        user = self.user_manager.check_user(request)
        if user:
            return redirect(url_for("home_page"))
        return redirect(url_for("login"))

    def get_login(self):
        user = self.user_manager.check_user(request)
        if user:
            return redirect(url_for("home_page"))
        return render_template(
            "auth/login.html",
            page_title="Login",
            show_seeded_accounts=bool(current_app.config.get("SEED_DEMO_CONTENT")),
        )

    def get_healthz(self):
        return jsonify({"status": "ok"}), 200

    def get_home_page(self):
        return self._render_auth_page("home/home.html", "Home")

    def get_logout(self):
        token = self.user_manager.get_token_from_cookie(request)
        return self.page_renderer.build_logout_response(token)

    def get_dashboard(self):
        return self._render_auth_page("home/dashboard.html", "Dashboard")

    def get_access_info(self):
        return self._render_auth_page("home/access_info.html", "Connection Info")

    def get_catalog(self):
        return self._render_auth_page("home/catalog.html", "Exam Catalog")

    def get_global_stats(self):
        return self._render_auth_page(
            "home/global_stats.html",
            "Global Stats",
            required_feature="global_stats_page",
        )

    def get_live_exams(self):
        return self._render_auth_page(
            "home/live_exams.html",
            "Live Exams",
            required_feature="live_exams_page",
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
        return redirect(url_for("home_page"))

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

    def get_log_registry(self):
        return self._render_auth_page("management/log_registry.html", "Log Registry", min_role="examiner")

    def get_log_registry_exam(self, exam_id):
        return self._render_auth_page(
            "management/log_registry_detail.html",
            "Exam Log Registry",
            min_role="examiner",
            exam_id=exam_id,
        )

    def get_media_asset(self, asset_path):
        user = self.user_manager.check_user(request)
        if not user:
            return abort(401)

        media_root = Path(current_app.config["MEDIA_ROOT"]).resolve()
        response = send_from_directory(media_root, asset_path)
        response.headers["Cache-Control"] = "private, max-age=3600"
        return response

    def _render_auth_page(self, template_name, page_title, min_role=None, required_feature=None, **page_context):
        return self.page_renderer.render(
            request,
            template_name,
            page_title,
            min_role=min_role,
            required_feature=required_feature,
            **page_context,
        )

    def _get_safe_return_to(self):
        return_to = (request.args.get("return_to") or "").strip()
        if not return_to.startswith("/") or return_to.startswith("//"):
            return ""
        return return_to
