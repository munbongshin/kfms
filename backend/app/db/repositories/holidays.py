"""Repository for received holidays and the sync's key and outcome."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HolidaySync, SyncedHoliday
from app.utils.crypto import decrypt_password, encrypt_password

ROW_ID = 1


class HolidayRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def synced(self) -> Dict[str, str]:
        """Received days (ISO date -> name); empty if the table is not there yet."""
        try:
            result = await self.session.execute(select(SyncedHoliday))
            return {row.day: row.name for row in result.scalars().all()}
        except Exception:
            await self.session.rollback()
            return {}

    async def replace_year(self, year: int, days: Dict[str, str], source: str) -> None:
        await self.session.execute(delete(SyncedHoliday).where(SyncedHoliday.day.like(f"{year}-%")))
        for day, name in days.items():
            self.session.add(SyncedHoliday(day=day, name=name[:100], source=source))
        await self.session.commit()

    async def _row(self) -> Optional[HolidaySync]:
        return await self.session.get(HolidaySync, ROW_ID)

    async def _row_or_new(self) -> HolidaySync:
        row = await self._row()
        if row is None:
            row = HolidaySync(id=ROW_ID)
            self.session.add(row)
        return row

    async def service_key(self) -> Optional[str]:
        try:
            row = await self._row()
        except Exception:
            await self.session.rollback()
            return None
        return decrypt_password(row.service_key) if row and row.service_key else None

    async def set_key(self, key: Optional[str]) -> None:
        """Save the key encrypted, or forget it when blank."""
        row = await self._row_or_new()
        row.service_key = encrypt_password(key) if key else None
        await self.session.commit()

    async def record(self, status: str, error: str, source: str) -> None:
        row = await self._row_or_new()
        row.last_synced_at = datetime.now(timezone.utc)
        row.last_status, row.last_error, row.last_source = status, error or None, source or None
        await self.session.commit()

    async def state(self) -> Dict[str, Any]:
        try:
            row = await self._row()
        except Exception:
            await self.session.rollback()
            row = None
        return {
            "key_saved": bool(row and row.service_key),
            "last_synced_at": row.last_synced_at.isoformat() if row and row.last_synced_at else None,
            "last_status": row.last_status if row else None,
            "last_error": row.last_error if row else None,
            "last_source": row.last_source if row else None,
        }
