from typing import Any

from app.services.listing_states import ListingState, register_state


@register_state
class PendingState(ListingState):
    name = "pending"

    def provisionally_accept(self, ctx: Any) -> None:
        ctx.transition_to("provisionally_accepted")

    def verify(self, ctx: Any) -> None:
        ctx.transition_to("verified")

    def reject(self, ctx: Any, reason: str) -> None:
        ctx.transition_to("rejected", reason=reason)

    def suspend(self, ctx: Any) -> None:
        ctx.transition_to("suspended")
