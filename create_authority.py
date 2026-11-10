from getpass import getpass
from datetime import datetime
import sqlite3

from werkzeug.security import generate_password_hash
from app import create_app
from app.database import get_db

app = create_app()

with app.app_context():
    username = input("Authority username: ").strip()
    password = getpass("Authority password (minimum 8 characters): ")
    confirm = getpass("Confirm password: ")
    if not (3 <= len(username) <= 30) or not all(c.isalnum() or c == "_" for c in username):
        raise SystemExit("Username must be 3–30 letters, numbers, or underscores.")
    if len(password) < 8 or password != confirm:
        raise SystemExit("Passwords must match and contain at least 8 characters.")
    connection = get_db()
    try:
        connection.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'authority', ?)",
            (username, generate_password_hash(password), datetime.now().astimezone().isoformat(timespec="seconds")),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        raise SystemExit("That username already exists. Choose another username.")
    finally:
        connection.close()
    print("Authority account created successfully. Keep the credentials private.")
