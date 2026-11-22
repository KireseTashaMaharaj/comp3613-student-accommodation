from typing import Any

from app.services.listing_states import ListingState, register_state


@register_state
class ActiveState(ListingState):
    name = "active"

    def deactivate(self, ctx: Any) -> None:
        ctx.transition_to("inactive")

    def suspend(self, ctx: Any) -> None:
        ctx.transition_to("suspended")

    def is_visible(self) -> bool:
        return True