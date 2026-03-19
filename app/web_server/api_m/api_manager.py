from flask import jsonify

from .domain_registry import register_domain_apis


class ApiManager:
    def __init__(self, app, user_manager, db_manager):
        self.app = app
        self.user_manager = user_manager
        self.db_manager = db_manager
        self.registered_domains = []
        self._register_core_api_routes()
        self._register_domain_apis()

    def _register_core_api_routes(self):
        self.app.add_url_rule("/api/check", "check", self.api_check, methods=["GET"])

    def _register_domain_apis(self):
        self.registered_domains = register_domain_apis(
            self.app,
            self.user_manager,
            self.db_manager,
        )
        for api_name in self.registered_domains:
            self.app.logger.info("Loaded API: %s", api_name)

    def api_check(self):
        return jsonify({"status": "ok"}), 200
