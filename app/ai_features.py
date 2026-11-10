from datetime import datetime, timezone
from math import radians, sin, cos, asin, sqrt


def gps_distance_meters(lat1, lon1, lat2, lon2):
    """Return approximate great-circle distance between two GPS points."""
    earth_radius_m = 6_371_000
    dlat = radians(float(lat2) - float(lat1))
    dlon = radians(float(lon2) - float(lon1))
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(float(lat1)))
        * cos(radians(float(lat2)))
        * sin(dlon / 2) ** 2
    )
    return 2 * earth_radius_m * asin(sqrt(min(1.0, a)))


def find_possible_duplicate(latitude, longitude, existing_reports, radius_meters=50):
    """
    Find the closest unresolved report within the radius.
    This is a location-based warning, not proof that two reports are identical.
    """
    closest = None
    closest_distance = None

    for report in existing_reports:
        if report["status"] == "Resolved":
            continue

        distance = gps_distance_meters(
            latitude, longitude, report["latitude"], report["longitude"]
        )
        if distance <= radius_meters and (
            closest_distance is None or distance < closest_distance
        ):
            closest = report
            closest_distance = distance

    return closest, closest_distance


def _parse_datetime(value):
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def calculate_priority(severity, created_at, nearby_unresolved=0, now=None):
    """
    Explainable rule-based score from 0 to 100.
    Severity contributes most; age and nearby unresolved reports add points.
    This is a heuristic, not an AI prediction.
    """
    severity_points = {"High": 50, "Medium": 30, "Low": 10}
    score = severity_points.get(str(severity).title(), 30)

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age_days = max(0, (now.astimezone(timezone.utc) - _parse_datetime(created_at)).total_seconds() / 86400)

    # Up to 25 points for report age: 1 point per day, capped at 25.
    score += min(25, int(age_days))

    # Up to 15 points for other unresolved reports within 100 metres.
    score += min(15, max(0, int(nearby_unresolved)) * 5)

    return max(0, min(100, int(score)))
