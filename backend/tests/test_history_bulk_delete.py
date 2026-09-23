"""The bulk delete must never take a bookmarked row with it.

A bookmark is the user saying "I run this again", so clearing history is not
allowed to destroy one. These check the statement the repository builds rather
than hitting a database, so the guard is pinned even if the query is rewritten.
"""
from app.db.models import QueryHistory
from app.db.repositories.history import build_clear_statement


def compiled(keep_bookmarked: bool) -> str:
    return str(build_clear_statement(keep_bookmarked))


def test_clearing_everything_touches_the_history_table():
    assert "DELETE FROM query_history" in compiled(keep_bookmarked=False)


def test_clearing_everything_has_no_condition():
    assert "WHERE" not in compiled(keep_bookmarked=False)


def test_keeping_bookmarks_excludes_them_in_the_statement():
    sql = compiled(keep_bookmarked=True)
    assert "WHERE" in sql
    assert "is_bookmarked" in sql


def test_the_guard_is_the_default():
    # A caller that forgets the flag must not wipe bookmarks.
    assert "is_bookmarked" in str(build_clear_statement())


def test_the_statement_targets_the_model_the_repository_uses():
    assert build_clear_statement(True).table.name == QueryHistory.__tablename__
