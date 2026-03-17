# db_methods/t_sessions.py


class SessionsTable:
    def __init__(self, db):
        self.db = db

    def create(self, user_id, token, expires_at):
        self.db.execute(
            """
            INSERT INTO sessions (token, user_id, expires_at)
            VALUES (?, ?, ?)
            """,
            (token, user_id, expires_at),
        )

    def get(self, token):
        _, row = self.db.execute(
            """
            SELECT token, user_id, created_at, expires_at
            FROM sessions
            WHERE token = ?
            """,
            (token,),
            fetchone=True,
        )
        if not row:
            return None
        return {
            "token": row["token"],
            "user_id": row["user_id"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
        }

    def delete(self, token):
        self.db.execute("DELETE FROM sessions WHERE token = ?", (token,))

    def delete_for_user(self, user_id):
        self.db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
