"""Listing CRUD, browse filters, messaging, and lifecycle transitions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.database import engine
from app.models.listing import Listing
from app.models.message import Message
from app.services.housing_auth import get_user
from app.services.lifecycle import visible_to_students
from app.services.listing_lifecycle import ListingLifecycle
from app.services.listing_states import InvalidTransitionError

ALLOWED_AREAS = {"st_augustine", "mount_hope"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_amenities(raw: str) -> list[str]:
    return [a.strip().lower() for a in (raw or "").split(",") if a.strip()]


def submit_listing(
    landlord_id: int,
    *,
    title: str,
    area: str,
    price: int,
    amenities: str,
    contact_phone: str,
    contact_email: str,
    photos: str = "",
) -> dict[str, Any]:
    user = get_user(landlord_id)
    if not user or user["role"] != "landlord":
        return {"ok": False, "error": "landlords only"}
    # DEFECT: area not restricted to ALLOWED_AREAS
    if price <= 0:
        return {"ok": False, "error": "price must be positive"}
    # DEFECT: empty amenities allowed

    with Session(engine) as session:
        listing = Listing(
            landlord_id=landlord_id,
            title=title,
            area=area,
            price=price,
            amenities=amenities,
            contact_phone=contact_phone,
            contact_email=contact_email,
            photos=photos,
            status="pending",
            created_at=_now(),
        )
        session.add(listing)
        session.commit()
        session.refresh(listing)
        return {"ok": True, "listing": listing.model_dump()}


def transition(
    actor_id: int,
    listing_id: int,
    action: str,
    reason: str | None = None,
) -> dict[str, Any]:
    actor = get_user(actor_id)
    if not actor:
        return {"ok": False, "error": "unknown user"}

    admin_actions = {
        "provisionally_accept",
        "verify",
        "reject",
        "suspend",
        "reinstate",
    }
    landlord_actions = {"activate", "deactivate", "resubmit"}
    allowed_actions = admin_actions | landlord_actions
    if action not in allowed_actions:
        return {
            "ok": False,
            "error": f"unknown action {action!r}; expected one of {sorted(allowed_actions)}",
        }
    if action in admin_actions and actor["role"] != "admin":
        return {"ok": False, "error": "admin only"}
    if action in landlord_actions and actor["role"] != "landlord":
        return {"ok": False, "error": "landlord only"}
    if action == "reject" and (reason is None or not reason.strip()):
        return {"ok": False, "error": "reason required"}

    with Session(engine) as session:
        listing = session.get(Listing, listing_id)
        if listing is None:
            return {"ok": False, "error": "listing not found"}
        if action in landlord_actions and listing.landlord_id != actor_id:
            return {"ok": False, "error": "not your listing"}

        try:
            lifecycle = ListingLifecycle(listing)
            if action == "reject":
                lifecycle.reject(reason)
            else:
                getattr(lifecycle, action)()
        except (InvalidTransitionError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

        session.add(listing)
        session.commit()
        session.refresh(listing)
        return {
            "ok": True,
            "listing": listing.model_dump(),
            "last_change": lifecycle.last_change,
        }


def browse_for_students(
    student_id: int,
    *,
    area: str | None = None,
    max_price: int | None = None,
    amenity: str | None = None,
) -> dict[str, Any]:
    student = get_user(student_id)
    if not student or student["role"] != "student":
        return {"ok": False, "error": "students only"}
    # DEFECT: provisional / missing student_id not blocked

    with Session(engine) as session:
        rows = session.exec(select(Listing).order_by(Listing.id)).all()
        items = [r.model_dump() for r in rows]

    results = []
    for item in items:
        if not visible_to_students(item):
            continue
        if area and item["area"] != area:
            continue
        if max_price is not None and int(item["price"]) > max_price:
            continue
        # DEFECT: amenity filter is substring on raw string, case-sensitive sometimes
        if amenity and amenity not in item["amenities"]:
            continue
        results.append(item)
    return {"ok": True, "listings": results}


def list_all(*, status: str | None = None) -> list[dict[str, Any]]:
    with Session(engine) as session:
        stmt = select(Listing).order_by(Listing.id)
        if status:
            stmt = stmt.where(Listing.status == status)
        return [r.model_dump() for r in session.exec(stmt).all()]


def send_message(student_id: int, listing_id: int, body: str) -> dict[str, Any]:
    student = get_user(student_id)
    if not student or student["role"] != "student":
        return {"ok": False, "error": "students only"}
    if not body.strip():
        return {"ok": False, "error": "body required"}
    with Session(engine) as session:
        listing = session.get(Listing, listing_id)
        if listing is None:
            return {"ok": False, "error": "listing not found"}
        # DEFECT: can message pending/rejected listings
        message = Message(
            listing_id=listing_id,
            student_id=student_id,
            body=body,
            created_at=_now(),
        )
        session.add(message)
        session.commit()
        session.refresh(message)
        return {"ok": True, "message_id": message.id}
