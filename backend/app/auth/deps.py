"""Who is calling, and may they.

`current_user` reads the bearer token and re-checks the user in the database,
so disabling an account or changing its role takes effect on the next request
rather than when the token expires.
"""
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import read_token
from app.config import settings
from app.db.repositories.audit import AuditRepository
from app.db.repositories.users import UserRepository
from app.dependencies import get_db

TOKEN_TTL_SECONDS = 12 * 3600


def secret() -> str:
    # The same key that protects stored connection passwords. Without one the
    # tokens still work but do not survive a restart.
    return settings.FERNET_KEY or "kfms-dev-secret"


@dataclass
class CurrentUser:
    id: int
    username: str
    display_name: str
    role: str


def client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def token_from(request: Request) -> Optional[str]:
    header = request.headers.get("authorization", "")
    return header[7:] if header.lower().startswith("bearer ") else None


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> CurrentUser:
    token = token_from(request)
    claims = read_token(token, secret()) if token else None
    if not claims:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다")
    user = await UserRepository(db).get(int(claims["uid"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용할 수 없는 계정입니다")
    me = CurrentUser(user.id, user.username, user.display_name, user.role)
    request.state.user = me
    return me


def require(*roles: str):
    """A dependency that admits only these roles."""
    async def check(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="이 작업을 할 권한이 없습니다")
        return user
    return check


ADMIN = Depends(require("admin"))
AUDITOR = Depends(require("admin", "auditor"))
ANY_USER = Depends(current_user)


async def record(
    db: AsyncSession, user: Optional[CurrentUser], request: Request, action: str, target: str = "", **detail
) -> None:
    """Write one audit entry; the log must never break the request it describes."""
    try:
        await AuditRepository(db).add(
            user.username if user else detail.pop("username", ""),
            user.role if user else "",
            action, target, detail, client_ip(request),
        )
    except Exception:
        pass
