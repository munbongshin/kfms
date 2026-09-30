"""Repository for the business glossary."""
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GlossaryTerm


class GlossaryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> List[GlossaryTerm]:
        result = await self.session.execute(select(GlossaryTerm).order_by(GlossaryTerm.term))
        return list(result.scalars().all())

    async def get_by_term(self, term: str) -> Optional[GlossaryTerm]:
        result = await self.session.execute(select(GlossaryTerm).where(GlossaryTerm.term == term))
        return result.scalar_one_or_none()

    async def create(self, term: str, definition: str) -> GlossaryTerm:
        row = GlossaryTerm(term=term, definition=definition)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def update(self, term_id: int, term: str, definition: str) -> Optional[GlossaryTerm]:
        row = await self.session.get(GlossaryTerm, term_id)
        if row is None:
            return None
        row.term, row.definition = term, definition
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def delete(self, term_id: int) -> bool:
        result = await self.session.execute(delete(GlossaryTerm).where(GlossaryTerm.id == term_id))
        await self.session.commit()
        return result.rowcount > 0
