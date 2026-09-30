"""Repository for the single-row anomaly_settings table."""
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnomalySetting, AnomalySettingHistory

ROW_ID = 1


class AnomalySettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def load(self) -> Dict[str, Dict[str, Any]]:
        """The saved overrides; empty when nothing was ever edited or the table
        is missing — the screen then simply runs on the built-in defaults."""
        try:
            result = await self.session.execute(select(AnomalySetting).where(AnomalySetting.id == ROW_ID))
            row = result.scalar_one_or_none()
            return dict(row.params) if row and row.params else {}
        except Exception:
            await self.session.rollback()
            return {}

    async def save(self, params: Dict[str, Dict[str, Any]]) -> None:
        result = await self.session.execute(select(AnomalySetting).where(AnomalySetting.id == ROW_ID))
        row = result.scalar_one_or_none()
        if row is None:
            row = AnomalySetting(id=ROW_ID)
            self.session.add(row)
        row.params = params
        await self.session.commit()

    async def add_history(
        self, changed_by: str, before: Dict[str, Any], after: Dict[str, Any], changes: List[Dict[str, Any]]
    ) -> AnomalySettingHistory:
        entry = AnomalySettingHistory(changed_by=changed_by, before=before, after=after, changes=changes)
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def history(self, limit: int = 30) -> List[AnomalySettingHistory]:
        result = await self.session.execute(
            select(AnomalySettingHistory).order_by(AnomalySettingHistory.id.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_history(self, entry_id: int) -> Optional[AnomalySettingHistory]:
        return await self.session.get(AnomalySettingHistory, entry_id)
