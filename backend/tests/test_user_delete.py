"""When a user may be deleted.

Deleting is permanent, so two accounts are protected: your own (an admin who
removes themselves mid-session is locked out) and the last active administrator
(nobody would be left to manage users).
"""
from types import SimpleNamespace

from app.auth.user_rules import delete_block_reason


def user(id_, role="viewer", active=True):
    return SimpleNamespace(id=id_, role=role, is_active=active)


def test_another_user_can_be_deleted():
    assert delete_block_reason(user(2), actor_id=1, active_admins=1) is None


def test_you_cannot_delete_yourself():
    assert "자기 자신" in delete_block_reason(user(1, "admin"), actor_id=1, active_admins=3)


def test_the_last_active_admin_cannot_be_deleted():
    assert "마지막 관리자" in delete_block_reason(user(2, "admin"), actor_id=1, active_admins=1)


def test_an_admin_can_be_deleted_while_another_remains():
    assert delete_block_reason(user(2, "admin"), actor_id=1, active_admins=2) is None


def test_a_disabled_admin_is_not_the_last_active_one():
    # Deleting a disabled admin removes nobody who could sign in.
    assert delete_block_reason(user(2, "admin", active=False), actor_id=1, active_admins=1) is None


def test_auditors_and_viewers_are_never_the_last_admin():
    for role in ("auditor", "viewer"):
        assert delete_block_reason(user(2, role), actor_id=1, active_admins=1) is None
