from typing import Any

from app.services.listing_states import ListingState, register_state


@register_state
class RejectedState(ListingState):
    name = "rejected"

    def resubmit(self, ctx: Any) -> None:
        ctx.transition_to("pending")
