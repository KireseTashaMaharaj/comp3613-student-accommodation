from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

import app.models
from app.main import app
from app.models.listing import Listing
from app.models.user import User
from app.models.listing_status_change import ListingStatusChange
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


def test_successful_transition_creates_one_status_change_record(monkeypatch):
    engine = _create_test_database(monkeypatch)

    with Session(engine) as session:
        landlord = _create_user(session, username="history_landlord", role="landlord")
        admin = _create_user(session, username="history_admin", role="admin")
        landlord_id = landlord.id
        admin_id = admin.id

    client = TestClient(app)
    submitted = client.post(
        "/api/landlord/listings",
        headers={"X-User-Id": str(landlord_id)},
        json=_listing_payload(),
    )
    listing_id = submitted.json()["listing"]["id"]

    approved = client.post(
        f"/api/listings/{listing_id}/transition",
        headers={"X-User-Id": str(admin_id)},
        json={"action": "verify"},
    )

    assert approved.status_code == 200

    with Session(engine) as session:
        changes = session.exec(
            select(ListingStatusChange)
            .where(ListingStatusChange.listing_id == listing_id)
            .order_by(ListingStatusChange.id)
        ).all()

    assert len(changes) == 1
    assert changes[0].old_status == "pending"
    assert changes[0].new_status == "verified"
    assert changes[0].actor_id == admin_id
    assert changes[0].changed_at


def test_two_successful_transitions_create_two_status_changes_in_order(monkeypatch):
    engine = _create_test_database(monkeypatch)

    with Session(engine) as session:
        landlord = _create_user(session, username="two_landlord", role="landlord")
        admin = _create_user(session, username="two_admin", role="admin")
        landlord_id = landlord.id
        admin_id = admin.id

    client = TestClient(app)
    submitted = client.post(
        "/api/landlord/listings",
        headers={"X-User-Id": str(landlord_id)},
        json=_listing_payload(),
    )
    listing_id = submitted.json()["listing"]["id"]

    provisional = client.post(
        f"/api/listings/{listing_id}/transition",
        headers={"X-User-Id": str(admin_id)},
        json={"action": "provisionally_accept"},
    )
    assert provisional.status_code == 200

    approved = client.post(
        f"/api/listings/{listing_id}/transition",
        headers={"X-User-Id": str(admin_id)},
        json={"action": "verify"},
    )
    assert approved.status_code == 200

    with Session(engine) as session:
        changes = session.exec(
            select(ListingStatusChange)
            .where(ListingStatusChange.listing_id == listing_id)
            .order_by(ListingStatusChange.id)
        ).all()

    assert [(change.old_status, change.new_status) for change in changes] == [
        ("pending", "provisionally_accepted"),
        ("provisionally_accepted", "verified"),
    ]
    assert [change.actor_id for change in changes] == [admin_id, admin_id]


def test_illegal_and_unauthorized_transitions_create_no_status_changes(monkeypatch):
    engine = _create_test_database(monkeypatch)

    with Session(engine) as session:
        landlord = _create_user(session, username="failed_landlord", role="landlord")
        other = _create_user(session, username="failed_other", role="landlord")
        landlord_id = landlord.id
        other_id = other.id

    client = TestClient(app)
    submitted = client.post(
        "/api/landlord/listings",
        headers={"X-User-Id": str(landlord_id)},
        json=_listing_payload(),
    )
    listing_id = submitted.json()["listing"]["id"]

    illegal = client.post(
        f"/api/listings/{listing_id}/transition",
        headers={"X-User-Id": str(landlord_id)},
        json={"action": "activate"},
    )
    assert illegal.status_code == 400

    unauthorized = client.post(
        f"/api/listings/{listing_id}/transition",
        headers={"X-User-Id": str(other_id)},
        json={"action": "deactivate"},
    )
    assert unauthorized.status_code == 400

    with Session(engine) as session:
        changes = session.exec(
            select(ListingStatusChange).where(
                ListingStatusChange.listing_id == listing_id
            )
        ).all()

    assert changes == []
