import os
import sqlite3
from flask import current_app


def get_db():
    connection = sqlite3.connect(current_app.config["DATABASE"], timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(app):
    os.makedirs(app.instance_path, exist_ok=True)
    app.config["DATABASE"] = os.path.join(app.instance_path, "roadcare.db")

    with app.app_context():
        connection = get_db()
        try:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('citizen', 'authority')),
                    created_at TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id TEXT UNIQUE NOT NULL,
                    image_filename TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    notes TEXT DEFAULT '',
                    severity TEXT NOT NULL DEFAULT 'Medium',
                    status TEXT NOT NULL DEFAULT 'Reported',
                    created_at TEXT NOT NULL
                )
            """)

            report_columns = {row["name"] for row in connection.execute("PRAGMA table_info(reports)")}
            migrations = {
                "is_duplicate": "ALTER TABLE reports ADD COLUMN is_duplicate INTEGER NOT NULL DEFAULT 0",
                "duplicate_of": "ALTER TABLE reports ADD COLUMN duplicate_of TEXT",
                "user_id": "ALTER TABLE reports ADD COLUMN user_id INTEGER REFERENCES users(id)",
            }
            for column, statement in migrations.items():
                if column not in report_columns:
                    connection.execute(statement)

            connection.execute("CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports(user_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)")
            connection.commit()
        finally:
            connection.close()
