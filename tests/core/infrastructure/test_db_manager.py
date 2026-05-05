import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.data_m.db_manager import DBManager


class _FakeTransactionContext:
    def __init__(self):
        self.entered = 0
        self.exited = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exited += 1
        return False


class _FakeDatabase:
    def __init__(self):
        self.calls = []
        self.transaction_context = _FakeTransactionContext()
        self.responses = {
            "SELECT": ("SELECT", [{"id": 1}]),
            "INSERT": ("INSERT", {"id": 2}),
            "UPDATE": ("UPDATE", {"updated": True}),
            "DELETE": ("DELETE", {"deleted": True}),
        }

    def execute(self, query, params=(), *, fetchone=False, fetchall=False):
        self.calls.append((query, params, fetchone, fetchall))
        operation = query.strip().split()[0].upper()
        return self.responses[operation]

    def transaction(self):
        return self.transaction_context


class _FakeLogger:
    def __init__(self):
        self.entries = []

    def log(self, **payload):
        self.entries.append(payload)


class DBManagerTests(unittest.TestCase):
    def setUp(self):
        self.database = _FakeDatabase()
        self.logger = _FakeLogger()
        self.manager = DBManager(db=self.database, logger=self.logger)

    def test_execute_returns_data_and_logs_mutations_except_data_logs(self):
        selected = self.manager.execute("SELECT * FROM exams", fetchall=True)
        inserted = self.manager.execute("INSERT INTO exams (code) VALUES (?)", ("EXM-100",))
        updated = self.manager.execute("UPDATE exams SET title = ? WHERE id = ?", ("Updated", 2))
        deleted = self.manager.execute("DELETE FROM exams WHERE id = ?", (2,))
        self.manager.execute("INSERT INTO data_logs (message) VALUES (?)", ("internal",))

        self.assertEqual(selected, [{"id": 1}])
        self.assertEqual(inserted, {"id": 2})
        self.assertEqual(updated, {"updated": True})
        self.assertEqual(deleted, {"deleted": True})
        self.assertEqual(len(self.logger.entries), 3)
        self.assertEqual(
            [entry["message"] for entry in self.logger.entries],
            ["INSERT executed", "UPDATE executed", "DELETE executed"],
        )
        self.assertEqual(self.logger.entries[0]["payload"]["params"], ("EXM-100",))

    def test_transaction_delegates_to_underlying_database(self):
        with self.manager.transaction() as transaction:
            self.assertIs(transaction, self.database.transaction_context)

        self.assertEqual(self.database.transaction_context.entered, 1)
        self.assertEqual(self.database.transaction_context.exited, 1)


if __name__ == "__main__":
    unittest.main()
