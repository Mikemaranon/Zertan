# db_connector.py

import sqlite3

from support_m import get_runtime_config


class DBConnector:
    def __init__(self, db_path=None):
        self.db_path = db_path or get_runtime_config()["db_path"]

    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def close(self, conn):
        if conn:
            conn.close()
