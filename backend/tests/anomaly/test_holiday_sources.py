"""Getting announced holidays (임시공휴일 included) from outside.

Official source first (공공데이터포털 특일정보, needs a service key); without a
key, or if it fails, Google's public 대한민국 holiday calendar. Both are
fetched with an injected HTTP client so nothing here touches the network.
"""
import asyncio

import httpx
import pytest

from app.anomaly.holiday_sources import (
    SourceError,
    fetch_ical,
    fetch_kasi,
    parse_ical,
    parse_kasi,
    sync_years,
)


def item(name, locdate, holiday="Y"):
    return {"dateKind": "01", "dateName": name, "isHoliday": holiday, "locdate": locdate, "seq": 1}


def kasi_payload(items, code="00", msg="NORMAL SERVICE."):
    body = {"items": {"item": items} if items else "", "numOfRows": 100, "pageNo": 1, "totalCount": len(items or [])}
    return {"response": {"header": {"resultCode": code, "resultMsg": msg}, "body": body}}


# --- official source ---------------------------------------------------------------------------------

def test_kasi_holidays_are_read_by_date():
    days = parse_kasi(kasi_payload([item("1월1일", 20260101), item("설날", 20260217)]))
    assert days == {"2026-01-01": "1월1일", "2026-02-17": "설날"}


def test_kasi_a_single_item_arrives_as_an_object_not_a_list():
    assert parse_kasi(kasi_payload(item("임시공휴일", 20261002))) == {"2026-10-02": "임시공휴일"}


def test_kasi_days_that_are_not_holidays_are_ignored():
    days = parse_kasi(kasi_payload([item("어버이날", 20260508, holiday="N"), item("광복절", 20260815)]))
    assert days == {"2026-08-15": "광복절"}


def test_kasi_no_items_is_an_empty_result():
    assert parse_kasi(kasi_payload(None)) == {}


def test_kasi_an_error_code_is_reported_with_its_message():
    with pytest.raises(SourceError) as err:
        parse_kasi(kasi_payload(None, code="30", msg="SERVICE KEY IS NOT REGISTERED ERROR."))
    assert "서비스키" in str(err.value)


def test_kasi_an_unexpected_body_is_an_error_not_a_crash():
    with pytest.raises(SourceError):
        parse_kasi({"nothing": "useful"})


