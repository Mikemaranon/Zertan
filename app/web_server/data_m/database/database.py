# database.py

from contextlib import contextmanager
from pathlib import Path
from threading import local

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

from support_m.runtime_config import get_runtime_config

from ..utils.integrity import DatabaseIntegrityManager
from ..utils.migration import DatabaseMigrationManager
from ..utils.seeding_data import DatabaseSeeder
from .db_connector import DBConnector
from .schema import SCHEMA_SQL, SCHEMA_VERSION


class Database:
    def __init__(self, *, connector=None, runtime_config=None):
        self.runtime_config = dict(runtime_config or get_runtime_config())
        self.connector = connector or DBConnector(db_path=self.runtime_config["db_path"])
        self._transaction_state = local()
        self.project_root = self.runtime_config["app_root"]
        self.upload_root = self.runtime_config["media_root"]
        self.init_lock_path = self._build_init_lock_path(self.runtime_config["db_path"])

        self.integrity = DatabaseIntegrityManager(self)
        self.migrations = DatabaseMigrationManager(
            self,
            project_root=self.project_root,
            upload_root=self.upload_root,
        )
        self.seeder = DatabaseSeeder(
            self,
            runtime_config=self.runtime_config,
            project_root=self.project_root,
            upload_root=self.upload_root,
        )

        with self._db_init_lock():
            self._init_db()

    def _build_init_lock_path(self, db_path):
        db_path = Path(db_path)
        return db_path.with_name(f"{db_path.name}.init.lock")

    @contextmanager
    def _db_init_lock(self):
        self.init_lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.init_lock_path.open("w", encoding="utf-8") as lock_file:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _get_transaction_connection(self):
        return getattr(self._transaction_state, "connection", None)

    def _get_transaction_depth(self):
        return getattr(self._transaction_state, "depth", 0)

    @contextmanager
    def _connection_context(self):
        transaction_connection = self._get_transaction_connection()
        if transaction_connection is not None:
            yield transaction_connection, False
            return

        connection = self.connector.connect()
        try:
            yield connection, True
        finally:
            self.connector.close(connection)

    @contextmanager
    def transaction(self):
        transaction_connection = self._get_transaction_connection()
        if transaction_connection is not None:
            self._transaction_state.depth = self._get_transaction_depth() + 1
            try:
                yield transaction_connection
            finally:
                self._transaction_state.depth -= 1
            return

        connection = self.connector.connect()
        self._transaction_state.connection = connection
        self._transaction_state.depth = 1
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            self._transaction_state.connection = None
            self._transaction_state.depth = 0
            self.connector.close(connection)

    def execute(self, query, params=(), *, fetchone=False, fetchall=False):
        with self._connection_context() as (connection, owns_connection):
            cursor = connection.cursor()
            try:
                cursor.execute(query, params)
                if owns_connection:
                    connection.commit()

                op = query.strip().split()[0].upper()
                if fetchone:
                    data = cursor.fetchone()
                elif fetchall:
                    data = cursor.fetchall()
                else:
                    data = None
                return op, data
            except Exception as exc:
                if owns_connection:
                    connection.rollback()
                raise exc
            finally:
                cursor.close()

    def execute_insert(self, query, params=()):
        with self._connection_context() as (connection, owns_connection):
            cursor = connection.cursor()
            try:
                cursor.execute(query, params)
                if owns_connection:
                    connection.commit()
                return cursor.lastrowid
            except Exception as exc:
                if owns_connection:
                    connection.rollback()
                raise exc
            finally:
                cursor.close()

    def executemany(self, query, seq_of_params):
        with self._connection_context() as (connection, owns_connection):
            cursor = connection.cursor()
            try:
                cursor.executemany(query, seq_of_params)
                if owns_connection:
                    connection.commit()
            except Exception as exc:
                if owns_connection:
                    connection.rollback()
                raise exc
            finally:
                cursor.close()

    def execute_script(self, script):
        with self._connection_context() as (connection, owns_connection):
            cursor = connection.cursor()
            try:
                cursor.executescript(script)
                if owns_connection:
                    connection.commit()
            except Exception as exc:
                if owns_connection:
                    connection.rollback()
                raise exc
            finally:
                cursor.close()

    def _init_db(self):
        from ..db_methods.t_questions import QuestionsTable

        self.upload_root.mkdir(parents=True, exist_ok=True)
        self.migrations.rename_legacy_live_exam_tables()
        self.execute_script(SCHEMA_SQL)

        self.integrity.ensure_column("exams", "official_url", "TEXT DEFAULT ''")
        self.integrity.ensure_column("users", "login_name", "TEXT")
        self.integrity.ensure_column("users", "display_name", "TEXT")
        self.integrity.ensure_column("users", "is_protected", "INTEGER NOT NULL DEFAULT 0")
        self.integrity.ensure_column("users", "avatar_path", "TEXT")
        self.integrity.ensure_column("live_exams", "status", "TEXT NOT NULL DEFAULT 'active'")
        self.integrity.ensure_column("live_exams", "closed_at", "TEXT")

        self.migrations.migrate_legacy_live_exam_data()
        self.migrations.migrate_live_exam_status()
        self.migrations.migrate_user_identity_fields()

        _, row = self.execute(
            "SELECT version FROM schema_meta ORDER BY version DESC LIMIT 1",
            fetchone=True,
        )
        current_version = row["version"] if row else 0
        if not row:
            self.execute("INSERT INTO schema_meta (version) VALUES (?)", (SCHEMA_VERSION,))
        elif current_version < SCHEMA_VERSION:
            self.execute("UPDATE schema_meta SET version = ?", (SCHEMA_VERSION,))

        self.seeder.seed_defaults()
        self.integrity.ensure_users_indexes()
        QuestionsTable(self).normalize_all_positions()
        if current_version < 2:
            self.seeder.seed_exam_links()
        if current_version < 4:
            self.migrations.migrate_static_uploads_to_data_assets()
