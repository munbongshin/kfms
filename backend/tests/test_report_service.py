"""Running a saved report and cleaning up expired uploads."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.report_service import MAX_STORED_ROWS, run_report

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 30, 9, 0, tzinfo=KST)


class Pool:
    def __init__(self, rows=None, error=None):
        self.rows, self.error, self.ran = rows or [], error, []

    async def execute_query(self, database_id, sql, params=None):
        self.ran.append(sql)
        if self.error:
            raise RuntimeError(self.error)
        return self.rows


def report(sql="SELECT 1 AS n", frequency="daily", hour=9, **kw):
    base = dict(
        id=1, name="r", question="q", sql=sql, database_id="1",
        frequency=frequency, run_hour=hour, run_weekday=None, run_day=None,
        is_active=True, next_run_at=NOW, last_run_at=None, last_status=None,
        last_error=None, last_row_count=None, last_results=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def run(r, pool):
    return asyncio.run(run_report(r, pool, NOW))


def test_a_successful_run_keeps_the_rows_and_the_time():
    r = report()
    run(r, Pool(rows=[{"n": 1}]))
    assert r.last_status == "ok"
    assert r.last_results == [{"n": 1}]
    assert r.last_row_count == 1
    assert r.last_run_at == NOW
    assert r.last_error is None


def test_the_next_run_moves_ahead_of_now():
    r = report()
    run(r, Pool(rows=[]))
    assert r.next_run_at > NOW


def test_only_the_first_rows_are_stored_but_the_count_is_true():
    r = report()
    run(r, Pool(rows=[{"n": i} for i in range(MAX_STORED_ROWS + 50)]))
    assert len(r.last_results) == MAX_STORED_ROWS
    assert r.last_row_count == MAX_STORED_ROWS + 50


def test_a_database_error_is_recorded_not_raised():
    r = report()
    run(r, Pool(error='column "x" does not exist'))
    assert r.last_status == "error"
    assert 'column "x" does not exist' in r.last_error
    assert r.last_results is None


def test_a_failed_run_still_schedules_the_next_one():
    # Retrying every minute forever would hammer a broken query.
    r = report()
    run(r, Pool(error="boom"))
    assert r.next_run_at > NOW


def test_an_unsafe_sql_is_never_sent_to_the_database():
    pool = Pool()
    r = report(sql="DROP TABLE t")
    run(r, pool)
    assert pool.ran == []
    assert r.last_status == "error"


def test_a_limit_is_enforced():
    pool = Pool()
    run(report(sql="SELECT n FROM t"), pool)
    assert "LIMIT" in pool.ran[0].upper()
