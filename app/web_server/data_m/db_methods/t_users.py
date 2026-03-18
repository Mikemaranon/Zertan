# db_methods/t_users.py


class UsersTable:
    def __init__(self, db):
        self.db = db

    def create(self, login_name, display_name, password_hash, role="user", email=None, status="active", avatar_path=None):
        self.db.execute(
            """
            INSERT INTO users (username, email, login_name, display_name, password_hash, role, status, avatar_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (login_name, email, login_name, display_name, password_hash, role, status, avatar_path),
        )

    def get_by_id(self, user_id):
        _, row = self.db.execute(
            """
            SELECT id, username, email, login_name, display_name, password_hash, role, status, avatar_path, created_at, updated_at, last_login_at
            FROM users WHERE id = ?
            """,
            (user_id,),
            fetchone=True,
        )
        return self._row_to_user(row)

    def get_by_login_name(self, login_name):
        _, row = self.db.execute(
            """
            SELECT id, username, email, login_name, display_name, password_hash, role, status, avatar_path, created_at, updated_at, last_login_at
            FROM users WHERE lower(COALESCE(login_name, username)) = lower(?)
            """,
            (login_name,),
            fetchone=True,
        )
        return self._row_to_user(row)

    def get(self, login_name):
        return self.get_by_login_name(login_name)

    def get_by_email(self, email):
        _, row = self.db.execute(
            """
            SELECT id, username, email, login_name, display_name, password_hash, role, status, avatar_path, created_at, updated_at, last_login_at
            FROM users WHERE lower(email) = lower(?)
            """,
            (email,),
            fetchone=True,
        )
        return self._row_to_user(row)

    def all(self):
        _, rows = self.db.execute(
            """
            SELECT id, login_name, display_name, role, status, avatar_path, created_at, last_login_at
            FROM users ORDER BY lower(display_name), lower(login_name)
            """,
            fetchall=True,
        )
        return [
            {
                "id": row["id"],
                "login_name": row["login_name"],
                "display_name": row["display_name"],
                "role": row["role"],
                "status": row["status"],
                "avatar_path": row["avatar_path"],
                "created_at": row["created_at"],
                "last_login_at": row["last_login_at"],
            }
            for row in rows
        ]

    def update(self, user_id, display_name, login_name, role, status):
        self.db.execute(
            """
            UPDATE users
            SET username = ?, login_name = ?, display_name = ?, role = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (login_name, login_name, display_name, role, status, user_id),
        )

    def update_profile(self, user_id, display_name):
        self.db.execute(
            """
            UPDATE users
            SET display_name = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (display_name, user_id),
        )

    def update_password(self, user_id, password_hash):
        self.db.execute(
            """
            UPDATE users
            SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (password_hash, user_id),
        )

    def update_avatar(self, user_id, avatar_path):
        self.db.execute(
            """
            UPDATE users
            SET avatar_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (avatar_path, user_id),
        )

    def touch_last_login(self, user_id):
        self.db.execute(
            """
            UPDATE users
            SET last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user_id,),
        )

    def delete(self, user_id):
        self.db.execute("DELETE FROM users WHERE id = ?", (user_id,))

    def _row_to_user(self, row):
        if not row:
            return None
        login_name = row["login_name"] or row["username"]
        display_name = row["display_name"] or row["username"] or login_name
        return {
            "id": row["id"],
            "username": display_name,
            "login_name": login_name,
            "display_name": display_name,
            "email": row["email"],
            "password_hash": row["password_hash"],
            "role": row["role"],
            "status": row["status"],
            "avatar_path": row["avatar_path"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_login_at": row["last_login_at"],
        }
