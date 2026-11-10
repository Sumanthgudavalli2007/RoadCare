import os
import secrets
from datetime import timedelta
from functools import wraps

from flask import Flask, abort, flash, g, redirect, request, session, url_for
from app.database import get_db, init_db


def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("ROADCARE_SECRET_KEY", "local-development-only-change-this-key"),
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        UPLOAD_FOLDER=os.path.abspath(os.path.join(app.root_path, "..", "uploads")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("ROADCARE_COOKIE_SECURE", "0") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    )
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    init_db(app)

    @app.before_request
    def load_user_and_check_csrf():
        g.user = None
        user_id = session.get("user_id")
        if user_id is not None:
            connection = get_db()
            try:
                g.user = connection.execute(
                    "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
                ).fetchone()
            finally:
                connection.close()
            if g.user is None:
                session.clear()

        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token

        if request.method == "POST":
            submitted = request.form.get("csrf_token", "")
            if not submitted or not secrets.compare_digest(token, submitted):
                abort(400, description="Invalid or missing security token. Refresh the page and try again.")

    @app.context_processor
    def inject_template_helpers():
        return {"current_user": g.get("user"), "csrf_token": lambda: session.get("_csrf_token", "")}

    from app.routes import main
    app.register_blueprint(main)
    return app


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            flash("Please log in to continue.")
            return redirect(url_for("main.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.get("user") is None:
                flash("Please log in to continue.")
                return redirect(url_for("main.login"))
            if g.user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator
