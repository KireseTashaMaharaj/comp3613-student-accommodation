from types import SimpleNamespace

import pytest

from app.services.listing_lifecycle import ListingLifecycle
from app.services.listing_states import STATES, InvalidTransitionError

ACTIONS = [
    "provisionally_accept",
    "verify",
    "reject",
    "resubmit",
    "activate",
    "deactivate",
    "suspend",
    "reinstate",
]

# state -> {allowed action: status it moves to}
ALLOWED = {
    "pending": {
        "provisionally_accept": "provisionally_accepted",
        "verify": "verified",
        "reject": "rejected",
        "suspend": "suspended",
    },
    "provisionally_accepted": {
        "verify": "verified",
        "reject": "rejected",
    },
    "verified": {
        "activate": "active",
        "deactivate": "inactive",
        "suspend": "suspended",
    },
    "active": {
        "deactivate": "inactive",
        "suspend": "suspended",
    },
    "rejected": {
        "resubmit": "pending",
    },
    "inactive": {
        "activate": "active",
        "suspend": "suspended",
    },
    "suspended": {
        "reinstate": "inactive",
    },
}

# Only the active state is visible to students.
VISIBLE = {state: state == "active" for state in ALLOWED}


def _run(lifecycle, action):
    if action == "reject":
        lifecycle.reject("not enough detail")
    else:
        getattr(lifecycle, action)()


ALLOWED_CASES = [
    (state, action, target)
    for state, moves in ALLOWED.items()
    for action, target in moves.items()
]

ILLEGAL_CASES = [
    (state, action)
    for state, moves in ALLOWED.items()
    for action in ACTIONS
    if action not in moves
]


def test_all_seven_states_are_registered():
    assert set(ALLOWED) <= set(STATES)
    assert len(ALLOWED) == 7


@pytest.mark.parametrize(("state", "action", "target"), ALLOWED_CASES)
def test_allowed_transition_moves_to_expected_status(state, action, target):
    listing = SimpleNamespace(status=state)
    lifecycle = ListingLifecycle(listing)

    _run(lifecycle, action)

    assert listing.status == target
    assert lifecycle.last_change["old_status"] == state
    assert lifecycle.last_change["new_status"] == target


@pytest.mark.parametrize(("state", "action"), ILLEGAL_CASES)
def test_illegal_transition_raises_and_leaves_status_unchanged(state, action):
    listing = SimpleNamespace(status=state)
    lifecycle = ListingLifecycle(listing)

    with pytest.raises(InvalidTransitionError):
        _run(lifecycle, action)

    assert listing.status == state
    assert lifecycle.last_change is None


@pytest.mark.parametrize(("state", "visible"), VISIBLE.items())
def test_only_active_listings_are_visible_to_students(state, visible):
    lifecycle = ListingLifecycle(SimpleNamespace(status=state))

    assert lifecycle.is_visible_to_students() is visible


def test_reject_reason_is_recorded():
    listing = SimpleNamespace(status="pending")
    lifecycle = ListingLifecycle(listing)

    lifecycle.reject("missing photos")

    assert lifecycle.last_change["reason"] == "missing photos"