# db_methods/t_users.py


class UsersTable:
    def __init__(self, db):
        self.db = db

    def create(self, username, password_hash, role="user", email=None, status="active"):
        self.db.execute(
            """
            INSERT INTO users (username, email, password_hash, role, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, email, password_hash, role, status),
        )

    def get_by_id(self, user_id):
        _, row = self.db.execute(
            """
            SELECT id, username, email, password_hash, role, status, created_at, updated_at, last_login_at
            FROM users WHERE id = ?
            """,
            (user_id,),
            fetchone=True,
        )
        return self._row_to_user(row)

    def get(self, username):
        _, row = self.db.execute(
            """
            SELECT id, username, email, password_hash, role, status, created_at, updated_at, last_login_at
            FROM users WHERE lower(username) = lower(?)
            """,
            (username,),
            fetchone=True,
        )
        return self._row_to_user(row)

    def get_by_email(self, email):
        _, row = self.db.execute(
            """
            SELECT id, username, email, password_hash, role, status, created_at, updated_at, last_login_at
            FROM users WHERE lower(email) = lower(?)
            """,
            (email,),
            fetchone=True,
        )
        return self._row_to_user(row)

    def all(self):
        _, rows = self.db.execute(
            """
            SELECT id, username, email, role, status, created_at, last_login_at
            FROM users ORDER BY username
            """,
            fetchall=True,
        )
        return [
            {
                "id": row["id"],
                "username": row["username"],
                "email": row["email"],
                "role": row["role"],
                "status": row["status"],
                "created_at": row["created_at"],
                "last_login_at": row["last_login_at"],
            }
            for row in rows
        ]

    def update(self, user_id, username, email, role, status):
        self.db.execute(
            """
            UPDATE users
            SET username = ?, email = ?, role = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (username, email, role, status, user_id),
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
        return {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "password_hash": row["password_hash"],
            "role": row["role"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_login_at": row["last_login_at"],
        }
