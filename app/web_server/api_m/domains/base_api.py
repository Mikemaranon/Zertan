# api_m/domains/base_api.py

from flask import jsonify

from user_m import UserManager


class BaseAPI:
    def __init__(self, app, user_manager: UserManager, db):
        self.app = app
        self.user_manager = user_manager
        self.db = db

    def ok(self, data, code=200):
        return jsonify(data), code

    def error(self, message, code=400):
        return jsonify({"error": message}), code

    def auth_user(self, request, min_role=None):
        user = self.user_manager.check_user(request)
        if not user:
            return None, self.error("Unauthorized", 401)
        if min_role and not self.user_manager.user_has_role(user, min_role):
            return None, self.error("Forbidden", 403)
        return user, None

    def feature_enabled(self, feature_key):
        feature = self.db.site_features.get(feature_key)
        return bool(feature and feature["enabled"])
