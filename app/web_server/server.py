# web_server/server.py

from flask import Flask

from api_m import ApiManager
from app_routes import AppRoutes
from data_m import DBManager
from services_m import ServiceManager
from support_m import get_runtime_config
from user_m import UserManager


class Server:
    def __init__(self, app: Flask, run_server=True):
        self.app = app
        self.runtime_config = get_runtime_config()
        self.project_root = self.runtime_config["app_root"]
        self.media_root = self.runtime_config["media_root"]
        self.secret_key = self.runtime_config["secret_key"]
        self.app.secret_key = self.secret_key
        self.app.config["JSON_SORT_KEYS"] = False
        self.app.config["APP_ROOT"] = str(self.project_root)
        self.app.config["DATA_ROOT"] = str(self.runtime_config["data_root"])
        self.app.config["DB_PATH"] = str(self.runtime_config["db_path"])
        self.app.config["MEDIA_ROOT"] = str(self.media_root)
        self.app.config["UPLOAD_FOLDER"] = str(self.media_root)
        self.app.config["JWT_LIFETIME_HOURS"] = self.runtime_config["jwt_lifetime_hours"]
        self.app.config["COOKIE_SECURE"] = self.runtime_config["cookie_secure"]
        self.app.config["COOKIE_SAMESITE"] = self.runtime_config["cookie_samesite"]
        self.app.config["DEBUG"] = self.runtime_config["debug"]
        self.app.config["SEED_DEMO_CONTENT"] = self.runtime_config["seed_demo_content"]

        self.DBManager = self.ini_DBManager()
        self.user_manager = self.ini_user_manager()
        self.service_manager = self.ini_service_manager()
        self.app_routes = self.ini_app_routes()
        self.api_manager = self.ini_api_manager()

        if run_server:
            self.run()

    def run(self):
        self.app.run(
            debug=self.runtime_config["debug"],
            host=self.runtime_config["host"],
            port=self.runtime_config["port"],
        )

    def ini_DBManager(self):
        return DBManager(runtime_config=self.runtime_config)

    def ini_user_manager(self):
        return UserManager(
            secret_key=self.secret_key,
            db_manager=self.DBManager,
            runtime_config=self.runtime_config,
        )

    def ini_service_manager(self):
        return ServiceManager(
            self.DBManager,
            project_root=self.project_root,
            media_root=self.media_root,
            runtime_config=self.runtime_config,
        )

    def ini_app_routes(self):
        return AppRoutes(self.app, self.user_manager, self.DBManager)

    def ini_api_manager(self):
        return ApiManager(self.app, self.user_manager, self.DBManager, self.service_manager)


def create_app(*, run_server=False):
    app = Flask(__name__, template_folder="../web_app", static_folder="../web_app/static")
    Server(app, run_server=run_server)
    return app
