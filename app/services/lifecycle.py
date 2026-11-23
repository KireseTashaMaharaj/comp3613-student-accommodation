"""
Listing lifecycle tracker — procedural flag soup.

Intended flow: pending → verified → active|inactive, or pending → rejected.
Landlord may toggle active/inactive only after verification.

This module mixes a status string with four boolean flags updated through
nested conditionals. Invalid jumps are allowed; flags and status drift.

Ideal fix: State pattern (one state object per status with allowed transitions).
"""

from __future__ import annotations

from typing import Any

ACTIONS = (
    "submit",  # noop after create
    "verify",
    "reject",
    "activate",
    "deactivate",
    "resubmit",
)


def snapshot(listing: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": listing["id"],
        "status": listing["status"],
    }


def apply_action(listing: dict[str, Any], action: str) -> dict[str, Any]:
    """Mutate a copy of the listing according to action using status only."""
    if action not in ACTIONS:
        return {"ok": False, "error": f"unknown action {action!r}"}

    status = listing["status"]

    if action == "submit":
        status = "pending"
    elif action == "verify":
        status = "verified"
    elif action == "reject":
        status = "rejected"
    elif action == "activate":
        status = "active"
    elif action == "deactivate":
        status = "inactive"
    elif action == "resubmit":
        status = "pending"
    else:
        return {"ok": False, "error": "unhandled"}

    return _ok(listing, status)


def _ok(
    listing: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    updated = dict(listing)
    updated["status"] = status
    return {
        "ok": True,
        "listing": snapshot(updated),
        "row": updated,
        "changed": True,
    }


def visible_to_students(listing: dict[str, Any]) -> bool:
    """A listing is visible to students only in the active state."""
    return listing.get("status") == "active"
