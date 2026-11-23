from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ListingStatusChange(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    old_status: str
    new_status: str
    actor_id: int
    changed_at: str = Field(default_factory=_now_iso)
    reason: str = ""