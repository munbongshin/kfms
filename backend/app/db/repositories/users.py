"""Repository for users."""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User

ROLES = ("admin", "auditor", "viewer")


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def count(self) -> int:
        return int((await self.session.execute(select(func.count()).select_from(User))).scalar() or 0)

    async def count_active_admins(self) -> int:
        stmt = select(func.count()).select_from(User).where(User.role == "admin", User.is_active.is_(True))
        return int((await self.session.execute(stmt)).scalar() or 0)

    async def list_all(self) -> List[User]:
        return list((await self.session.execute(select(User).order_by(User.username))).scalars().all())

    async def get(self, user_id: int) -> Optional[User]:
        return await self.session.get(User, user_id)

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def create(self, username: str, display_name: str, password_hash: str, role: str) -> User:
        user = User(username=username, display_name=display_name, password_hash=password_hash, role=role)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def save(self, user: User) -> User:
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def touch_login(self, user: User) -> None:
        user.last_login_at = datetime.now(timezone.utc)
        await self.session.commit()
