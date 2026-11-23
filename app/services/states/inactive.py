from typing import Any

from app.services.listing_states import ListingState, register_state


@register_state
class InactiveState(ListingState):
    name = "inactive"

    def activate(self, ctx: Any) -> None:
        ctx.transition_to("active")

    def suspend(self, ctx: Any) -> None:
        ctx.transition_to("suspended")
