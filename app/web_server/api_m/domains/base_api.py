# api_m/domains/base_api.py

from flask import jsonify

from ...user_m import UserManager


class BaseAPI:
    def __init__(self, app, user_manager: UserManager, db, services):
        self.app = app
        self.user_manager = user_manager
        self.db = db
        self.services = services
        self.exam_policy = self._require_service("exam_policy")

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

    def user_is_administrator(self, user):
        return self.exam_policy.user_is_administrator(user)

    def list_exam_scope_options_for_user(self, user):
        return self.exam_policy.list_exam_scope_options_for_user(user)

    def list_exam_scope_group_ids_for_user(self, user):
        return self.exam_policy.list_exam_scope_group_ids_for_user(user)

    def user_can_access_exam(self, user, exam_id):
        return self.exam_policy.user_can_access_exam(user, exam_id)

    def user_can_manage_exam(self, user, exam):
        return self.exam_policy.user_can_manage_exam(user, exam)

    def get_accessible_exam(self, user, exam_id):
        exam, failure = self.exam_policy.get_accessible_exam(user, exam_id)
        if failure == "not_found":
            return None, self.error("Exam not found.", 404)
        if failure == "forbidden":
            return None, self.error("Forbidden", 403)
        return exam, None

    def build_exam_permissions(self, user, exam):
        return self.exam_policy.build_exam_permissions(user, exam)

    def build_question_permissions(self, user, exam):
        return self.exam_policy.build_question_permissions(user, exam)

    def _require_service(self, service_name):
        service = getattr(self.services, service_name, None)
        if service is None:
            raise AttributeError(f"services manager is missing required service '{service_name}'.")
        return service
