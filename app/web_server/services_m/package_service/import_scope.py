from ..exam_definition_service import normalize_exam_group_ids, validate_exam_scope_group_ids


class PackageImportScopeResolver:
    def __init__(self, db_manager):
        self.db = db_manager
        self.groups = self._groups_repository(db_manager)

    def resolve_group_ids(
        self,
        exam_payload,
        explicit_group_ids=None,
        explicit_scope_mode=None,
        allowed_group_ids=None,
        allow_global=True,
    ):
        normalized_explicit_group_ids = normalize_exam_group_ids(explicit_group_ids)
        normalized_scope_mode = str(explicit_scope_mode or "").strip().lower()
        if normalized_scope_mode == "global":
            return []
        if normalized_scope_mode == "groups":
            if normalized_explicit_group_ids:
                return validate_exam_scope_group_ids(
                    self.db,
                    normalized_explicit_group_ids,
                    allowed_group_ids=allowed_group_ids,
                    allow_global=allow_global,
                )
            raise ValueError("Select at least one group for this imported exam.")
        if normalized_explicit_group_ids:
            return validate_exam_scope_group_ids(
                self.db,
                normalized_explicit_group_ids,
                allowed_group_ids=allowed_group_ids,
                allow_global=allow_global,
            )

        package_group_codes = [
            str(value).strip()
            for value in exam_payload.get("group_codes", [])
            if str(value).strip()
        ]
        if package_group_codes:
            return validate_exam_scope_group_ids(
                self.db,
                self._resolve_package_group_codes(package_group_codes),
                allowed_group_ids=allowed_group_ids,
                allow_global=allow_global,
            )

        if exam_payload.get("scope_mode") == "groups" and not allow_global:
            raise ValueError("Select at least one group for this imported exam.")

        return []

    def _resolve_package_group_codes(self, package_group_codes):
        rows = self.groups.list_by_codes(package_group_codes)
        code_to_id = {row["code"].lower(): row["id"] for row in rows}
        missing_codes = [code for code in package_group_codes if code.lower() not in code_to_id]
        if missing_codes:
            raise ValueError("The imported package references groups that do not exist in this domain.")
        return [code_to_id[code.lower()] for code in package_group_codes]

    def _groups_repository(self, db_manager):
        groups = getattr(db_manager, "groups", None)
        if groups is None:
            raise TypeError("PackageImportScopeResolver requires a DB manager exposing db.groups.")
        return groups
