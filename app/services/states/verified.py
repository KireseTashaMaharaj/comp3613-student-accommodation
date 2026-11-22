from typing import Any

from app.services.listing_states import ListingState, register_state


@register_state
class VerifiedState(ListingState):
    name = "verified"

    def activate(self, ctx: Any) -> None:
        ctx.transition_to("active")

    def deactivate(self, ctx: Any) -> None:
        ctx.transition_to("inactive")

    def suspend(self, ctx: Any) -> None:
        ctx.transition_to("suspended")