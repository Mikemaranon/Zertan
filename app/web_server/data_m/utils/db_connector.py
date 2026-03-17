# db_connector.py

import sqlite3
from pathlib import Path


DB_FILENAME = "zertan.db"


class DBConnector:
    def __init__(self):
        self.db_path = Path(__file__).resolve().parent / DB_FILENAME

    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def close(self, conn):
        if conn:
            conn.close()
