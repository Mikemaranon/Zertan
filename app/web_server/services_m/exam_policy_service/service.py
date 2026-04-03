class ExamPolicyService:
    def __init__(self, db_manager, user_manager):
        self.db = db_manager
        self.user_manager = user_manager

    def user_is_administrator(self, user):
        return self.user_manager.user_has_role(user, "administrator")

    def list_exam_scope_options_for_user(self, user):
        user_id = None if self.user_is_administrator(user) else user["id"]
        return self.db.groups.list_scope_options_for_user(user_id)

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
            return None, "not_found"
        if not self.user_can_access_exam(user, exam_id):
            return None, "forbidden"
        return exam, None

    def build_exam_permissions(self, user, exam):
        can_manage = self.user_manager.user_has_role(user, "examiner") and self.user_can_manage_exam(user, exam)
        return {
            "can_manage": can_manage,
            "can_edit_questions": self.user_manager.user_has_role(user, "reviewer") and self.user_can_manage_exam(user, exam),
            "can_export_package": can_manage,
        }

    def build_question_permissions(self, user, exam):
        return {
            "can_edit_questions": self.user_manager.user_has_role(user, "reviewer") and self.user_can_manage_exam(user, exam),
            "can_delete_questions": self.user_manager.user_has_role(user, "examiner") and self.user_can_manage_exam(user, exam),
        }
