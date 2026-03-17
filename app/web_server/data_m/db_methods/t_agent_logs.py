# db_methods/t_agent_logs.py


class AgentLogsTable:
    def __init__(self, db):
        self.db = db

    def create(self, action, details):
        self.db.execute(
            """
            INSERT INTO agent_logs (action, details)
            VALUES (?, ?)
            """,
            (action, details),
        )

    def all(self):
        _, rows = self.db.execute(
            """
            SELECT id, action, details, created_at
            FROM agent_logs
            ORDER BY id DESC
            """,
            fetchall=True,
        )
        return [
            {
                "id": row["id"],
                "action": row["action"],
                "details": row["details"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def delete(self, log_id):
        self.db.execute("DELETE FROM agent_logs WHERE id = ?", (log_id,))
