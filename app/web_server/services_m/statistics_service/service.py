from ..exam_policy_service import ExamPolicyService


class StatisticsService:
    def __init__(self, db_manager, user_manager, exam_policy=None):
        self.db = db_manager
        self.user_manager = user_manager
        self.exam_policy = exam_policy or ExamPolicyService(db_manager, user_manager)

    def build_dashboard_payload(self, user_id):
        kpis = self.db.statistics.user_overview(user_id)
        by_exam = self.db.statistics.user_success_by_exam(user_id)
        return {
            "overview": {
                "kpis": kpis,
                "by_exam": by_exam,
                "recent_attempts": self.db.attempts.list_recent_for_user(user_id, limit=4),
            },
            "personal": {
                "kpis": kpis,
                "by_exam": by_exam,
                "by_question_type": self.db.statistics.user_success_by_question_type(user_id),
            },
        }

    def build_platform_payload(self, user, requested_group_id):
        scope = self.resolve_platform_scope(user, requested_group_id)
        return {
            "platform": self.db.statistics.platform_overview(scope["scope_group_ids"]),
            "current_user_id": user["id"],
            "current_user_role": user["role"],
            "comparison_groups": scope["comparison_groups"],
            "selected_group_id": scope["selected_group_id"],
        }

    def resolve_platform_scope(self, user, requested_group_id):
        allowed_groups = self.exam_policy.list_exam_scope_options_for_user(user)
        selected_group_id = self._parse_requested_group_id(requested_group_id)

        if selected_group_id is not None:
            allowed_group_ids = {group["id"] for group in allowed_groups}
            if selected_group_id not in allowed_group_ids:
                raise PermissionError("Selected group is not available for this user.")

        is_administrator = self.exam_policy.user_is_administrator(user)
        if is_administrator:
            scope_group_ids = [selected_group_id] if selected_group_id is not None else None
        else:
            scope_group_ids = [selected_group_id] if selected_group_id is not None else [group["id"] for group in allowed_groups]

        return {
            "comparison_groups": allowed_groups,
            "selected_group_id": selected_group_id,
            "scope_group_ids": scope_group_ids,
        }

    def _parse_requested_group_id(self, requested_group_id):
        raw_value = str(requested_group_id or "").strip()
        if not raw_value:
            return None
        try:
            return int(raw_value)
        except ValueError as exc:
            raise ValueError("Group id must be a valid integer.") from exc
