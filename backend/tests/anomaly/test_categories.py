"""The merchant categories present in the data, offered when choosing 주의 업종.

The watch list matches names exactly (spaces included: "볼 링 장"), so typing one
from memory can silently match nothing. Showing what the data really contains
lets the screen suggest and check names.
"""
import asyncio

from app.services.anomaly_service import AnomalyService


class FakePool:
    def __init__(self, by_view, fail=()):
        self.by_view, self.fail, self.sql = by_view, set(fail), []

    async def execute_query(self, database_id, sql, params=None):
        self.sql.append(sql)
        for view, rows in self.by_view.items():
            if f"FROM {view}" in sql:
                if view in self.fail:
                    raise RuntimeError("view missing")
                return rows
        return []


def run(pool):
    return asyncio.run(AnomalyService(pool, None).list_categories("1"))


def test_categories_come_with_their_counts_most_common_first():
    pool = FakePool({"v_approval": [{"name": "영화관", "n": 3}, {"name": "일반한식", "n": 50}]})
    assert run(pool) == [{"name": "일반한식", "count": 50}, {"name": "영화관", "count": 3}]


def test_the_same_name_in_two_sources_is_added_up():
    pool = FakePool({
        "v_approval": [{"name": "영화관", "n": 3}],
        "v_acquire": [{"name": "영화관", "n": 4}, {"name": "화   원", "n": 1}],
    })
    assert run(pool) == [{"name": "영화관", "count": 7}, {"name": "화   원", "count": 1}]


def test_names_are_returned_exactly_as_stored():
    pool = FakePool({"v_approval": [{"name": "볼 링 장", "n": 2}]})
    assert run(pool)[0]["name"] == "볼 링 장"


def test_a_source_that_cannot_be_read_is_skipped():
    pool = FakePool({"v_approval": [{"name": "영화관", "n": 3}], "v_acquire": []}, fail={"v_acquire"})
    assert run(pool) == [{"name": "영화관", "count": 3}]


def test_only_sources_that_have_a_category_column_are_asked():
    pool = FakePool({})
    run(pool)
    assert any("v_approval" in q for q in pool.sql) and not any("v_bill" in q for q in pool.sql)
