from typing import Any

from app.services.listing_states import ListingState, register_state


@register_state
class SuspendedState(ListingState):
    name = "suspended"

    def reinstate(self, ctx: Any) -> None:
        ctx.transition_to("inactive")
