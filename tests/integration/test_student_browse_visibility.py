"""Integration tests: which listings a student sees when browsing.

Uses TestClient against the real endpoints (/api/auth/login,
/api/landlord/listings, /api/listings/{id}/transition, /api/student/listings)
and reuses the helpers from test_listing_transitions.py.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.models.listing import Listing
from app.utilities.security import encrypt_password

from test_listing_transitions import (
    _create_test_database,
    _create_user,
    _listing_payload,
)

STUDENT_EMAIL = "browse_student@example.com"
STUDENT_PASSWORD = "stud-dev"

# status -> steps (actor, action, reason) that take a new pending listing there
PATHS = {
    "pending": [],
    "provisionally_accepted": [("admin", "provisionally_accept", None)],
    "verified": [("admin", "verify", None)],
    "active": [("admin", "verify", None), ("landlord", "activate", None)],
    "inactive": [
        ("admin", "verify", None),
        ("landlord", "activate", None),
        ("landlord", "deactivate", None),
    ],
    "rejected": [("admin", "reject", "missing documents")],
    "suspended": [("admin", "verify", None), ("admin", "suspend", None)],
}


def _title(status: str) -> str:
    return f"{status} listing"


def _setup(monkeypatch):
    """Empty test database with an admin, a landlord and a student who logs in."""
    engine = _create_test_database(monkeypatch)

    with Session(engine) as session:
        admin = _create_user(session, username="browse_admin", role="admin")
        landlord = _create_user(session, username="browse_landlord", role="landlord")
        student = _create_user(session, username="browse_student", role="student")
        student.password = encrypt_password(STUDENT_PASSWORD)
        student.student_id = "202012345"
        session.add(student)
        session.commit()
        ids = {"admin": admin.id, "landlord": landlord.id}

    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={"email": STUDENT_EMAIL, "password": STUDENT_PASSWORD},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "student"
    student_headers = {"X-User-Id": str(login.json()["user"]["id"])}

    return engine, client, ids, student_headers


def _transition(client, ids, listing_id, actor, action, reason=None):
    response = client.post(
        f"/api/listings/{listing_id}/transition",
        headers={"X-User-Id": str(ids[actor])},
        json={"action": action, "reason": reason},
    )
    assert response.status_code == 200, response.text
    return response


def _create_listing_in_status(client, ids, status):
    submitted = client.post(
        "/api/landlord/listings",
        headers={"X-User-Id": str(ids["landlord"])},
        json={**_listing_payload(), "title": _title(status)},
    )
    assert submitted.status_code == 200, submitted.text
    listing_id = submitted.json()["listing"]["id"]

    for actor, action, reason in PATHS[status]:
        _transition(client, ids, listing_id, actor, action, reason)

    return listing_id


def _browse_titles(client, student_headers):
    response = client.get("/api/student/listings", headers=student_headers)
    assert response.status_code == 200, response.text
    return [item["title"] for item in response.json()["listings"]]


def test_student_browse_shows_only_the_active_listing(monkeypatch):
    engine, client, ids, student_headers = _setup(monkeypatch)

    listing_ids = {
        status: _create_listing_in_status(client, ids, status) for status in PATHS
    }

    # Make sure every listing really is in the status this test claims.
    with Session(engine) as session:
        for status, listing_id in listing_ids.items():
            assert session.get(Listing, listing_id).status == status

    titles = _browse_titles(client, student_headers)

    assert _title("active") in titles
    for status in PATHS:
        if status != "active":
            assert _title(status) not in titles, f"{status} listing is visible"
    assert titles == [_title("active")]


def test_listing_disappears_from_browse_when_deactivated(monkeypatch):
    engine, client, ids, student_headers = _setup(monkeypatch)
    listing_id = _create_listing_in_status(client, ids, "active")

    assert _browse_titles(client, student_headers) == [_title("active")]

    response = _transition(client, ids, listing_id, "landlord", "deactivate")

    assert response.json()["listing"]["status"] == "inactive"
    assert _browse_titles(client, student_headers) == []
