# api_m/domains/base_api.py

from flask import jsonify

from user_m import UserManager


class BaseAPI:
    def __init__(self, app, user_manager: UserManager, db, services):
        self.app = app
        self.user_manager = user_manager
        self.db = db
        self.services = services

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
        return self.user_manager.user_has_role(user, "administrator")

    def list_exam_scope_options_for_user(self, user):
        return self.db.groups.list_scope_options_for_user(None if self.user_is_administrator(user) else user["id"])

    def list_exam_scope_group_ids_for_user(self, user):
        if self.user_is_administrator(user):
            return [group["id"] for group in self.db.groups.list_scope_options_for_user(None)]
        return self.db.groups.list_ids_for_user(user["id"])

    def user_can_access_exam(self, user, exam_id):
        return self.db.exams.user_can_access(
            exam_id,
            None if self.user_is_administrator(user) else user["id"],
            is_administrator=self.user_is_administrator(user),
        )

    def user_can_manage_exam(self, user, exam):
        if not exam:
            return False
        if self.user_is_administrator(user):
            return True
        if not exam.get("group_ids") or not self.user_manager.user_has_role(user, "reviewer"):
            return False
        allowed_group_ids = set(self.list_exam_scope_group_ids_for_user(user))
        return set(exam.get("group_ids", [])).issubset(allowed_group_ids)

    def get_accessible_exam(self, user, exam_id):
        exam = self.db.exams.get(exam_id)
        if not exam:
            return None, self.error("Exam not found.", 404)
        if not self.user_can_access_exam(user, exam_id):
            return None, self.error("Forbidden", 403)
        return exam, None
