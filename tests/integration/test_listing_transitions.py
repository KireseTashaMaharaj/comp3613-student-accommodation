from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

import app.models
from app.main import app
from app.models.listing import Listing
from app.models.user import User
from app.services import housing_auth, listings


def _create_test_database(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(listings, "engine", engine)
    monkeypatch.setattr(housing_auth, "engine", engine)
    return engine


def _create_user(session: Session, *, username: str, role: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password="test-password",
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _listing_payload() -> dict:
    return {
        "title": "Test Flat",
        "area": "st_augustine",
        "price": 3500,
        "amenities": "wifi,parking",
        "contact_phone": "555-0100",
        "contact_email": "landlord@example.com",
        "photos": "photo1.jpg",
    }


def test_landlord_submits_and_admin_approves_listing(monkeypatch):
    engine = _create_test_database(monkeypatch)

    with Session(engine) as session:
        landlord = _create_user(session, username="landlord", role="landlord")
        admin = _create_user(session, username="admin", role="admin")
        landlord_id = landlord.id
        admin_id = admin.id

    client = TestClient(app)
    submitted = client.post(
        "/api/landlord/listings",
        headers={"X-User-Id": str(landlord_id)},
        json=_listing_payload(),
    )

    assert submitted.status_code == 200
    listing_id = submitted.json()["listing"]["id"]
    assert submitted.json()["listing"]["status"] == "pending"

    approved = client.post(
        f"/api/listings/{listing_id}/transition",
        headers={"X-User-Id": str(admin_id)},
        json={"action": "verify"},
    )

    assert approved.status_code == 200
    assert approved.json()["listing"]["status"] == "verified"

    with Session(engine) as session:
        saved = session.get(Listing, listing_id)
        assert saved is not None
        assert saved.status == "verified"


def test_pending_listing_cannot_transition_directly_to_active(monkeypatch):
    engine = _create_test_database(monkeypatch)

    with Session(engine) as session:
        landlord = _create_user(session, username="landlord", role="landlord")
        landlord_id = landlord.id

    client = TestClient(app)
    submitted = client.post(
        "/api/landlord/listings",
        headers={"X-User-Id": str(landlord_id)},
        json=_listing_payload(),
    )

    assert submitted.status_code == 200
    listing_id = submitted.json()["listing"]["id"]

    response = client.post(
        f"/api/listings/{listing_id}/transition",
        headers={"X-User-Id": str(landlord_id)},
        json={"action": "activate"},
    )

    assert response.status_code == 400
    assert "cannot activate" in response.json()["detail"]

    with Session(engine) as session:
        saved = session.get(Listing, listing_id)
        assert saved is not None
        assert saved.status == "pending"


def test_landlord_cannot_transition_another_landlords_listing(monkeypatch):
    engine = _create_test_database(monkeypatch)

    with Session(engine) as session:
        owner = _create_user(session, username="owner", role="landlord")
        other = _create_user(session, username="other", role="landlord")
        owner_id = owner.id
        other_id = other.id

    client = TestClient(app)
    submitted = client.post(
        "/api/landlord/listings",
        headers={"X-User-Id": str(owner_id)},
        json=_listing_payload(),
    )

    assert submitted.status_code == 200
    listing_id = submitted.json()["listing"]["id"]

    response = client.post(
        f"/api/listings/{listing_id}/transition",
        headers={"X-User-Id": str(other_id)},
        json={"action": "deactivate"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "not your listing"

    with Session(engine) as session:
        saved = session.get(Listing, listing_id)
        assert saved is not None
        assert saved.status == "pending"
