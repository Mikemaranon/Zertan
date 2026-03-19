import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.data_m.db_manager import DBManager
from app.web_server.user_m.user_manager import UserManager


class _FakeDatabase:
    def execute(self, query, params=(), *, fetchone=False, fetchall=False):
        return "SELECT", None


class InfrastructureLifecycleTests(unittest.TestCase):
    def test_db_manager_instances_are_not_singletons(self):
        first_manager = DBManager(db=_FakeDatabase())
        second_manager = DBManager(db=_FakeDatabase())

        self.assertIsNot(first_manager, second_manager)

    def test_db_manager_reuses_same_database_for_logging(self):
        database = _FakeDatabase()

        manager = DBManager(db=database)

        self.assertIs(manager.db, database)
        self.assertIs(manager.logger.db, database)

    def test_user_manager_instances_are_not_singletons(self):
        first_manager = UserManager(
            db_manager=object(),
            runtime_config={"secret_key": "secret-a", "jwt_lifetime_hours": 2},
        )
        second_manager = UserManager(
            db_manager=object(),
            runtime_config={"secret_key": "secret-b", "jwt_lifetime_hours": 8},
        )

        self.assertIsNot(first_manager, second_manager)
        self.assertEqual(first_manager.secret_key, "secret-a")
        self.assertEqual(second_manager.secret_key, "secret-b")
        self.assertEqual(first_manager.jwt_lifetime_hours, 2)
        self.assertEqual(second_manager.jwt_lifetime_hours, 8)


if __name__ == "__main__":
    unittest.main()
