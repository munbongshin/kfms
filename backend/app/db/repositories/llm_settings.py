"""Repository for the single-row llm_settings table."""
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LLMSetting
from app.utils.crypto import decrypt_password, encrypt_password

ROW_ID = 1


def _map_keys(profiles: Dict[str, Dict[str, Any]], fn) -> Dict[str, Dict[str, Any]]:
    """Apply fn to every profile's api_key, leaving the rest as is."""
    out: Dict[str, Dict[str, Any]] = {}
    for name, values in (profiles or {}).items():
        copy = dict(values)
        if copy.get("api_key"):
            copy["api_key"] = fn(copy["api_key"])
        out[name] = copy
    return out


class LLMSettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _row(self) -> Optional[LLMSetting]:
        result = await self.session.execute(select(LLMSetting).where(LLMSetting.id == ROW_ID))
        return result.scalar_one_or_none()

    async def load(self) -> Optional[Dict[str, Any]]:
        """The saved settings with keys decrypted, or None if never saved."""
        row = await self._row()
        if row is None:
            return None
        return {"provider": row.provider, "profiles": _map_keys(row.profiles, decrypt_password)}

    async def save(self, values: Dict[str, Any]) -> None:
        """Store the settings; every API key is encrypted before it is written."""
        row = await self._row()
        if row is None:
            row = LLMSetting(id=ROW_ID)
            self.session.add(row)

        row.provider = values.get("provider")
        # A fresh dict so SQLAlchemy sees the JSON column as changed.
        row.profiles = _map_keys(values.get("profiles") or {}, encrypt_password)
        await self.session.commit()
