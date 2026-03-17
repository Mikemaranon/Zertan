# web_server/api_m/api_manager.py

import pkgutil
import importlib

from flask import jsonify
from user_m import UserManager
from data_m import DBManager

class ApiManager:
    def __init__(self, app, user_manager: UserManager, DBManager: DBManager):
        self.app = app
        self.user_manager = user_manager
        self.DBManager = DBManager
        self._register_APIs()
        self._autoload_domains()

    # ============================================================
    #                     REGISTERING APIs
    # ============================================================

    def _register_APIs(self):
        self.app.add_url_rule("/api/check", "check", self.API_check, methods=["GET"])

    # ============================================================
    #     AUTOLOAD OF ALL API CLASSES INSIDE api_m/domains/
    # ============================================================

    def _autoload_domains(self):

        import api_m.domains as domains_package

        # Iterate through every module inside api_m/domains/
        for _, module_name, _ in pkgutil.iter_modules(domains_package.__path__):

            full_module = f"{domains_package.__name__}.{module_name}"
            module = importlib.import_module(full_module)

            # Inspect module members
            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                if (
                    isinstance(attr, type)
                    and hasattr(attr, "register")
                    and attr.__name__ != "BaseAPI"
                ):
                    api_instance = attr(self.app, self.user_manager, self.DBManager)
                    api_instance.register()
                    print(f"[API Manager] Loaded API: {attr.__name__}")

    # =========================================
    #       API protocols start from here
    # =========================================
        
    # endpoint to check if the API is working
    def API_check(self):
        return jsonify({"status": "ok"}), 200
    
    