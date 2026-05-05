from pathlib import Path

from flask import current_app, jsonify, redirect, request, send_from_directory, url_for

from .page_renderer import LitePageRenderer


ROUTE_DEFINITIONS = (
    ("/", "home", "get_home", ["GET"]),
    ("/home", "home_page", "get_home_page", ["GET"]),
    ("/dashboard", "dashboard", "get_dashboard", ["GET"]),
    ("/catalog", "catalog", "get_catalog", ["GET"]),
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
    ("/media/<path:asset_path>", "media_asset", "get_media_asset", ["GET"]),
)


class LiteAppRoutes:
    def __init__(self, app, user_manager, db_manager, service_manager):
        self.app = app
        self.user_manager = user_manager
        self.db_manager = db_manager
        self.service_manager = service_manager
        self.page_renderer = LitePageRenderer(user_manager, db_manager)
        self._register_routes()

    def _register_routes(self):
        for rule, endpoint, handler_name, methods in ROUTE_DEFINITIONS:
            self.app.add_url_rule(rule, endpoint, getattr(self, handler_name), methods=methods)

    def get_home(self):
        return redirect(url_for("home_page"))

    def get_login(self):
        return redirect(url_for("home_page"))

    def get_healthz(self):
        return jsonify({"status": "ok", "service": "zertan-lite"}), 200

    def get_home_page(self):
        return self._render_page(
            "home/home.html",
            "Home",
            lite_connection=self._build_lite_connection_context(),
        )

    def get_logout(self):
        return self.page_renderer.build_logout_response()

    def get_dashboard(self):
        return self._render_page("home/dashboard.html", "Dashboard")

    def get_catalog(self):
        return self._render_page("home/catalog.html", "Exam Catalog")

    def get_exam_detail(self, exam_id):
        return self._render_page("exam/detail.html", "Study Mode", exam_id=exam_id)

    def get_exam_builder(self, exam_id):
        return self._render_page("exam/builder.html", "Exam Builder", exam_id=exam_id)

    def get_exam_runner(self, attempt_id):
        return self._render_page("exam/runner.html", "Exam Runner", attempt_id=attempt_id)

    def get_attempt_results(self, attempt_id):
        return self._render_page("exam/results.html", "Attempt Results", attempt_id=attempt_id)

    def get_profile(self):
        return redirect(url_for("home_page"))

    def get_exam_management(self):
        return self._render_page("management/exams.html", "Exam Management", min_role="reviewer")

    def get_exam_question_management(self, exam_id):
        return self._render_page(
            "management/questions.html",
            "Question Management",
            min_role="reviewer",
            exam_id=exam_id,
        )

    def get_question_create(self, exam_id):
        return self._render_page(
            "management/question_editor.html",
            "Create Question",
            min_role="reviewer",
            exam_id=exam_id,
            return_to=self._get_safe_return_to(),
        )

    def get_question_edit(self, question_id):
        return self._render_page(
            "management/question_editor.html",
            "Edit Question",
            min_role="reviewer",
            question_id=question_id,
            return_to=self._get_safe_return_to(),
        )

    def redirect_home(self, **_kwargs):
        return redirect(url_for("home_page"))

    def get_media_asset(self, asset_path):
        user = self.user_manager.check_user(request)
        if not user:
            return redirect(url_for("home_page"))

        media_root = Path(current_app.config["MEDIA_ROOT"]).resolve()
        response = send_from_directory(media_root, asset_path)
        response.headers["Cache-Control"] = "private, max-age=3600"
        return response

    def _render_page(self, template_name, page_title, **page_context):
        return self.page_renderer.render(request, template_name, page_title, **page_context)

    def _get_safe_return_to(self):
        return_to = (request.args.get("return_to") or "").strip()
        if not return_to.startswith("/") or return_to.startswith("//"):
            return ""
        return return_to

    def _build_lite_connection_context(self):
        connection_service = self.service_manager.connection_info
        detected_addresses = connection_service.list_detected_ipv4_addresses()
        primary_ip = connection_service._select_primary_lan_ip(detected_addresses)
        port = connection_service.port
        listen_scope = connection_service._listen_scope()

        return {
            "primary_ip": primary_ip,
            "port": port,
            "url": f"http://{primary_ip}:{port}" if primary_ip else "",
            "listen_scope": listen_scope,
            "share_hint": connection_service._share_hint(primary_ip),
            "detected_ipv4_addresses": detected_addresses,
            "bind_host": connection_service.bind_host,
        }
