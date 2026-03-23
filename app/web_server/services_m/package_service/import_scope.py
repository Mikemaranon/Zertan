class PackageImportScopeResolver:
    def __init__(self, db_manager):
        self.db = db_manager

    def resolve_group_ids(
        self,
        exam_payload,
        explicit_group_ids=None,
        explicit_scope_mode=None,
        allowed_group_ids=None,
        allow_global=True,
    ):
        normalized_explicit_group_ids = self.db.exams._normalize_group_ids(explicit_group_ids)
        normalized_scope_mode = str(explicit_scope_mode or "").strip().lower()
        if normalized_scope_mode == "global":
            return []
        if normalized_scope_mode == "groups":
            if normalized_explicit_group_ids:
                return normalized_explicit_group_ids
            raise ValueError("Select at least one group for this imported exam.")
        if normalized_explicit_group_ids:
            return normalized_explicit_group_ids

        package_group_codes = [
            str(value).strip()
            for value in exam_payload.get("group_codes", [])
            if str(value).strip()
        ]
        if package_group_codes:
            return self._resolve_package_group_codes(package_group_codes)

        if exam_payload.get("scope_mode") == "groups" and not allow_global:
            raise ValueError("Select at least one group for this imported exam.")

        return []

    def _resolve_package_group_codes(self, package_group_codes):
        placeholders = ",".join("?" for _ in package_group_codes)
        rows = self.db.execute(
            f"""
            SELECT id, code
            FROM user_groups
            WHERE lower(code) IN ({placeholders})
            ORDER BY id
            """,
            tuple(code.lower() for code in package_group_codes),
            fetchall=True,
        )
        code_to_id = {row["code"].lower(): row["id"] for row in rows}
        missing_codes = [code for code in package_group_codes if code.lower() not in code_to_id]
        if missing_codes:
            raise ValueError("The imported package references groups that do not exist in this domain.")
        return [code_to_id[code.lower()] for code in package_group_codes]
