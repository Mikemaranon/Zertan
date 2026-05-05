from pathlib import Path

from flask import Flask
from jinja2 import ChoiceLoader, FileSystemLoader

from app.web_server.data_m.db_manager import DBManager
from app.web_server.services_m.service_manager import ServiceManager

from .api_manager import LiteApiManager
from .app_routes import LiteAppRoutes
from .runtime_config import get_runtime_config
from .user_manager import LiteUserManager


class LiteServer:
    def __init__(self, app: Flask, run_server=True):
        self.app = app
        self.runtime_config = get_runtime_config()
        self.project_root = self.runtime_config["app_root"]
        self.media_root = self.runtime_config["media_root"]
        self.secret_key = self.runtime_config["secret_key"]

        self._configure_app()

        self.DBManager = self.init_db_manager()
        self.user_manager = self.init_user_manager()
        self.service_manager = self.init_service_manager()
        self.app_routes = self.init_app_routes()
        self.api_manager = self.init_api_manager()

        if run_server:
            self.run()

    def _configure_app(self):
        self.app.secret_key = self.secret_key
        self.app.config["JSON_SORT_KEYS"] = False
        self.app.config["APP_ROOT"] = str(self.project_root)
        self.app.config["DATA_ROOT"] = str(self.runtime_config["data_root"])
        self.app.config["DB_PATH"] = str(self.runtime_config["db_path"])
        self.app.config["MEDIA_ROOT"] = str(self.media_root)
        self.app.config["UPLOAD_FOLDER"] = str(self.media_root)
        self.app.config["INSTANCE_ID"] = self.runtime_config["instance_id"]
        self.app.config["JWT_LIFETIME_HOURS"] = self.runtime_config["jwt_lifetime_hours"]
        self.app.config["COOKIE_SECURE"] = self.runtime_config["cookie_secure"]
        self.app.config["COOKIE_SAMESITE"] = self.runtime_config["cookie_samesite"]
        self.app.config["DEBUG"] = self.runtime_config["debug"]
        self.app.config["SEED_DEMO_CONTENT"] = self.runtime_config["seed_demo_content"]
        self.app.config["LITE_MODE"] = True
        self.app.config["LITE_ROOT"] = str(self.runtime_config["lite_root"])

    def run(self):
        self.app.run(
            debug=self.runtime_config["debug"],
            host=self.runtime_config["host"],
            port=self.runtime_config["port"],
        )

    def init_db_manager(self):
        return DBManager(runtime_config=self.runtime_config)

    def init_user_manager(self):
        return LiteUserManager(
            secret_key=self.secret_key,
            db_manager=self.DBManager,
            runtime_config=self.runtime_config,
        )

    def init_service_manager(self):
        return ServiceManager(
            self.DBManager,
            project_root=self.project_root,
            media_root=self.media_root,
            runtime_config=self.runtime_config,
            user_manager=self.user_manager,
        )

    def init_app_routes(self):
        return LiteAppRoutes(self.app, self.user_manager, self.DBManager, self.service_manager)

    def init_api_manager(self):
        return LiteApiManager(self.app, self.user_manager, self.DBManager, self.service_manager)


def create_app(*, run_server=False):
    repo_root = Path(__file__).resolve().parents[2]
    lite_template_root = Path(__file__).resolve().parents[1] / "web_app"
    main_template_root = repo_root / "app" / "web_app"
    main_static_root = main_template_root / "static"

    app = Flask(
        __name__,
        template_folder=str(lite_template_root),
        static_folder=str(main_static_root),
    )
    app.jinja_loader = ChoiceLoader(
        [
            FileSystemLoader(str(lite_template_root)),
            FileSystemLoader(str(main_template_root)),
        ]
    )

    server = LiteServer(app, run_server=run_server)
    app.extensions["lite_server"] = server
    return app
