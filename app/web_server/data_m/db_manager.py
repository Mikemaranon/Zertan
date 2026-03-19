# db_manager.py

from .db_methods import (
    AgentLogsTable,
    AttemptsTable,
    ExamsTable,
    GroupsTable,
    LiveExamsTable,
    QuestionsTable,
    SessionsTable,
    SiteFeaturesTable,
    StatisticsTable,
    UsersTable,
)
from .utils import Database, LogRepository


class DBManager:
    def __init__(self, *, db=None, logger=None, runtime_config=None):
        self.db = db or Database(runtime_config=runtime_config)
        self.logger = logger or LogRepository(self.db)

        self.users = UsersTable(self.db)
        self.groups = GroupsTable(self.db)
        self.sessions = SessionsTable(self.db)
        self.exams = ExamsTable(self.db)
        self.questions = QuestionsTable(self.db)
        self.attempts = AttemptsTable(self.db)
        self.live_exams = LiveExamsTable(self.db)
        self.site_features = SiteFeaturesTable(self.db)
        self.statistics = StatisticsTable(self.db)
        self.agent_logs = AgentLogsTable(self.db)

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