# --- calendar feed -----------------------------------------------------------------------------------------

ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART;VALUE=DATE:20261005
DTEND;VALUE=DATE:20261006
SUMMARY:개천절 대체공휴일
DESCRIPTION:공휴일
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260508
DTEND;VALUE=DATE:20260509
SUMMARY:어버이날
DESCRIPTION:기념일
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260924
DTEND;VALUE=DATE:20260927
SUMMARY:추석
DESCRIPTION:공휴일
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20270101
DTEND;VALUE=DATE:20270102
SUMMARY:신정
DESCRIPTION:공휴일
END:VEVENT
END:VCALENDAR
"""


def test_ical_public_holidays_are_read_and_observances_left_out():
    days = parse_ical(ICS, 2026)
    assert days["2026-10-05"] == "개천절 대체공휴일"
    assert "2026-05-08" not in days


def test_ical_a_multi_day_event_covers_each_day():
    days = parse_ical(ICS, 2026)
    assert {"2026-09-24", "2026-09-25", "2026-09-26"} <= set(days)


def test_ical_only_the_asked_year_is_returned():
    assert "2027-01-01" not in parse_ical(ICS, 2026)
    assert set(parse_ical(ICS, 2027)) == {"2027-01-01"}


def test_ical_folded_lines_and_escaped_commas_are_undone():
    text = "BEGIN:VEVENT\r\nDTSTART;VALUE=DATE:20260101\r\nSUMMARY:신정\\, 새해\r\n 첫날\r\nDESCRIPTION:공휴일\r\nEND:VEVENT\r\n"
    assert parse_ical(text, 2026) == {"2026-01-01": "신정, 새해첫날"}


def test_ical_a_feed_that_never_says_what_kind_of_day_keeps_everything():
    text = "BEGIN:VEVENT\nDTSTART;VALUE=DATE:20260815\nSUMMARY:광복절\nEND:VEVENT\n"
    assert parse_ical(text, 2026) == {"2026-08-15": "광복절"}


def test_ical_something_that_is_not_a_calendar_is_an_error():
    with pytest.raises(SourceError):
        parse_ical("<html>blocked</html>", 2026)


# --- fetching -----------------------------------------------------------------------------------------------------

def client_for(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def run(coro):
    return asyncio.run(coro)


def test_the_official_call_sends_the_year_and_a_decoded_key():
    seen = {}

    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=kasi_payload([item("광복절", 20260815)]))

    async def go():
        async with client_for(handler) as c:
            return await fetch_kasi(c, "abc%2Bdef%3D%3D", 2026)

    assert run(go()) == {"2026-08-15": "광복절"}
    assert seen["params"]["solYear"] == "2026"
    # An "Encoding" key copied from the portal is decoded first, so it is not encoded twice.
    assert seen["params"]["ServiceKey"] == "abc+def=="


def test_the_official_call_fails_cleanly_on_a_bad_status():
    async def go():
        async with client_for(lambda r: httpx.Response(500, text="boom")) as c:
            await fetch_kasi(c, "k", 2026)

    with pytest.raises(SourceError):
        run(go())


def test_the_official_call_fails_cleanly_when_the_answer_is_not_json():
    async def go():
        async with client_for(lambda r: httpx.Response(200, text="<OpenAPI_ServiceResponse>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</OpenAPI_ServiceResponse>")) as c:
            await fetch_kasi(c, "k", 2026)

    with pytest.raises(SourceError) as err:
        run(go())
    assert "서비스키" in str(err.value)


def test_a_network_failure_is_a_source_error():
    def handler(request):
        raise httpx.ConnectError("no route")

    async def go():
        async with client_for(handler) as c:
            await fetch_ical(c, 2026)

    with pytest.raises(SourceError) as err:
        run(go())
    assert "연결" in str(err.value)


# --- the order of sources -----------------------------------------------------------------------------------------

def routing(kasi=None, ical=None):
    """A client whose two endpoints answer as given (a status/body pair, or None to fail)."""
    def handler(request):
        if "SpcdeInfoService" in str(request.url):
            return kasi(request) if callable(kasi) else httpx.Response(500)
        return ical(request) if callable(ical) else httpx.Response(500)
    return client_for(handler)


def official_ok(request):
    return httpx.Response(200, json=kasi_payload([item("광복절", 20260815), item("임시공휴일", 20261002)]))


def calendar_ok(request):
    return httpx.Response(200, text=ICS)


def test_with_a_key_the_official_source_is_used():
    async def go():
        async with routing(kasi=official_ok, ical=calendar_ok) as c:
            return await sync_years([2026], "key", c)

    result = run(go())
    assert result[0]["source"] == "official" and result[0]["ok"] and result[0]["count"] == 2
    assert "2026-10-02" in result[0]["days"]


def test_without_a_key_the_calendar_feed_is_used():
    async def go():
        async with routing(ical=calendar_ok) as c:
            return await sync_years([2026], None, c)

    result = run(go())
    assert result[0]["source"] == "google" and result[0]["ok"]
    assert "2026-10-05" in result[0]["days"]


def test_if_the_official_source_fails_the_calendar_feed_takes_over_and_says_so():
    async def go():
        async with routing(kasi=lambda r: httpx.Response(500), ical=calendar_ok) as c:
            return await sync_years([2026], "key", c)

    result = run(go())[0]
    assert result["source"] == "google" and result["ok"]
    assert "공식" in result["error"]  # why the official source was not used


def test_if_everything_fails_the_year_is_not_ok_and_has_no_days():
    async def go():
        async with routing() as c:
            return await sync_years([2026], "key", c)

    result = run(go())[0]
    assert result["ok"] is False and result["days"] == {} and result["error"]


def test_an_empty_answer_is_a_failure_because_no_year_has_no_holidays():
    async def go():
        async with routing(kasi=lambda r: httpx.Response(200, json=kasi_payload(None)), ical=calendar_ok) as c:
            return await sync_years([2026], "key", c)

    result = run(go())[0]
    assert result["source"] == "google"  # the empty official answer was not trusted


def test_each_year_is_synced_on_its_own():
    async def go():
        async with routing(kasi=official_ok) as c:
            return await sync_years([2026, 2027], "key", c)

    assert [r["year"] for r in run(go())] == [2026, 2027]


def test_a_rejected_key_is_named_as_the_problem():
    async def go():
        async with client_for(lambda r: httpx.Response(403, text="Forbidden")) as c:
            await fetch_kasi(c, "bad", 2026)

    with pytest.raises(SourceError) as err:
        run(go())
    assert "서비스키" in str(err.value) and "403" in str(err.value)
