"""Rules for editing a database connection.

Renaming must not disturb the live pool, and no connection may point at the
app's own metadata database: it holds every connection's credentials, so a
text2sql question must never be able to read it.
"""
from app.services.connection_rules import is_metadata_database, needs_pool_refresh

META = "postgresql+asyncpg://postgres:secret@localhost:5434/kfms?ssl=disable"


def test_a_rename_leaves_the_pool_alone():
    assert needs_pool_refresh({"name": "KFMS Demo DB"}) is False


def test_new_credentials_rebuild_the_engine():
    assert needs_pool_refresh({"password": "x"}) is True


def test_moving_the_connection_rebuilds_the_engine():
    for field in ("host", "port", "database", "username"):
        assert needs_pool_refresh({field: "x"}) is True, field


def test_read_only_and_active_changes_rebuild_the_engine():
    # Read-only is set when the engine is created, so it only takes effect then.
    assert needs_pool_refresh({"is_read_only": False}) is True
    assert needs_pool_refresh({"is_active": False}) is True


def test_nothing_changed_needs_nothing():
    assert needs_pool_refresh({}) is False


def test_the_metadata_database_is_recognised():
    assert is_metadata_database("localhost", 5434, "kfms", META) is True


def test_loopback_spellings_count_as_the_same_host():
    assert is_metadata_database("127.0.0.1", 5434, "kfms", META) is True


def test_the_data_database_on_the_same_server_is_allowed():
    assert is_metadata_database("localhost", 5434, "retail", META) is False


def test_a_same_named_database_on_another_server_is_allowed():
    assert is_metadata_database("10.1.10.5", 5432, "kfms", META) is False
