ROADCARE — ROLE-BASED LOGIN UPDATE

WHAT THIS UPDATE ADDS
- Citizen self-registration (new accounts are always citizen role).
- Secure password hashing (Werkzeug).
- Login and logout using Flask sessions.
- Authority-only dashboard and report status updates.
- Citizen-only report submission and owner-only report tracking.
- Database migrations add users, reports.user_id, is_duplicate, duplicate_of.
- Existing RoadCare form styling, Leaflet map, and report dashboard layout are retained.
- GPS duplicate warning and rule-based priority score remain in place.

PROJECT PATHS
Copy the contents of this package into your existing C:\RoadCare folder. The app folder should be C:\RoadCare\app.
Replace matching files and add the new files. Keep your existing app/severity.py if it is your current version; this package includes the copy retrieved from your saved project.

INSTALL / RUN (Windows CMD)
1. Open terminal in C:\RoadCare
2. Activate your existing virtual environment if you use one:
   .venv\Scripts\activate
3. Install dependencies:
   py -m pip install -r requirements.txt
4. Create the first authority account (interactive; no default password):
   py create_authority.py
5. Start the app:
   py run.py
6. Open http://127.0.0.1:5000/login

FIRST USE
- Create citizen accounts from the Register link. Public registration cannot create authority accounts.
- Create authority accounts only by running create_authority.py on the trusted project machine.
- Authority login redirects to /dashboard. Citizen login redirects to /.

DATABASE
The app uses app/instance/roadcare.db. Existing reports are retained. Their user_id stays NULL because older reports were not associated with an account; they remain visible to authority users only. New reports are linked to the logged-in citizen. Back up your database and uploads before replacing files.

SECURITY NOTES
- Set ROADCARE_SECRET_KEY to a long random secret before deployment. The built-in fallback is only for local development.
- On HTTPS hosting set ROADCARE_COOKIE_SECURE=1.
- Do not commit instance/, uploads/, .env, or credentials.
- This is a student prototype. For public production deployment, use persistent database and image storage and review rate limiting, account recovery, and security configuration.

FEATURE LIMITATIONS
Duplicate detection is GPS-proximity based, not photo identity matching. Priority score is an explainable rule-based heuristic, not an AI model.


CITIZEN DASHBOARD UPDATE
- Citizens are redirected to /citizen/dashboard after login and registration.
- The dashboard lists only reports whose reports.user_id matches the logged-in citizen.
- Citizens can still open the report form separately using Submit New Report.
- Older reports created before citizen ownership was enabled may have user_id=NULL.
  They are intentionally not shown to any citizen because ownership cannot be verified.
- The authority dashboard remains at /dashboard and continues to show all reports.
