"""Repository for the single-row anomaly_settings table."""
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnomalySetting

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
