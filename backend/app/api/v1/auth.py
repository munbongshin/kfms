"""
Sign-in, first-run setup, user management and the audit log.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import (
    ADMIN, AUDITOR, TOKEN_TTL_SECONDS, CurrentUser, current_user, record, secret,
)
from app.auth.security import create_token, hash_password, verify_password
from app.auth.user_rules import delete_block_reason
from app.db.repositories.audit import AuditRepository
from app.db.repositories.users import ROLES, UserRepository
from app.dependencies import get_db

router = APIRouter(tags=["Auth"])

MIN_PASSWORD = 8


class Credentials(BaseModel):
    username: str = Field(..., min_length=1, max_length=60)
    password: str = Field(..., min_length=1, max_length=200)


class NewUser(BaseModel):
    username: str = Field(..., min_length=2, max_length=60, pattern=r"^[A-Za-z0-9_.\-가-힣]+$")
    display_name: str = Field(default="", max_length=100)
    password: str = Field(..., min_length=MIN_PASSWORD, max_length=200)
    role: str = "viewer"


class UserChange(BaseModel):
    display_name: Optional[str] = Field(None, max_length=100)
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=MIN_PASSWORD, max_length=200)


def _user_out(u) -> dict:
    return {
        "id": u.id, "username": u.username, "display_name": u.display_name, "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


def _session(user) -> dict:
    token = create_token(
        {"uid": user.id, "name": user.username, "role": user.role}, secret(), TOKEN_TTL_SECONDS
    )
    return {"token": token, "user": _user_out(user)}


@router.get("/auth/status")
async def auth_status(db: AsyncSession = Depends(get_db)):
    """Whether the first administrator still has to be created."""
    return {"setup_required": await UserRepository(db).count() == 0}


@router.post("/auth/setup", status_code=status.HTTP_201_CREATED)
async def setup_first_admin(body: NewUser, request: Request, db: AsyncSession = Depends(get_db)):
    """Create the first administrator. Only possible while there are no users."""
    repo = UserRepository(db)
    if await repo.count() > 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 관리자 계정이 있습니다")
    user = await repo.create(body.username.strip(), body.display_name.strip(), hash_password(body.password), "admin")
    await record(db, None, request, "setup", user.username, username=user.username)
    return _session(user)


@router.post("/auth/login")
async def login(body: Credentials, request: Request, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    user = await repo.get_by_username(body.username.strip())
    # The same message for "no such user" and "wrong password", so the answer
    # does not reveal which usernames exist.
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        await record(db, None, request, "login_failed", body.username[:60], username=body.username[:60])
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="아이디 또는 비밀번호가 올바르지 않습니다")
    await repo.touch_login(user)
    await record(db, None, request, "login", user.username, username=user.username)
    return _session(user)


@router.get("/auth/me")
async def me(user: CurrentUser = Depends(current_user)):
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role}


@router.get("/users", dependencies=[ADMIN])
async def list_users(db: AsyncSession = Depends(get_db)):
    return [_user_out(u) for u in await UserRepository(db).list_all()]


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: NewUser, request: Request, admin: CurrentUser = ADMIN, db: AsyncSession = Depends(get_db)
):
    if body.role not in ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="알 수 없는 역할입니다")
    repo = UserRepository(db)
    if await repo.get_by_username(body.username.strip()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"'{body.username}' 아이디가 이미 있습니다")
    user = await repo.create(body.username.strip(), body.display_name.strip(), hash_password(body.password), body.role)
    await record(db, admin, request, "user_create", user.username, role=user.role)
    return _user_out(user)


@router.patch("/users/{user_id}")
async def change_user(
    user_id: int, body: UserChange, request: Request, admin: CurrentUser = ADMIN,
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    user = await repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다")
    if body.role is not None and body.role not in ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="알 수 없는 역할입니다")

    losing_admin = user.role == "admin" and user.is_active and (
        (body.role is not None and body.role != "admin") or body.is_active is False
    )
    # Locking every administrator out would leave nobody able to fix it.
    if losing_admin and await repo.count_active_admins() <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="마지막 관리자는 바꿀 수 없습니다")

    changed = []
    if body.display_name is not None:
        user.display_name = body.display_name.strip()
        changed.append("display_name")
    if body.role is not None and body.role != user.role:
        user.role = body.role
        changed.append(f"role={body.role}")
    if body.is_active is not None and body.is_active != user.is_active:
        user.is_active = body.is_active
        changed.append(f"is_active={body.is_active}")
    if body.password:
        user.password_hash = hash_password(body.password)
        changed.append("password")
    await repo.save(user)
    await record(db, admin, request, "user_change", user.username, changed=changed)
    return _user_out(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int, request: Request, admin: CurrentUser = ADMIN, db: AsyncSession = Depends(get_db)
):
    """Delete an account for good. Its past audit entries stay, under its name."""
    repo = UserRepository(db)
    user = await repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다")

    reason = delete_block_reason(user, admin.id, await repo.count_active_admins())
    if reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

    username, role = user.username, user.role
    await repo.delete(user)
    await record(db, admin, request, "user_delete", username, role=role)


@router.get("/audit-log", dependencies=[ADMIN])
async def audit_log(
    username: Optional[str] = None,
    action: Optional[str] = None,
    days: Optional[int] = Query(None, ge=1, le=3650),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    rows = await AuditRepository(db).search(username, action, since, limit, offset)
    return [
        {
            "id": r.id, "at": r.at.isoformat(), "username": r.username, "role": r.role,
            "action": r.action, "target": r.target, "detail": r.detail, "ip": r.ip,
        }
        for r in rows
    ]
