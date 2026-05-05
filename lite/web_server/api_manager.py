from flask import current_app, jsonify

from app.web_server.api_m.domains.attempts_api import AttemptsAPI
from app.web_server.api_m.domains.auth_api import AuthAPI
from app.web_server.api_m.domains.exams_api import ExamsAPI
from app.web_server.api_m.domains.import_export_api import ImportExportAPI
from app.web_server.api_m.domains.questions_api import QuestionsAPI
from app.web_server.api_m.domains.statistics_api import StatisticsAPI
from app.web_server.api_m.domains.user_api import UserAPI


class LiteStatisticsAPI(StatisticsAPI):
    def register(self):
        self.app.add_url_rule("/api/statistics/overview", endpoint="api_statistics_overview", view_func=self.overview, methods=["GET"])
        self.app.add_url_rule("/api/statistics/me", endpoint="api_statistics_me", view_func=self.my_statistics, methods=["GET"])
        self.app.add_url_rule(
            "/api/statistics/exams/<int:exam_id>",
            endpoint="api_statistics_exam",
            view_func=self.exam_statistics,
            methods=["GET"],
        )


REGISTERED_LITE_DOMAIN_APIS = (
    AttemptsAPI,
    AuthAPI,
    ExamsAPI,
    ImportExportAPI,
    QuestionsAPI,
    LiteStatisticsAPI,
    UserAPI,
)


class LiteApiManager:
    def __init__(self, app, user_manager, db_manager, service_manager):
        self.app = app
        self.user_manager = user_manager
        self.db_manager = db_manager
        self.service_manager = service_manager
        self.registered_domains = []
        self._register_core_api_routes()
        self._register_domain_apis()

    def _register_core_api_routes(self):
        self.app.add_url_rule("/api/check", "check", self.api_check, methods=["GET"])

    def _register_domain_apis(self):
        for api_class in REGISTERED_LITE_DOMAIN_APIS:
            api_class(self.app, self.user_manager, self.db_manager, self.service_manager).register()
            self.registered_domains.append(api_class.__name__)
            self.app.logger.info("Loaded Lite API: %s", api_class.__name__)

    def api_check(self):
        return jsonify(
            {
                "status": "ok",
                "service": "zertan-lite",
                "instance_id": current_app.config.get("INSTANCE_ID", ""),
            }
        ), 200
