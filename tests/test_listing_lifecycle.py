from types import SimpleNamespace

import pytest

from app.services import listing_states
from app.services.listing_lifecycle import ListingLifecycle
from app.services.listing_states import InvalidTransitionError, ListingState


def test_context_delegates_actions_updates_status_and_visibility():
    class ActiveState(ListingState):
        name = "active"

        def is_visible(self):
            return True

    class PendingState(ListingState):
        name = "pending"

        def activate(self, context):
            context.set_state(ActiveState(), reason="approved")

    listing = SimpleNamespace(status="pending")
    lifecycle = ListingLifecycle(
        listing,
        states={"pending": PendingState, "active": ActiveState},
    )

    assert isinstance(lifecycle.state, PendingState)
    assert lifecycle.is_visible_to_students() is False

    lifecycle.activate()

    assert isinstance(lifecycle.state, ActiveState)
    assert listing.status == "active"
    assert lifecycle.last_change == {
        "old_status": "pending",
        "new_status": "active",
        "reason": "approved",
    }
    assert lifecycle.is_visible_to_students() is True

    with pytest.raises(InvalidTransitionError):
        lifecycle.deactivate()

    assert listing.status == "active"


def test_unknown_status_raises_clear_error():
    listing = SimpleNamespace(status="unknown")

    with pytest.raises(ValueError, match="unknown"):
        ListingLifecycle(listing, states={})


def test_register_state_adds_class_and_rejects_duplicate_name(monkeypatch):
    monkeypatch.setattr(listing_states, "STATES", {})

    @listing_states.register_state
    class RegisteredState(ListingState):
        name = "test-registered"

    assert listing_states.STATES["test-registered"] is RegisteredState

    with pytest.raises(ValueError, match="already registered"):

        @listing_states.register_state
        class DuplicateState(ListingState):
            name = "test-registered"
