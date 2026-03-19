# services_m/live_exam_service.py

from .attempt_service import AttemptService


class LiveExamService:
    def __init__(self, db_manager):
        self.db = db_manager

    def list_for_admin(self):
        return self.db.live_exams.list_for_admin()

    def list_for_user(self, user_id):
        return self.db.live_exams.list_for_user(user_id)

    def create_live_exam(self, payload, created_by):
        title = str(payload.get("title", "") or "").strip()
        description = str(payload.get("description", "") or "").strip()
        instructions = str(payload.get("instructions", "") or "").strip()
        exam_id = int(payload.get("exam_id") or 0)
        question_count = int(payload.get("question_count") or 0)
        time_limit_minutes = self._normalize_time_limit(payload.get("time_limit_minutes"))
        criteria = self._normalize_criteria(payload)
        direct_user_ids = self._normalize_user_ids(payload.get("user_ids") or payload.get("direct_user_ids") or [])
        group_ids = self._normalize_group_ids(payload.get("group_ids") or [])
        excluded_user_ids = self._normalize_user_ids(payload.get("excluded_user_ids") or [])

        if not title:
            raise ValueError("Live exam title is required.")
        if not exam_id:
            raise ValueError("Select a source exam.")
        if not direct_user_ids and not group_ids:
            raise ValueError("Assign at least one user or group to the live exam.")

        exam = self.db.exams.get(exam_id)
        if not exam:
            raise ValueError("Source exam not found.")

        available_question_ids = self.db.questions.list_filtered_ids(
            exam_id,
            criteria,
        )
        if not available_question_ids:
            raise ValueError("No questions match the selected live exam criteria.")
        if question_count < 1:
            raise ValueError("Question count must be greater than zero.")
        if question_count > len(available_question_ids):
            raise ValueError("Question count exceeds the number of questions that match the selected criteria.")

        eligible_users = self._resolve_assignment_user_ids(direct_user_ids, group_ids, excluded_user_ids)
        if not eligible_users:
            raise ValueError("The selected users and groups do not produce any active assignees.")

        live_exam_id = self.db.live_exams.create(
            {
                "exam_id": exam_id,
                "title": title,
                "description": description,
                "instructions": instructions,
                "question_count": question_count,
                "time_limit_minutes": time_limit_minutes,
                "criteria": criteria,
            },
            created_by,
        )
        self.db.live_exams.set_assignments(live_exam_id, eligible_users)
        return self.db.live_exams.get(live_exam_id)

    def close_live_exam(self, live_exam_id):
        live_exam = self.db.live_exams.get(live_exam_id)
        if not live_exam:
            raise ValueError("Live exam not found.")
        if live_exam["status"] == "closed":
            raise ValueError("Live exam is already closed.")
        return self.db.live_exams.close(live_exam_id)

    def delete_live_exam(self, live_exam_id):
        live_exam = self.db.live_exams.get(live_exam_id)
        if not live_exam:
            raise ValueError("Live exam not found.")
        attempt_ids = self.db.live_exams.list_attempt_ids(live_exam_id)
        for attempt_id in attempt_ids:
            self.db.attempts.delete(attempt_id)
        self.db.live_exams.delete(live_exam_id)

    def start_assignment(self, assignment_id, user):
        assignment = self.db.live_exams.get_assignment(assignment_id)
        if not assignment:
            raise ValueError("Assigned live exam not found.")
        if assignment["live_exam_status"] != "active":
            raise ValueError("This live exam is closed.")
        if assignment["user_id"] != user["id"]:
            raise ValueError("You do not have access to this live exam.")
        if assignment["assignment_status"] == "completed":
            if assignment["attempt_id"]:
                return assignment["attempt_id"]
            raise ValueError("This live exam is already completed.")
        if assignment["attempt_id"]:
            return assignment["attempt_id"]

        criteria = dict(assignment.get("criteria") or {})
        criteria.update(
            {
                "question_count": assignment["question_count"],
                "time_limit_minutes": assignment["time_limit_minutes"],
                "random_order": bool(criteria.get("random_order", True)),
                "live_exam_id": assignment["live_exam_id"],
                "live_exam_assignment_id": assignment["assignment_id"],
                "live_exam_title": assignment["live_exam_title"],
            }
        )
        attempt_id = AttemptService(self.db).create_attempt(
            assignment["exam_id"],
            assignment["user_id"],
            criteria,
        )
        self.db.live_exams.attach_attempt(assignment["assignment_id"], attempt_id)
        return attempt_id

    def mark_completed_for_attempt(self, attempt_id):
        self.db.live_exams.mark_assignment_completed_by_attempt(attempt_id)

    def _normalize_time_limit(self, value):
        if value in (None, "", 0, "0"):
            return None
        normalized = int(value)
        if normalized < 1:
            raise ValueError("Time limit must be zero or a positive number of minutes.")
        return normalized

    def _normalize_user_ids(self, values):
        user_ids = []
        for value in values:
            try:
                normalized = int(value)
            except (TypeError, ValueError):
                continue
            if normalized > 0:
                user_ids.append(normalized)
        return user_ids

    def _normalize_group_ids(self, values):
        group_ids = []
        for value in values:
            try:
                normalized = int(value)
            except (TypeError, ValueError):
                continue
            if normalized > 0:
                group_ids.append(normalized)
        return group_ids

    def _resolve_assignment_user_ids(self, direct_user_ids, group_ids, excluded_user_ids):
        active_users = {
            int(user["id"]): user
            for user in self.db.users.all()
            if user["status"] == "active"
        }
        active_groups = {
            int(group["id"]): group
            for group in self.db.groups.all()
            if group["status"] == "active"
        }

        resolved_user_ids = {user_id for user_id in direct_user_ids if user_id in active_users}
        for group_id in group_ids:
            group = active_groups.get(group_id)
            if not group:
                continue
            for member in group.get("members", []):
                member_id = int(member["id"])
                if member_id in active_users:
                    resolved_user_ids.add(member_id)

        resolved_user_ids.difference_update(
            user_id for user_id in excluded_user_ids if user_id in resolved_user_ids
        )
        return sorted(resolved_user_ids)

    def _normalize_criteria(self, payload):
        return {
            "topics": self._normalize_mode_group(payload.get("topics")),
            "tags": self._normalize_mode_group(payload.get("tags")),
            "question_types": self._normalize_mode_group(payload.get("question_types")),
            "difficulty": str(payload.get("difficulty") or "").strip() or None,
            "random_order": bool(payload.get("random_order", True)),
        }

    def _normalize_mode_group(self, value):
        if isinstance(value, list):
            include = value
            exclude = []
        else:
            include = (value or {}).get("include") or []
            exclude = (value or {}).get("exclude") or []
        normalized_include = self._normalize_string_list(include)
        normalized_exclude = [item for item in self._normalize_string_list(exclude) if item not in normalized_include]
        return {
            "include": normalized_include,
            "exclude": normalized_exclude,
        }

    def _normalize_string_list(self, values):
        normalized = []
        seen = set()
        for value in values or []:
            item = str(value or "").strip()
            if not item or item in seen:
                continue
            seen.add(item)
            normalized.append(item)
        return normalized
