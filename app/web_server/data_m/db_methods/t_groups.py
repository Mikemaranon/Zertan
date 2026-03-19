import re


class GroupsTable:
    def __init__(self, db):
        self.db = db

    def all(self):
        rows = self._group_rows()
        members_map = self._members_by_group_ids([row["id"] for row in rows])
        return [self._row_to_group(row, members_map.get(row["id"], [])) for row in rows]

    def list_for_user(self, user_id):
        rows = self._group_rows(user_id=user_id)
        members_map = self._members_by_group_ids([row["id"] for row in rows])
        return [self._row_to_group(row, members_map.get(row["id"], [])) for row in rows]

    def get(self, group_id):
        _, row = self.db.execute(
            """
            SELECT
                g.id,
                g.code,
                g.name,
                g.description,
                g.status,
                g.created_at,
                g.updated_at,
                COUNT(m.user_id) AS member_count
            FROM user_groups g
            LEFT JOIN user_group_memberships m ON m.group_id = g.id
            WHERE g.id = ?
            GROUP BY g.id
            """,
            (group_id,),
            fetchone=True,
        )
        if not row:
            return None
        members_map = self._members_by_group_ids([group_id])
        return self._row_to_group(row, members_map.get(group_id, []))

    def list_scope_options_for_user(self, user_id=None):
        if user_id is None:
            groups = self.all()
        else:
            groups = self.list_for_user(user_id)
        return [
            {
                "id": group["id"],
                "code": group["code"],
                "name": group["name"],
                "member_count": group["member_count"],
            }
            for group in groups
        ]

    def list_ids_for_user(self, user_id):
        _, rows = self.db.execute(
            """
            SELECT group_id
            FROM user_group_memberships
            WHERE user_id = ?
            ORDER BY group_id
            """,
            (user_id,),
            fetchall=True,
        )
        return [row["group_id"] for row in rows]

    def set_memberships_for_user(self, user_id, group_ids):
        if not self.db.execute("SELECT id FROM users WHERE id = ?", (user_id,), fetchone=True)[1]:
            return []
        normalized_group_ids = self._normalize_group_ids(group_ids)
        self.db.execute("DELETE FROM user_group_memberships WHERE user_id = ?", (user_id,))
        if not normalized_group_ids:
            return []
        self.db.executemany(
            """
            INSERT INTO user_group_memberships (group_id, user_id)
            VALUES (?, ?)
            """,
            [(group_id, user_id) for group_id in normalized_group_ids],
        )
        return normalized_group_ids

    def create(self, name, description="", user_ids=None):
        normalized_name = self._normalize_name(name)
        if not normalized_name:
            raise ValueError("Group name is required.")
        if self._name_exists(normalized_name):
            raise ValueError("A group with this name already exists.")

        code = self._generate_unique_code(normalized_name)
        self.db.execute(
            """
            INSERT INTO user_groups (code, name, description, status)
            VALUES (?, ?, ?, 'active')
            """,
            (code, normalized_name, self._normalize_description(description)),
        )
        _, row = self.db.execute(
            "SELECT id FROM user_groups WHERE code = ?",
            (code,),
            fetchone=True,
        )
        group_id = row["id"]
        self._sync_memberships(group_id, user_ids or [])
        return self.get(group_id)

    def update(self, group_id, name, description="", user_ids=None):
        existing = self.get(group_id)
        if not existing:
            return None

        normalized_name = self._normalize_name(name)
        if not normalized_name:
            raise ValueError("Group name is required.")
        if self._name_exists(normalized_name, exclude_group_id=group_id):
            raise ValueError("A group with this name already exists.")

        self.db.execute(
            """
            UPDATE user_groups
            SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (normalized_name, self._normalize_description(description), group_id),
        )
        self._sync_memberships(group_id, user_ids or [])
        return self.get(group_id)

    def delete(self, group_id):
        self.db.execute("DELETE FROM user_groups WHERE id = ?", (group_id,))

    def _sync_memberships(self, group_id, user_ids):
        normalized_user_ids = self._normalize_user_ids(user_ids)
        self.db.execute("DELETE FROM user_group_memberships WHERE group_id = ?", (group_id,))
        if not normalized_user_ids:
            return
        self.db.executemany(
            """
            INSERT INTO user_group_memberships (group_id, user_id)
            VALUES (?, ?)
            """,
            [(group_id, user_id) for user_id in normalized_user_ids],
        )

    def _normalize_user_ids(self, user_ids):
        normalized = []
        seen = set()
        for value in user_ids or []:
            try:
                user_id = int(value)
            except (TypeError, ValueError):
                continue
            if user_id < 1 or user_id in seen:
                continue
            if not self.db.execute("SELECT id FROM users WHERE id = ?", (user_id,), fetchone=True)[1]:
                continue
            seen.add(user_id)
            normalized.append(user_id)
        return normalized

    def _normalize_group_ids(self, group_ids):
        normalized = []
        seen = set()
        for value in group_ids or []:
            try:
                group_id = int(value)
            except (TypeError, ValueError):
                continue
            if group_id < 1 or group_id in seen:
                continue
            if not self.db.execute("SELECT id FROM user_groups WHERE id = ?", (group_id,), fetchone=True)[1]:
                continue
            seen.add(group_id)
            normalized.append(group_id)
        return normalized

    def _members_by_group_ids(self, group_ids):
        if not group_ids:
            return {}
        placeholders = ",".join("?" for _ in group_ids)
        _, rows = self.db.execute(
            f"""
            SELECT
                m.group_id,
                u.id,
                u.login_name,
                u.display_name,
                u.role,
                u.status
            FROM user_group_memberships m
            JOIN users u ON u.id = m.user_id
            WHERE m.group_id IN ({placeholders})
            ORDER BY lower(u.display_name), lower(u.login_name)
            """,
            tuple(group_ids),
            fetchall=True,
        )
        members_map = {group_id: [] for group_id in group_ids}
        for row in rows:
            members_map.setdefault(row["group_id"], []).append(
                {
                    "id": row["id"],
                    "login_name": row["login_name"],
                    "display_name": row["display_name"],
                    "role": row["role"],
                    "status": row["status"],
                }
            )
        return members_map

    def _group_rows(self, user_id=None):
        params = []
        query = """
            SELECT
                g.id,
                g.code,
                g.name,
                g.description,
                g.status,
                g.created_at,
                g.updated_at,
                COUNT(m.user_id) AS member_count
            FROM user_groups g
            LEFT JOIN user_group_memberships m ON m.group_id = g.id
        """
        if user_id is not None:
            query += """
                WHERE EXISTS (
                    SELECT 1
                    FROM user_group_memberships scope_m
                    WHERE scope_m.group_id = g.id
                    AND scope_m.user_id = ?
                )
            """
            params.append(user_id)
        query += """
            GROUP BY g.id
            ORDER BY lower(g.name), lower(g.code)
        """
        _, rows = self.db.execute(query, tuple(params), fetchall=True)
        return rows

    def _generate_unique_code(self, name):
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "group"
        base_code = f"grp-{slug}"
        candidate = base_code
        counter = 2
        while self.db.execute("SELECT id FROM user_groups WHERE code = ?", (candidate,), fetchone=True)[1]:
            candidate = f"{base_code}-{counter}"
            counter += 1
        return candidate

    def _name_exists(self, name, exclude_group_id=None):
        params = [name]
        query = "SELECT id FROM user_groups WHERE lower(name) = lower(?)"
        if exclude_group_id is not None:
            query += " AND id != ?"
            params.append(exclude_group_id)
        _, row = self.db.execute(query, tuple(params), fetchone=True)
        return bool(row)

    def _normalize_name(self, name):
        return (name or "").strip()

    def _normalize_description(self, description):
        return (description or "").strip()

    def _row_to_group(self, row, members):
        return {
            "id": row["id"],
            "code": row["code"],
            "name": row["name"],
            "description": row["description"] or "",
            "status": row["status"],
            "member_count": row["member_count"] or 0,
            "members": members,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
