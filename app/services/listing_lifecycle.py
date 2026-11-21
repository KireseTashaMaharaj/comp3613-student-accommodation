"""Context for delegating listing lifecycle actions to the current state."""

from typing import Dict, Mapping, Optional, Protocol, Type, Union

from . import listing_states
from . import states as _registered_states
from .listing_states import ListingState


class ListingLike(Protocol):
    status: str


class ListingLifecycle:
    def __init__(
        self,
        listing: ListingLike,
        states: Optional[Mapping[str, Type[ListingState]]] = None,
    ) -> None:
        self.listing = listing
        self.states = listing_states.STATES if states is None else states

        try:
            state_class = self.states[listing.status]
        except KeyError:
            raise ValueError(
                f"no listing state is registered for status {listing.status!r}"
            ) from None

        self.state = state_class()
        self.last_change: Optional[Dict[str, Optional[str]]] = None

    def provisionally_accept(self) -> None:
        self.state.provisionally_accept(self)

    def verify(self) -> None:
        self.state.verify(self)

    def reject(self, reason: str) -> None:
        self.state.reject(self, reason)

    def resubmit(self) -> None:
        self.state.resubmit(self)

    def activate(self) -> None:
        self.state.activate(self)

    def deactivate(self) -> None:
        self.state.deactivate(self)

    def suspend(self) -> None:
        self.state.suspend(self)

    def reinstate(self) -> None:
        self.state.reinstate(self)

    def set_state(
        self,
        new_state: Union[ListingState, Type[ListingState]],
        reason: Optional[str] = None,
    ) -> None:
        if isinstance(new_state, type):
            new_state = new_state()

        old_status = self.listing.status
        new_status = new_state.name
        self.listing.status = new_status
        self.state = new_state
        self.last_change = {
            "old_status": old_status,
            "new_status": new_status,
            "reason": reason,
        }

    def transition_to(self, status_name: str, reason: Optional[str] = None) -> None:
        try:
            state_class = self.states[status_name]
        except KeyError:
            raise ValueError(
                f"no listing state is registered for status {status_name!r}"
            ) from None

        self.set_state(state_class, reason=reason)

    def is_visible_to_students(self) -> bool:
        return self.state.is_visible()
