"""Repository for evaluation cases and runs."""
from typing import List, Optional

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvalCase, EvalRun


class EvalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def cases(self, database_id: Optional[str] = None) -> List[EvalCase]:
        stmt = select(EvalCase).order_by(EvalCase.id)
        if database_id:
            stmt = stmt.where(EvalCase.database_id == database_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def add_case(self, case: EvalCase) -> EvalCase:
        self.session.add(case)
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def delete_case(self, case_id: int) -> bool:
        result = await self.session.execute(delete(EvalCase).where(EvalCase.id == case_id))
        await self.session.commit()
        return result.rowcount > 0

    async def add_run(self, run: EvalRun) -> EvalRun:
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def run(self, run_id: int) -> Optional[EvalRun]:
        return await self.session.get(EvalRun, run_id)

    async def runs(self, limit: int = 20) -> List[EvalRun]:
        stmt = select(EvalRun).order_by(desc(EvalRun.id)).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def save(self, run: EvalRun) -> None:
        await self.session.commit()
