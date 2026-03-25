# data_m/db_methods/__init__.py

from .t_agent_logs import AgentLogsTable
from .t_attempts import AttemptsTable
from .t_exams import ExamsTable
from .t_groups import GroupsTable
from .t_live_exams import LiveExamsTable
from .t_questions import QuestionsTable
from .t_server_aliases import ServerAliasesTable
from .t_sessions import SessionsTable
from .t_site_features import SiteFeaturesTable
from .t_statistics import StatisticsTable
from .t_users import UsersTable

__all__ = [
    "AgentLogsTable",
    "AttemptsTable",
    "ExamsTable",
    "GroupsTable",
    "LiveExamsTable",
    "QuestionsTable",
    "ServerAliasesTable",
    "SessionsTable",
    "SiteFeaturesTable",
    "StatisticsTable",
    "UsersTable",
]
