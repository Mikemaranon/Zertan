# db_manager.py

from .db_methods import (
    AgentLogsTable,
    AttemptsTable,
    ExamsTable,
    QuestionsTable,
    SessionsTable,
    StatisticsTable,
    UsersTable,
)
from .utils import Database, LogRepository


class DBManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "initialized") and self.initialized:
            return

        self.db = Database()
        self.logger = LogRepository()

        self.users = UsersTable(self.db)
        self.sessions = SessionsTable(self.db)
        self.exams = ExamsTable(self.db)
        self.questions = QuestionsTable(self.db)
        self.attempts = AttemptsTable(self.db)
        self.statistics = StatisticsTable(self.db)
        self.agent_logs = AgentLogsTable(self.db)

        self.initialized = True

    def execute(self, query, params=(), *, fetchone=False, fetchall=False):
        op, data = self.db.execute(query, params, fetchone=fetchone, fetchall=fetchall)

        if op in ("INSERT", "UPDATE", "DELETE") and "data_logs" not in query.lower():
            self.logger.log(
                level="INFO",
                source="DBManager",
                message=f"{op} executed",
                payload={"query": query, "params": params},
            )

        return data
