import sqlite3
from flask import Flask, render_template, session, redirect, url_for, g, request
from database import get_db, close_db
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from forms import RegistrationForm, LoginForm
from functools import wraps
from airgroundcrewsys import *


app = Flask(__name__)
app.teardown_appcontext(close_db)
app.config["SECRET_KEY"] = "6062-corkathon"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


@app.before_request
def load_logged_in_user():
    g.user = session.get("id", None)
    g.isAdmin = session.get("isAdmin", None)

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped_view

def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.isAdmin != 1:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


# Shared by login and register: replaces any old session with one for this account
def start_session(account):
    session.clear()
    session["id"] = account["id"]
    session["airport_code"] = account["airportCode"]
    session["employee_id"] = account["employee_id"]
    session["isAdmin"] = account["isAdmin"]


def redirect_for_role():
    return redirect(url_for("supervisor" if session["isAdmin"] else "employee_flights"))


def is_safe_next(target):
    return bool(target) and target.startswith("/") and not target.startswith(("//", "/\\"))


@app.route('/')
def home():
    return render_template("home.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        account = get_db().execute("""SELECT * FROM users
                    WHERE airportCode = ? AND employee_id = ? AND isActive = 1;""",
                    (form.airport_code.data, form.employee_id.data)).fetchone()

        # One message for both failures so the form doesn't reveal which IDs exist
        if account is None or not check_password_hash(account["password"], form.password.data):
            form.password.errors.append("Incorrect airport code, employee ID or password")
        else:
            start_session(account)
            next_page = request.args.get("next")
            if is_safe_next(next_page):
                return redirect(next_page)
            return redirect_for_role()

    return render_template("login.html", form=form)


# Route allows user to log out which clearing session data
@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


# Route allows user to register an account
@app.route("/register", methods=["GET","POST"])
def register():

    form = RegistrationForm()

    if form.validate_on_submit():
        employee_id = form.employee_id.data
        db = get_db()

        airport = db.execute("SELECT 1 FROM airports WHERE airportCode = ?;",
                             (form.airport_code.data,)).fetchone()

        if airport is None:
            form.airport_code.errors.append("Unknown airport code")
        else:
            #schema requires supervisors to have an ID ending in 400
            is_admin = employee_id % 1000 == 400
            try:
                cursor = db.execute("""INSERT INTO users (airportCode, employee_id, password, role, isAdmin, firstName, lastName)
                           VALUES (?,?,?,?,?,?,?);""",
                           (form.airport_code.data, employee_id, generate_password_hash(form.password.data),
                            "supervisor" if is_admin else "ramp_agent", int(is_admin),
                            form.f_name.data, form.s_name.data))
            except sqlite3.IntegrityError:
                form.employee_id.errors.append("employee_id already exists at this airport")
            else:
                db.commit()
                start_session(db.execute("SELECT * FROM users WHERE id = ?;", (cursor.lastrowid,)).fetchone())
                return redirect_for_role()

    return render_template("register.html", form=form)

@app.route('/employee_flights')
@login_required
def employee_flights():
    # Imported here so this route is self-contained
    from datetime import datetime, time, timedelta, timezone
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ? AND isActive = 1;", (g.user,)).fetchone()
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    # "Today" means today at the user's airport, but the database stores UTC
    airport = db.execute("SELECT * FROM airports WHERE airportCode = ?;", (user["airportCode"],)).fetchone()
    try:
        tz = ZoneInfo(airport["timezone"] if airport else "UTC")
    except ZoneInfoNotFoundError:
        tz = timezone.utc   #pip install tzdata done

    fmt = "%Y-%m-%dT%H:%M:%SZ"
    now = datetime.now(timezone.utc)
    local_midnight = datetime.combine(now.astimezone(tz).date(), time.min, tzinfo=tz)
    today = local_midnight.date().isoformat()
    day_start = local_midnight.astimezone(timezone.utc).strftime(fmt)
    day_end = (local_midnight + timedelta(days=1)).astimezone(timezone.utc).strftime(fmt)

    def local_hhmm(utc_text):
        parsed = datetime.fromisoformat(utc_text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(tz).strftime("%H:%M")

    # Flight rows with the times shown in the airport's local time
    def display(row):
        flight = dict(row)
        flight["scheduledArrival"] = local_hhmm(row["scheduledArrival"])
        flight["scheduledDeparture"] = local_hhmm(row["scheduledDeparture"])
        return flight

    #user's team, shift today, each member's skills and status
    team = {"name": "No team assigned", "members": []}
    shift = None
    if user["teamID"] is not None:
        team_row = db.execute("SELECT * FROM teams WHERE id = ?;", (user["teamID"],)).fetchone()
        if team_row is not None:
            team = dict(team_row)
            team["members"] = []

        shift = db.execute("""SELECT * FROM shifts
                           WHERE teamID = ? AND shiftDate = ?
                           ORDER BY startTime LIMIT 1;""", (user["teamID"], today)).fetchone()

        skills = {}
        for row in db.execute("""SELECT userSkills.userID, userSkills.skill
                              FROM userSkills JOIN users ON users.id = userSkills.userID
                              WHERE users.teamID = ?
                              ORDER BY userSkills.skill;""", (user["teamID"],)):
            skills.setdefault(row["userID"], []).append(row["skill"])

        members = db.execute("""SELECT users.id, users.firstName, users.lastName, users.role,
                             COALESCE(shiftAssignments.status, 'ready') AS status
                             FROM users
                             LEFT JOIN shiftAssignments ON shiftAssignments.userID = users.id
                                                       AND shiftAssignments.shiftID = ?
                             WHERE users.teamID = ? AND users.isActive = 1
                             ORDER BY users.lastName, users.firstName;""",
                             (shift["id"] if shift else None, user["teamID"])).fetchall()
        team["members"] = [{"name": m["firstName"] + " " + m["lastName"],
                            "role": m["role"],
                            "status": m["status"],
                            "skills": skills.get(m["id"], [])} for m in members]

    # Everyone on shift at airport today
    roster = [{"name": r["firstName"] + " " + r["lastName"], "role": r["role"], "status": r["status"]}
              for r in db.execute("""SELECT users.firstName, users.lastName, users.role, shiftAssignments.status
                                  FROM shiftAssignments
                                  JOIN shifts ON shifts.id = shiftAssignments.shiftID
                                  JOIN users ON users.id = shiftAssignments.userID
                                  WHERE shifts.airportCode = ? AND shifts.shiftDate = ?
                                  ORDER BY users.lastName, users.firstName;""",
                                  (user["airportCode"], today))]
    roster_sick = sum(1 for person in roster if person["status"] == "sick")

    # flights arriving today
    my_rows = []
    if user["teamID"] is not None:
        my_rows = db.execute("""SELECT * FROM flights
                             WHERE airportCode = ? AND teamID = ?
                             AND scheduledArrival >= ? AND scheduledArrival < ?
                             ORDER BY scheduledArrival;""",
                             (user["airportCode"], user["teamID"], day_start, day_end)).fetchall()
    all_rows = db.execute("""SELECT flights.*, teams.name AS team_name
                          FROM flights LEFT JOIN teams ON teams.id = flights.teamID
                          WHERE flights.airportCode = ?
                          AND flights.scheduledArrival >= ? AND flights.scheduledArrival < ?
                          ORDER BY flights.scheduledArrival;""",
                          (user["airportCode"], day_start, day_end)).fetchall()

    # next flight still to leave: the team's, or the airport's if the user has no team
    now_text = now.strftime(fmt)
    candidates = my_rows if user["teamID"] is not None else all_rows
    next_row = next((f for f in candidates
                     if f["scheduledDeparture"] >= now_text
                     and f["status"] not in ("departed", "cancelled")), None)

    return render_template('employee_flights.html',
                           user=user,
                           team=team,
                           shift_start=local_hhmm(shift["startTime"]) if shift else None,
                           shift_end=local_hhmm(shift["endTime"]) if shift else None,
                           next_flight=display(next_row) if next_row else None,
                           roster=roster,
                           roster_total=len(roster),
                           roster_available=len(roster) - roster_sick,
                           roster_sick=roster_sick,
                           team_ready=sum(1 for m in team["members"] if m["status"] == "ready"),
                           team_size=len(team["members"]),
                           my_flights=[display(f) for f in my_rows],
                           all_flights=[display(f) for f in all_rows])

@app.route('/supervisor')
@login_required
@admin_required
def supervisor():
    # imported here so this route is self-contained
    from datetime import datetime, time, timedelta, timezone
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    db = get_db()
    employee = db.execute("SELECT * FROM users WHERE id = ? AND isActive = 1 AND isAdmin = 1;", (g.user,)).fetchone()
    if employee is None:
        session.clear()
        return redirect(url_for("login"))

    # "today" means today at the supervisor's airport, database stores UTC
    airport = db.execute("SELECT * FROM airports WHERE airportCode = ?;", (employee["airportCode"],)).fetchone()
    try:
        tz = ZoneInfo(airport["timezone"] if airport else "UTC")
    except ZoneInfoNotFoundError:
        tz = timezone.utc 

    fmt = "%Y-%m-%dT%H:%M:%SZ"
    now = datetime.now(timezone.utc)
    local_midnight = datetime.combine(now.astimezone(tz).date(), time.min, tzinfo=tz)
    today = local_midnight.date().isoformat()
    day_start = local_midnight.astimezone(timezone.utc).strftime(fmt)
    day_end = (local_midnight + timedelta(days=1)).astimezone(timezone.utc).strftime(fmt)

    def local_hhmm(utc_text):
        parsed = datetime.fromisoformat(utc_text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(tz).strftime("%H:%M")

    # earliest shift start to latest shift end across all teams today, and how many teams are on duty
    span = db.execute("""SELECT MIN(startTime) AS first, MAX(endTime) AS last, COUNT(DISTINCT teamID) AS teams
                      FROM shifts WHERE airportCode = ? AND shiftDate = ?;""",
                      (employee["airportCode"], today)).fetchone()

    # flights arriving today, with team handling each
    flight_rows = db.execute("""SELECT flights.*, teams.name AS team_name
                             FROM flights LEFT JOIN teams ON teams.id = flights.teamID
                             WHERE flights.airportCode = ?
                             AND flights.scheduledArrival >= ? AND flights.scheduledArrival < ?
                             ORDER BY flights.scheduledArrival;""",
                             (employee["airportCode"], day_start, day_end)).fetchall()
    flights = []
    for row in flight_rows:
        flight = dict(row)
        flight["scheduledArrival"] = local_hhmm(row["scheduledArrival"])
        flight["scheduledDeparture"] = local_hhmm(row["scheduledDeparture"])
        flights.append(flight)

    # active staff with no team (supervisors and managers never have one), with their skills
    skills = {}
    for row in db.execute("""SELECT userSkills.userID, userSkills.skill
                          FROM userSkills JOIN users ON users.id = userSkills.userID
                          WHERE users.airportCode = ? AND users.teamID IS NULL
                          ORDER BY userSkills.skill;""", (employee["airportCode"],)):
        skills.setdefault(row["userID"], []).append(row["skill"])
    unassigned_staff = [{"name": r["firstName"] + " " + r["lastName"],
                         "role": r["role"],
                         "employee_id": r["employee_id"],
                         "skills": skills.get(r["id"], [])}
                        for r in db.execute("""SELECT id, firstName, lastName, role, employee_id
                                            FROM users
                                            WHERE airportCode = ? AND isActive = 1
                                            AND teamID IS NULL AND role NOT IN ('supervisor', 'manager')
                                            ORDER BY lastName, firstName;""",
                                            (employee["airportCode"],))]

    # everyone on shift at this airport today
    roster = [{"name": r["firstName"] + " " + r["lastName"], "role": r["role"], "status": r["status"]}
              for r in db.execute("""SELECT users.firstName, users.lastName, users.role, shiftAssignments.status
                                  FROM shiftAssignments
                                  JOIN shifts ON shifts.id = shiftAssignments.shiftID
                                  JOIN users ON users.id = shiftAssignments.userID
                                  WHERE shifts.airportCode = ? AND shifts.shiftDate = ?
                                  ORDER BY users.lastName, users.firstName;""",
                                  (employee["airportCode"], today))]
    roster_sick = sum(1 for person in roster if person["status"] == "sick")

    return render_template('supervisor.html',
                           employee=employee,
                           shift_start=local_hhmm(span["first"]) if span["first"] else None,
                           shift_end=local_hhmm(span["last"]) if span["last"] else None,
                           flights=flights,
                           flights_total=len(flights),
                           teams_total=span["teams"],
                           unassigned_total=sum(1 for f in flight_rows if f["teamID"] is None),
                           delays_total=sum(1 for f in flight_rows if f["status"] == "delayed"),
                           unassigned_staff=unassigned_staff,
                           roster=roster,
                           roster_total=len(roster),
                           roster_available=len(roster) - roster_sick,
                           roster_sick=roster_sick)
