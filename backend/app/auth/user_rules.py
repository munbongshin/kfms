"""Rules for managing users."""
from typing import Any, Optional


def delete_block_reason(target: Any, actor_id: int, active_admins: int) -> Optional[str]:
    """Why `target` must not be deleted, or None if it may be."""
    if target.id == actor_id:
        return "자기 자신은 삭제할 수 없습니다"
    # Only an admin who can still sign in counts as one left to manage users.
    if target.role == "admin" and target.is_active and active_admins <= 1:
        return "마지막 관리자는 삭제할 수 없습니다"
    return None


def username_key(name: str) -> str:
    """How usernames are compared: Kim and kim are the same person's id."""
    return name.strip().lower()


def password_change_problem(current_ok: bool, current: str, new: str) -> Optional[str]:
    """Why a self-service password change must be refused, or None."""
    if not current_ok:
        return "현재 비밀번호가 올바르지 않습니다"
    if new == current:
        return "새 비밀번호가 현재 비밀번호와 같습니다"
    return None
