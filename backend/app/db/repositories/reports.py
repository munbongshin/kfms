"""Repository for saved reports."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SavedReport


class ReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> List[SavedReport]:
        result = await self.session.execute(select(SavedReport).order_by(SavedReport.name))
        return list(result.scalars().all())

    async def get(self, report_id: int) -> Optional[SavedReport]:
        return await self.session.get(SavedReport, report_id)

    async def due(self, now: datetime) -> List[SavedReport]:
        stmt = select(SavedReport).where(SavedReport.is_active.is_(True), SavedReport.next_run_at <= now)
        return list((await self.session.execute(stmt)).scalars().all())

    async def add(self, report: SavedReport) -> SavedReport:
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def save(self, report: SavedReport) -> SavedReport:
        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def delete(self, report_id: int) -> bool:
        result = await self.session.execute(delete(SavedReport).where(SavedReport.id == report_id))
        await self.session.commit()
        return result.rowcount > 0
