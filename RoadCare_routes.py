import os
import uuid
import secrets
import sqlite3
from datetime import datetime
from functools import wraps
from io import BytesIO

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app, send_from_directory, session, g, abort
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from PIL import Image, UnidentifiedImageError

from app.database import get_db
from app.severity import estimate_severity
from app.ai_features import find_possible_duplicate, calculate_priority, gps_distance_meters
from app import login_required, role_required

main = Blueprint("main", __name__)
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VALID_STATUSES = {"Reported", "In Progress", "Resolved"}


def _safe_next(value):
    # Only allow local relative paths to prevent open redirects.
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return None


@main.route("/login", methods=["GET", "POST"])
def login():
    if g.get("user") is not None:
        return redirect(url_for("main.dashboard" if g.user["role"] == "authority" else "main.citizen_dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        connection = get_db()
        try:
            user = connection.execute(
                "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
            ).fetchone()
        finally:
            connection.close()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session.permanent = True
            # Regenerate the CSRF token after login.
            session["_csrf_token"] = secrets.token_urlsafe(32)
            flash("Welcome back!")
            target = _safe_next(request.args.get("next"))
            if target and user["role"] == "citizen":
                return redirect(target)
            return redirect(url_for("main.dashboard" if user["role"] == "authority" else "main.citizen_dashboard"))
        flash("Invalid username or password.")
    return render_template("login.html")


@main.route("/register", methods=["GET", "POST"])
def register():
    if g.get("user") is not None:
        return redirect(url_for("main.dashboard" if g.user["role"] == "authority" else "main.citizen_dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not re_username(username):
            flash("Username must be 3–30 characters and contain only letters, numbers, or underscores.")
            return render_template("register.html")
        if len(password) < 8:
            flash("Password must contain at least 8 characters.")
            return render_template("register.html")
        if password != confirm:
            flash("Passwords do not match.")
            return render_template("register.html")
        connection = get_db()
        try:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'citizen', ?)",
                (username, generate_password_hash(password), datetime.now().astimezone().isoformat(timespec="seconds")),
            )
            connection.commit()
            new_user_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            flash("That username is already registered. Please choose another.")
            return render_template("register.html")
        finally:
            connection.close()
        session.clear()
        session["user_id"] = new_user_id
        session.permanent = True
        session["_csrf_token"] = secrets.token_urlsafe(32)
        flash("Your citizen account has been created.")
        return redirect(url_for("main.citizen_dashboard"))
    return render_template("register.html")


def re_username(value):
    return 3 <= len(value) <= 30 and all(ch.isalnum() or ch == "_" for ch in value)


@main.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("main.login"))


@main.route("/")
def home():
    return redirect(url_for("main.login"))


@main.route("/report/new", methods=["GET"])
@role_required("citizen")
def new_report():
    """Display the road damage report form for a logged-in citizen."""
    return render_template("index.html")


@main.route("/citizen/dashboard")
@role_required("citizen")
def citizen_dashboard():
    """Show only reports submitted by the currently logged-in citizen."""
    connection = get_db()
    try:
        reports = connection.execute(
            "SELECT * FROM reports WHERE user_id = ? ORDER BY id DESC",
            (g.user["id"],),
        ).fetchall()
        stats = {
            "total": len(reports),
            "reported": sum(row["status"] == "Reported" for row in reports),
            "progress": sum(row["status"] == "In Progress" for row in reports),
            "resolved": sum(row["status"] == "Resolved" for row in reports),
        }
    finally:
        connection.close()

    return render_template(
        "citizen_dashboard.html",
        reports=reports,
        stats=stats,
    )


@main.route("/health")
def health():
    return {"status": "ok", "project": "RoadCare"}


@main.route("/report", methods=["POST"])
@role_required("citizen")
def submit_report():
    photo = request.files.get("photo")
    latitude_text = request.form.get("latitude", "").strip()
    longitude_text = request.form.get("longitude", "").strip()
    notes = request.form.get("notes", "").strip()[:500]
    if not photo or not photo.filename:
        flash("Please select a road damage photo.")
        return redirect(url_for("main.new_report"))
    try:
        latitude, longitude = float(latitude_text), float(longitude_text)
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError
    except (ValueError, TypeError):
        flash("Enter valid latitude and longitude coordinates.")
        return redirect(url_for("main.new_report"))
    extension = os.path.splitext(secure_filename(photo.filename))[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        flash("Use a JPG, JPEG, PNG, or WEBP image.")
        return redirect(url_for("main.new_report"))
    try:
        image_bytes = photo.read()
        if not image_bytes:
            raise ValueError("Empty image")
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        flash("The uploaded file is not a valid image.")
        return redirect(url_for("main.new_report"))

    filename = f"{uuid.uuid4().hex}{extension}"
    upload_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    report_id = "RC-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3).upper()
    severity = estimate_severity(notes)
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    duplicate = None
    duplicate_distance = None
    priority_score = 0
    connection = get_db()
    try:
        existing = connection.execute(
            "SELECT report_id, latitude, longitude, status FROM reports WHERE status != 'Resolved'"
        ).fetchall()
        duplicate, duplicate_distance = find_possible_duplicate(latitude, longitude, existing, radius_meters=50)
        nearby_unresolved = sum(
            1 for item in existing if gps_distance_meters(latitude, longitude, item["latitude"], item["longitude"]) <= 100
        )
        priority_score = calculate_priority(severity, created_at, nearby_unresolved)
        with open(upload_path, "wb") as image_file:
            image_file.write(image_bytes)
        connection.execute(
            """INSERT INTO reports
            (report_id, image_filename, latitude, longitude, notes, severity, status, created_at, is_duplicate, duplicate_of, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (report_id, filename, latitude, longitude, notes, severity, "Reported", created_at,
             1 if duplicate else 0, duplicate["report_id"] if duplicate else None, g.user["id"]),
        )
        connection.commit()
    except (OSError, sqlite3.Error):
        if os.path.exists(upload_path):
            os.remove(upload_path)
        current_app.logger.exception("Could not save road report")
        flash("The report could not be saved. Please try again.")
        return redirect(url_for("main.new_report"))
    finally:
        connection.close()

    return render_template(
        "success.html", report_id=report_id, severity=severity,
        is_duplicate=bool(duplicate), duplicate_of=duplicate["report_id"] if duplicate else None,
        duplicate_distance=round(duplicate_distance) if duplicate_distance is not None else None,
        priority_score=priority_score,
    )


@main.route("/uploads/<path:filename>")
@login_required
def uploaded_image(filename):
    connection = get_db()
    try:
        report = connection.execute(
            "SELECT user_id FROM reports WHERE image_filename = ?", (filename,)
        ).fetchone()
    finally:
        connection.close()
    if report is None:
        abort(404)
    if g.user["role"] != "authority" and report["user_id"] != g.user["id"]:
        abort(403)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@main.route("/track", methods=["GET", "POST"])
@login_required
def track():
    report = None
    searched = False
    if request.method == "POST":
        searched = True
        report_id = request.form.get("report_id", "").strip()
        if report_id:
            connection = get_db()
            try:
                if g.user["role"] == "authority":
                    report = connection.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
                else:
                    report = connection.execute(
                        "SELECT * FROM reports WHERE report_id = ? AND user_id = ?", (report_id, g.user["id"])
                    ).fetchone()
            finally:
                connection.close()
        if not report:
            flash("No report found for your account. Check the report ID and try again.")
    return render_template("track.html", report=report, searched=searched)


@main.route("/dashboard")
@role_required("authority")
def dashboard():
    connection = get_db()
    try:
        raw = [dict(row) for row in connection.execute("SELECT * FROM reports ORDER BY id DESC").fetchall()]
        reports = []
        for report in raw:
            nearby = sum(
                1 for other in raw if other["report_id"] != report["report_id"] and other["status"] != "Resolved"
                and gps_distance_meters(report["latitude"], report["longitude"], other["latitude"], other["longitude"]) <= 100
            )
            report["nearby_unresolved"] = nearby
            report["priority_score"] = calculate_priority(report["severity"], report["created_at"], nearby)
            reports.append(report)
        reports.sort(key=lambda item: (item["priority_score"], item["id"]), reverse=True)
        stats = {
            "total": len(reports),
            "high": sum(r["severity"] == "High" for r in reports),
            "reported": sum(r["status"] == "Reported" for r in reports),
            "progress": sum(r["status"] == "In Progress" for r in reports),
            "resolved": sum(r["status"] == "Resolved" for r in reports),
            "duplicates": sum(bool(r.get("is_duplicate")) for r in reports),
        }
    finally:
        connection.close()
    return render_template("dashboard.html", reports=reports, stats=stats)


@main.route("/dashboard/status/<report_id>", methods=["POST"])
@role_required("authority")
def update_status(report_id):
    status = request.form.get("status", "")
    if status not in VALID_STATUSES:
        flash("Invalid report status.")
        return redirect(url_for("main.dashboard"))
    connection = get_db()
    try:
        cursor = connection.execute("UPDATE reports SET status = ? WHERE report_id = ?", (status, report_id))
        connection.commit()
        flash(f"Report {report_id} status updated." if cursor.rowcount else "Report not found.")
    finally:
        connection.close()
    return redirect(url_for("main.dashboard"))
