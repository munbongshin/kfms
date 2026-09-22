"""Repository for anomaly_review."""
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnomalyReview


class AnomalyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_reviews(
        self, database_id: str, finding_keys: List[str]
    ) -> Dict[str, AnomalyReview]:
        """Reviews for the given keys, indexed by finding_key."""
        if not finding_keys:
            return {}

        result = await self.session.execute(
            select(AnomalyReview).where(
                AnomalyReview.database_id == database_id,
                AnomalyReview.finding_key.in_(finding_keys),
            )
        )
        return {r.finding_key: r for r in result.scalars().all()}

    async def upsert_review(
        self,
        database_id: str,
        finding_key: str,
        rule_code: str,
        status: str,
        fingerprint: str,
        note: Optional[str] = None,
    ) -> AnomalyReview:
        result = await self.session.execute(
            select(AnomalyReview).where(
                AnomalyReview.database_id == database_id,
                AnomalyReview.finding_key == finding_key,
            )
        )
        review = result.scalar_one_or_none()

        if review is None:
            review = AnomalyReview(
                database_id=database_id,
                finding_key=finding_key,
                rule_code=rule_code,
                status=status,
                fingerprint=fingerprint,
                note=note,
            )
            self.session.add(review)
        else:
            review.status = status
            review.fingerprint = fingerprint
            # I3: the timestamp IS the audit evidence. Without this, flipping a
            # decision from confirmed to dismissed keeps the original review time
            # (the column's server_default only fires on INSERT).
            review.reviewed_at = datetime.now(timezone.utc)
            # An omitted note (None) must not erase a previously recorded one;
            # only overwrite when the caller actually supplied a note.
            if note is not None:
                review.note = note

        await self.session.commit()
        await self.session.refresh(review)
        return review
