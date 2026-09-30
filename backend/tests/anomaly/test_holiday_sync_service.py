"""Running the sync: keep what came back, never lose what we had when a fetch
fails, and never show or return the service key.
"""
import asyncio
from datetime import datetime, timezone

import httpx

from app.anomaly.rules import TEMPLATES
from app.anomaly.settings import with_synced_holidays
from app.services.holiday_sync import run_sync, status_of


class FakeRepo:
    def __init__(self, key=None, days=None):
        self.key = key
        self.days = dict(days or {})
        self.sources = {}
        self.result = None

    async def service_key(self):
        return self.key

    async def replace_year(self, year, days, source):
        self.days = {d: n for d, n in self.days.items() if not d.startswith(f"{year}-")}
        self.days.update(days)
        self.sources[year] = source

    async def record(self, status, error, source):
        self.result = {"status": status, "error": error, "source": source}

    async def state(self):
        return {"key_saved": bool(self.key), "last_synced_at": None, "last_status": (self.result or {}).get("status"),
                "last_error": (self.result or {}).get("error"), "last_source": (self.result or {}).get("source")}

    async def synced(self):
        return dict(self.days)


ICS = "BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART;VALUE=DATE:20260701\nDTEND;VALUE=DATE:20260702\nSUMMARY:임시공휴일\nDESCRIPTION:공휴일\nEND:VEVENT\nEND:VCALENDAR\n"


def client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def run(coro):
    return asyncio.run(coro)


def sync(repo, handler, years=(2026,)):
    async def go():
        async with client(handler) as c:
            return await run_sync(repo, c, list(years))
    return run(go())


def test_a_successful_sync_stores_the_days_and_records_where_they_came_from():
    repo = FakeRepo()
    out = sync(repo, lambda r: httpx.Response(200, text=ICS))
    assert repo.days == {"2026-07-01": "임시공휴일"}
    assert repo.result["status"] == "ok" and repo.result["source"] == "google"
    assert out["last_status"] == "ok"


def test_a_failed_year_keeps_the_days_already_stored():
    repo = FakeRepo(days={"2026-07-01": "임시공휴일"})
    out = sync(repo, lambda r: httpx.Response(500))
    assert repo.days == {"2026-07-01": "임시공휴일"}  # not wiped by a bad answer
    assert repo.result["status"] == "error" and repo.result["error"]
    assert out["last_status"] == "error"


def test_a_successful_year_replaces_that_years_days_so_a_cancelled_one_disappears():
    repo = FakeRepo(days={"2026-06-30": "취소된 날", "2025-12-25": "성탄절"})
    sync(repo, lambda r: httpx.Response(200, text=ICS))
    assert "2026-06-30" not in repo.days and "2025-12-25" in repo.days


def test_one_good_year_and_one_bad_year_is_a_partial_result():
    repo = FakeRepo()

    def handler(request):
        return httpx.Response(200, text=ICS) if True else None

    # 2027 has nothing in the feed, so it fails while 2026 succeeds.
    out = sync(repo, handler, years=(2026, 2027))
    assert repo.result["status"] == "partial"
    assert "2027" in repo.result["error"]


def test_the_key_is_used_when_saved_and_never_appears_in_the_status():
    repo = FakeRepo(key="SECRET-KEY-123")
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, text=ICS)

    out = sync(repo, handler)
    assert any("SpcdeInfoService" in u for u in seen)  # the official source was tried first
    assert "SECRET-KEY-123" not in repr(out)
    assert out["key_saved"] is True


def test_status_reports_counts_without_a_key():
    repo = FakeRepo(days={"2026-07-01": "a", "2026-08-15": "b", "2027-01-01": "c"})
    out = run(status_of(repo))
    assert out["synced_count"] == 3 and out["synced_years"] == [2026, 2027]
    assert out["key_saved"] is False


# --- handing the received days to the rule --------------------------------------------------------------

def test_the_received_days_reach_only_the_off_hours_rule():
    out = with_synced_holidays(TEMPLATES, {"2026-07-01": "임시공휴일"})
    off = next(t for t in out if t.template == "OFF_HOURS")
    high = next(t for t in out if t.template == "HIGH_AMOUNT")
    assert off.params["synced_holidays"] == {"2026-07-01": "임시공휴일"}
    assert "synced_holidays" not in high.params


def test_the_original_templates_are_not_modified():
    with_synced_holidays(TEMPLATES, {"2026-07-01": "x"})
    off = next(t for t in TEMPLATES if t.template == "OFF_HOURS")
    assert "synced_holidays" not in off.params
