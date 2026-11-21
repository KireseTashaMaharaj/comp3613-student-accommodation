import pytest

from app.services.listing_states import InvalidTransitionError, ListingState


class PendingListingState(ListingState):
    name = "pending"


@pytest.mark.parametrize(
    ("action", "args"),
    [
        ("provisionally_accept", ()),
        ("verify", ()),
        ("reject", ("missing information",)),
        ("resubmit", ()),
        ("activate", ()),
        ("deactivate", ()),
        ("suspend", ()),
        ("reinstate", ()),
    ],
)
def test_base_state_rejects_every_action(action, args):
    state = PendingListingState()

    with pytest.raises(InvalidTransitionError) as error:
        getattr(state, action)(None, *args)

    assert action.replace("_", " ") in str(error.value)
    assert "pending" in str(error.value)


def test_invalid_transition_error_names_action_and_state():
    error = InvalidTransitionError("activate", PendingListingState())

    assert str(error) == "cannot activate a listing that is pending"


def test_subclass_name_appears_in_invalid_transition_error():
    with pytest.raises(InvalidTransitionError) as error:
        PendingListingState().activate(None)

    assert "pending" in str(error.value)


def test_base_state_is_not_visible():
    assert ListingState().is_visible() is False
