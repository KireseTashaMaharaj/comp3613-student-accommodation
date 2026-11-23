from sqlmodel import select

from app.models.listing import Listing
from app.models.listing_status_change import ListingStatusChange
from app.models.user import User
from app.services import housing_auth, listings
from app.services.listing_states import ListingState, STATES


def _create_user(test_session, username, role):
    user = User(
        username=username,
        email=f"{username}@example.com",
        password="test-password",
        role=role,
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user


def _create_pending_listing(test_session, landlord_id):
    listing = Listing(
        landlord_id=landlord_id,
        title="Test listing",
        area="st_augustine",
        price=1000,
        amenities="",
        contact_phone="555-0100",
        contact_email="landlord@example.com",
        status="pending",
        created_at="2026-01-01T00:00:00+00:00",
    )
    test_session.add(listing)
    test_session.commit()
    test_session.refresh(listing)
    return listing


def _use_test_database(test_session, monkeypatch):
    engine = test_session.get_bind()
    monkeypatch.setattr(listings, "engine", engine)
    monkeypatch.setattr(housing_auth, "engine", engine)


def _history(test_session):
    test_session.expire_all()
    return test_session.exec(select(ListingStatusChange)).all()


def test_successful_transition_records_status_change(test_session, monkeypatch):
    _use_test_database(test_session, monkeypatch)
    admin = _create_user(test_session, "admin", "admin")
    landlord = _create_user(test_session, "owner", "landlord")
    listing = _create_pending_listing(test_session, landlord.id)

    class VerifiedState(ListingState):
        name = "verified"

    monkeypatch.setitem(STATES, "verified", VerifiedState)

    result = listings.transition(admin.id, listing.id, "verify")

    assert result["ok"] is True
    rows = _history(test_session)
    assert len(rows) == 1
    assert rows[0].listing_id == listing.id
    assert rows[0].old_status == "pending"
    assert rows[0].new_status == "verified"
    assert rows[0].actor_id == admin.id
    assert rows[0].reason == ""
    assert rows[0].changed_at  # timestamp was filled in


def test_reject_records_the_reason(test_session, monkeypatch):
    _use_test_database(test_session, monkeypatch)
    admin = _create_user(test_session, "admin", "admin")
    landlord = _create_user(test_session, "owner", "landlord")
    listing = _create_pending_listing(test_session, landlord.id)

    class RejectedState(ListingState):
        name = "rejected"

    monkeypatch.setitem(STATES, "rejected", RejectedState)

    result = listings.transition(
        admin.id, listing.id, "reject", reason="  missing documents  "
    )

    assert result["ok"] is True
    rows = _history(test_session)
    assert len(rows) == 1
    assert rows[0].new_status == "rejected"
    assert rows[0].reason == "missing documents"  # trimmed


def test_illegal_transition_records_nothing(test_session, monkeypatch):
    _use_test_database(test_session, monkeypatch)
    landlord = _create_user(test_session, "landlord", "landlord")
    listing = _create_pending_listing(test_session, landlord.id)

    result = listings.transition(landlord.id, listing.id, "activate")

    assert result["ok"] is False
    assert _history(test_session) == []


def test_unauthorized_role_records_nothing(test_session, monkeypatch):
    _use_test_database(test_session, monkeypatch)
    landlord = _create_user(test_session, "landlord", "landlord")
    listing = _create_pending_listing(test_session, landlord.id)

    result = listings.transition(landlord.id, listing.id, "verify")

    assert result == {"ok": False, "error": "admin only"}
    assert _history(test_session) == []


def test_another_landlords_listing_records_nothing(test_session, monkeypatch):
    _use_test_database(test_session, monkeypatch)
    actor = _create_user(test_session, "actor", "landlord")
    owner = _create_user(test_session, "owner", "landlord")
    listing = _create_pending_listing(test_session, owner.id)

    result = listings.transition(actor.id, listing.id, "activate")

    assert result == {"ok": False, "error": "not your listing"}
    assert _history(test_session) == []