from types import SimpleNamespace

import pytest

from app.services.listing_lifecycle import ListingLifecycle
from app.services.listing_states import InvalidTransitionError, ListingState, STATES
from app.services.states.pending import PendingState


def _fake_target_states():
    class ProvisionallyAcceptedState(ListingState):
        name = "provisionally_accepted"

    class VerifiedState(ListingState):
        name = "verified"

    class RejectedState(ListingState):
        name = "rejected"

    class SuspendedState(ListingState):
        name = "suspended"

    return {
        state.name: state
        for state in (
            ProvisionallyAcceptedState,
            VerifiedState,
            RejectedState,
            SuspendedState,
        )
    }


@pytest.mark.parametrize(
    ("action", "expected_status", "reason"),
    [
        ("provisionally_accept", "provisionally_accepted", None),
        ("verify", "verified", None),
        ("reject", "rejected", "missing documents"),
        ("suspend", "suspended", None),
    ],
)
def test_pending_state_allows_expected_transitions(action, expected_status, reason):
    listing = SimpleNamespace(status="pending")
    states = {"pending": PendingState, **_fake_target_states()}
    lifecycle = ListingLifecycle(listing, states=states)

    if action == "reject":
        lifecycle.reject(reason)
    else:
        getattr(lifecycle, action)()

    assert listing.status == expected_status
    assert lifecycle.last_change["new_status"] == expected_status
    assert lifecycle.last_change["reason"] == reason


@pytest.mark.parametrize("action", ["activate", "deactivate", "resubmit", "reinstate"])
def test_pending_state_blocks_other_actions(action):
    listing = SimpleNamespace(status="pending")
    lifecycle = ListingLifecycle(
        listing,
        states={"pending": PendingState, **_fake_target_states()},
    )

    with pytest.raises(InvalidTransitionError):
        getattr(lifecycle, action)()

    assert listing.status == "pending"


def test_pending_state_is_not_visible_to_students():
    listing = SimpleNamespace(status="pending")
    lifecycle = ListingLifecycle(
        listing,
        states={"pending": PendingState, **_fake_target_states()},
    )

    assert not lifecycle.is_visible_to_students()


def test_pending_state_is_registered_in_real_registry():
    assert STATES["pending"] is PendingState


def test_transition_to_unknown_state_leaves_status_unchanged():
    listing = SimpleNamespace(status="pending")
    lifecycle = ListingLifecycle(
        listing,
        states={"pending": PendingState, **_fake_target_states()},
    )

    with pytest.raises(ValueError, match="not-registered"):
        lifecycle.transition_to("not-registered", reason="should not be saved")

    assert listing.status == "pending"
    assert lifecycle.last_change is None
