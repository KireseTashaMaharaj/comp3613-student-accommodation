from sqlmodel import Session, select
from app.models.listing import Listing
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ListingRepository:
    """Reads and writes Listing rows. Holds no lifecycle rules."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, listing_id: int) -> Optional[Listing]:
        return self.db.get(Listing, listing_id)

    def get_all(self, status: Optional[str] = None) -> list[Listing]:
        stmt = select(Listing).order_by(Listing.id)
        if status:
            stmt = stmt.where(Listing.status == status)
        return self.db.exec(stmt).all()

    def get_by_landlord(self, landlord_id: int) -> list[Listing]:
        stmt = (
            select(Listing)
            .where(Listing.landlord_id == landlord_id)
            .order_by(Listing.id)
        )
        return self.db.exec(stmt).all()

    def save(self, listing: Listing) -> Listing:
        """Insert or update a listing, then return the refreshed row."""
        try:
            self.db.add(listing)
            self.db.commit()
            self.db.refresh(listing)
            return listing
        except Exception as e:
            logger.error(f"An error occurred while saving listing: {e}")
            self.db.rollback()
            raise