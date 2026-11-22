from app.models.listing import Listing
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


def test_admin_can_verify_pending_listing(test_session, monkeypatch):
    _use_test_database(test_session, monkeypatch)
    admin = _create_user(test_session, "admin", "admin")
    landlord = _create_user(test_session, "owner", "landlord")
    listing = _create_pending_listing(test_session, landlord.id)

    class VerifiedState(ListingState):
        name = "verified"

    monkeypatch.setitem(STATES, "verified", VerifiedState)

    result = listings.transition(admin.id, listing.id, "verify")

    assert result["ok"] is True
    assert result["listing"]["status"] == "verified"
    assert result["last_change"] == {
        "old_status": "pending",
        "new_status": "verified",
        "reason": None,
    }


def test_landlord_cannot_verify(test_session, monkeypatch):
    _use_test_database(test_session, monkeypatch)
    landlord = _create_user(test_session, "landlord", "landlord")
    listing = _create_pending_listing(test_session, landlord.id)

    result = listings.transition(landlord.id, listing.id, "verify")

    assert result == {"ok": False, "error": "admin only"}


def test_landlord_cannot_change_another_landlords_listing(test_session, monkeypatch):
    _use_test_database(test_session, monkeypatch)
    actor = _create_user(test_session, "actor", "landlord")
    owner = _create_user(test_session, "owner", "landlord")
    listing = _create_pending_listing(test_session, owner.id)

    result = listings.transition(actor.id, listing.id, "activate")

    assert result == {"ok": False, "error": "not your listing"}


def test_reject_requires_a_reason(test_session, monkeypatch):
    _use_test_database(test_session, monkeypatch)
    admin = _create_user(test_session, "admin", "admin")
    landlord = _create_user(test_session, "owner", "landlord")
    listing = _create_pending_listing(test_session, landlord.id)

    result = listings.transition(admin.id, listing.id, "reject")

    assert result == {"ok": False, "error": "reason required"}


def test_unknown_action_returns_clear_error(test_session, monkeypatch):
    _use_test_database(test_session, monkeypatch)
    admin = _create_user(test_session, "admin", "admin")

    result = listings.transition(admin.id, 1, "teleport")

    assert result["ok"] is False
    assert "unknown action" in result["error"]


def test_illegal_move_returns_error_without_changing_status(test_session, monkeypatch):
    _use_test_database(test_session, monkeypatch)
    landlord = _create_user(test_session, "landlord", "landlord")
    listing = _create_pending_listing(test_session, landlord.id)

    result = listings.transition(landlord.id, listing.id, "activate")

    assert result["ok"] is False
    assert "cannot activate" in result["error"]
    test_session.expire_all()
    assert test_session.get(Listing, listing.id).status == "pending"


def test_successful_reject_returns_change_with_reason(test_session, monkeypatch):
    _use_test_database(test_session, monkeypatch)
    admin = _create_user(test_session, "admin", "admin")
    landlord = _create_user(test_session, "owner", "landlord")
    listing = _create_pending_listing(test_session, landlord.id)

    class RejectedState(ListingState):
        name = "rejected"

    monkeypatch.setitem(STATES, "rejected", RejectedState)

    result = listings.transition(
        admin.id,
        listing.id,
        "reject",
        reason="missing documents",
    )

    assert result["ok"] is True
    assert result["listing"]["status"] == "rejected"
    assert result["last_change"] == {
        "old_status": "pending",
        "new_status": "rejected",
        "reason": "missing documents",
    }
