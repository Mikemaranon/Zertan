# integrity.py


class DatabaseIntegrityManager:
    def __init__(self, db):
        self.db = db

    def ensure_column(self, table, column_name, definition):
        existing_columns = set(self.table_columns(table))
        if column_name not in existing_columns:
            self.db.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {definition}")

    def table_exists(self, table_name):
        _, row = self.db.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (table_name,),
            fetchone=True,
        )
        return bool(row)

    def table_columns(self, table_name):
        if not self.table_exists(table_name):
            return []
        _, rows = self.db.execute(f"PRAGMA table_info({table_name})", fetchall=True)
        return [row["name"] for row in rows]

    def ensure_users_indexes(self):
        self.db.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_login_name_unique
            ON users (lower(login_name))
            """
        )
