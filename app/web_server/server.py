# web_server/server.py

import os
from pathlib import Path

from flask import Flask

from api_m import ApiManager
from app_routes import AppRoutes
from data_m import DBManager
from user_m import UserManager


class Server:
    def __init__(self, app: Flask, run_server=True):
        self.app = app
        self.project_root = Path(__file__).resolve().parents[1]
        self.media_root = self.project_root / "web_server" / "data_m" / "assets"
        self.secret_key = os.environ.get(
            "SECRET_KEY",
            "zertan-development-secret-key-2026-32b",
        )
        self.app.secret_key = self.secret_key
        self.app.config["JSON_SORT_KEYS"] = False
        self.app.config["MEDIA_ROOT"] = str(self.media_root)
        self.app.config["UPLOAD_FOLDER"] = str(self.media_root)

        self.DBManager = self.ini_DBManager()
        self.user_manager = self.ini_user_manager()
        self.app_routes = self.ini_app_routes()
        self.api_manager = self.ini_api_manager()

        if run_server:
            self.run()

    def run(self):
        port = int(os.environ.get("PORT", 5050))
        self.app.run(debug=True, host="0.0.0.0", port=port)

    def ini_DBManager(self):
        return DBManager()

    def ini_user_manager(self):
        return UserManager(secret_key=self.secret_key, db_manager=self.DBManager)

    def ini_app_routes(self):
        return AppRoutes(self.app, self.user_manager, self.DBManager)

    def ini_api_manager(self):
        return ApiManager(self.app, self.user_manager, self.DBManager)
