-- CrewOps database schema (SQLite), simplified
-- Run with:   sqlite3 app.db < schema.sql
-- Times are TEXT in UTC ISO-8601, e.g. '2026-11-07T06:00:00Z'.
-- shiftDate is the airport's local date, e.g. '2026-11-07'.
-- True/false values are INTEGER 0 or 1.
-- Any column ending in "userID" points to users.id, not the 9-digit employee_id.

DROP TABLE IF EXISTS airports;
DROP TABLE IF EXISTS teams;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS skills;
DROP TABLE IF EXISTS userSkills;
DROP TABLE IF EXISTS shifts;
DROP TABLE IF EXISTS shiftAssignments;
DROP TABLE IF EXISTS flights;
DROP TABLE IF EXISTS absenceReports;
DROP TABLE IF EXISTS reassignmentRequests;
DROP TABLE IF EXISTS notifications;

CREATE TABLE airports (
    airportCode TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    timezone    TEXT NOT NULL
);

CREATE TABLE teams (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    airportCode TEXT NOT NULL REFERENCES airports(airportCode),
    name        TEXT NOT NULL,
    UNIQUE (airportCode, name)
);

CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    airportCode TEXT NOT NULL REFERENCES airports(airportCode),
    employee_id  INTEGER NOT NULL,
    password    TEXT NOT NULL,
    role        TEXT NOT NULL,
    isAdmin     INTEGER NOT NULL DEFAULT 0,
    firstName   TEXT NOT NULL,
    lastName    TEXT NOT NULL,
    teamID      INTEGER REFERENCES teams(id),
    isActive    INTEGER NOT NULL DEFAULT 1,
    createdAt   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (airportCode, employee_id)
);

CREATE TABLE skills (
    name TEXT PRIMARY KEY
);

CREATE TABLE userSkills (
    userID INTEGER NOT NULL REFERENCES users(id),
    skill  TEXT NOT NULL REFERENCES skills(name),
    PRIMARY KEY (userID, skill)
);

CREATE TABLE shifts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    airportCode TEXT NOT NULL REFERENCES airports(airportCode),
    teamID      INTEGER NOT NULL REFERENCES teams(id),
    shiftDate   TEXT NOT NULL,
    startTime   TEXT NOT NULL,
    endTime     TEXT NOT NULL
);

CREATE TABLE shiftAssignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    shiftID         INTEGER NOT NULL REFERENCES shifts(id),
    userID          INTEGER NOT NULL REFERENCES users(id),
    coveringSkill   TEXT REFERENCES skills(name),
    status          TEXT NOT NULL DEFAULT 'ready',   -- ready, delayed, sick
    expectedArrival TEXT,
    UNIQUE (shiftID, userID)
);

CREATE TABLE flights (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    airportCode        TEXT NOT NULL REFERENCES airports(airportCode),
    teamID             INTEGER REFERENCES teams(id),
    flightNumber       TEXT NOT NULL,
    airline            TEXT NOT NULL,
    origin             TEXT NOT NULL,
    scheduledArrival   TEXT NOT NULL,
    scheduledDeparture TEXT NOT NULL,
    stand              TEXT,
    status             TEXT NOT NULL DEFAULT 'on_time'  -- on_time, delayed, arrived, departed, cancelled
);

CREATE TABLE absenceReports (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    shiftAssignmentID INTEGER NOT NULL UNIQUE REFERENCES shiftAssignments(id),
    reportedAt        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE reassignmentRequests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    absenceReportID INTEGER NOT NULL REFERENCES absenceReports(id),
    proposedUserID  INTEGER REFERENCES users(id),
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending, approved, rejected
    decidedBy       INTEGER REFERENCES users(id),
    decidedAt       TEXT,
    createdAt       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE notifications (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    userID    INTEGER NOT NULL REFERENCES users(id),
    message   TEXT NOT NULL,
    isRead    INTEGER NOT NULL DEFAULT 0,
    createdAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO skills (name) VALUES ('Tug'), ('Belt loader'), ('Baggage'), ('Steps');