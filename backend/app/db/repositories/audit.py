"""Repository for the audit log."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(
        self,
        username: str,
        role: str,
        action: str,
        target: str = "",
        detail: Optional[Dict[str, Any]] = None,
        ip: str = "",
    ) -> None:
        self.session.add(AuditLog(
            username=username, role=role, action=action,
            target=target[:500], detail=detail or {}, ip=ip[:64],
        ))
        await self.session.commit()

    async def search(
        self,
        username: Optional[str] = None,
        action: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[AuditLog]:
        stmt = select(AuditLog).order_by(desc(AuditLog.at), desc(AuditLog.id))
        if username:
            stmt = stmt.where(AuditLog.username == username)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if since:
            stmt = stmt.where(AuditLog.at >= since)
        result = await self.session.execute(stmt.limit(limit).offset(offset))
        return list(result.scalars().all())
