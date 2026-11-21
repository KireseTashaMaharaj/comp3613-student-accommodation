"""Base types for listing lifecycle states."""

from typing import Any


class InvalidTransitionError(Exception):
    """Raised when an action is not allowed by the current listing state."""

    def __init__(self, action: str, state: Any) -> None:
        self.action = action
        self.state_name = getattr(state, "name", str(state))
        super().__init__(
            f"cannot {self.action} a listing that is {self.state_name}"
        )


class ListingState:
    """Base listing state that rejects every lifecycle action by default."""

    name = "base"

    def provisionally_accept(self, ctx: Any) -> None:
        """Reject provisional acceptance in this state."""
        raise InvalidTransitionError("provisionally accept", self)

    def verify(self, ctx: Any) -> None:
        """Reject verification in this state."""
        raise InvalidTransitionError("verify", self)

    def reject(self, ctx: Any, reason: str) -> None:
        """Reject the rejection action in this state."""
        raise InvalidTransitionError("reject", self)

    def resubmit(self, ctx: Any) -> None:
        """Reject resubmission in this state."""
        raise InvalidTransitionError("resubmit", self)

    def activate(self, ctx: Any) -> None:
        """Reject activation in this state."""
        raise InvalidTransitionError("activate", self)

    def deactivate(self, ctx: Any) -> None:
        """Reject deactivation in this state."""
        raise InvalidTransitionError("deactivate", self)

    def suspend(self, ctx: Any) -> None:
        """Reject suspension in this state."""
        raise InvalidTransitionError("suspend", self)

    def reinstate(self, ctx: Any) -> None:
        """Reject reinstatement in this state."""
        raise InvalidTransitionError("reinstate", self)

    def is_visible(self) -> bool:
        """Return whether listings in this state are visible."""
        return False
