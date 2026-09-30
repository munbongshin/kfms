"""Announced holidays from outside the program, so a newly declared 임시공휴일
is picked up without waiting for the built-in calendar to be updated.

Order: the official 공공데이터포털 특일정보 (needs a free service key), and if
there is no key or it fails, Google's public 대한민국 holiday calendar. Both are
fetched through an injected HTTP client; nothing here reads the database.
"""
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

import httpx

KASI_URL = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"
ICAL_URL = (
    "https://calendar.google.com/calendar/ical/"
    "ko.south_korea%23holiday%40group.v.calendar.google.com/public/basic.ics"
)
TIMEOUT_SECONDS = 20

# Result codes of the portal that mean the service key is the problem.
_KEY_CODES = {"30", "31", "32", "33"}


class SourceError(Exception):
    """A source could not be used; the message is safe to show on screen."""


def _iso(locdate: Any) -> str:
    text = str(locdate)
    return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"


# --- official source ----------------------------------------------------------------------------

def parse_kasi(payload: Any) -> Dict[str, str]:
    """ISO date -> name for the days the answer marks as holidays."""
    try:
        response = payload["response"]
        header, body = response["header"], response["body"]
    except (KeyError, TypeError):
        raise SourceError("공공데이터포털 응답을 해석하지 못했습니다")

    code = str(header.get("resultCode", ""))
    if code != "00":
        message = str(header.get("resultMsg", "")) or f"오류 코드 {code}"
        hint = " — 서비스키를 확인하세요" if code in _KEY_CODES or "KEY" in message.upper() else ""
        raise SourceError(f"공공데이터포털 응답: {message}{hint}")

    items = (body.get("items") or {}) if isinstance(body, dict) else {}
    found = items.get("item") if isinstance(items, dict) else None
    if found is None:
        return {}
    if isinstance(found, dict):  # one holiday arrives as an object, several as a list
        found = [found]

    days: Dict[str, str] = {}
    for entry in found:
        if str(entry.get("isHoliday", "")).upper() == "Y":
            days[_iso(entry["locdate"])] = str(entry.get("dateName", "")).strip()
    return days


async def fetch_kasi(client: httpx.AsyncClient, service_key: str, year: int) -> Dict[str, str]:
    # The portal hands out an "Encoding" and a "Decoding" key. Decoding first makes
    # either one work, since the client encodes the parameter itself.
    params = {"solYear": str(year), "ServiceKey": unquote(service_key), "numOfRows": "100", "_type": "json"}
    try:
        response = await client.get(KASI_URL, params=params, timeout=TIMEOUT_SECONDS)
    except httpx.HTTPError:
        raise SourceError("공공데이터포털에 연결하지 못했습니다")
    if response.status_code in (401, 403):
        # The portal answers a wrong, expired or not-yet-active key with 401/403.
        raise SourceError(f"공공데이터포털이 서비스키를 받아 주지 않았습니다 (HTTP {response.status_code}) — 서비스키를 확인하세요. 발급 직후에는 활성화까지 시간이 걸릴 수 있습니다")
    if response.status_code != 200:
        raise SourceError(f"공공데이터포털이 오류로 응답했습니다 (HTTP {response.status_code})")
    try:
        payload = response.json()
    except ValueError:
        # An unregistered key is answered with an XML error page rather than JSON.
        raise SourceError("공공데이터포털 응답을 읽지 못했습니다 — 서비스키를 확인하세요")
    return parse_kasi(payload)


# --- calendar feed ------------------------------------------------------------------------------

def _unescape(text: str) -> str:
    return text.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ").replace("\\\\", "\\")


def _field(event: str, name: str) -> Optional[str]:
    match = re.search(rf"^{name}[^:\r\n]*:(.*)$", event, re.M)
    return match.group(1).strip() if match else None


def _day(value: Optional[str]) -> Optional[date]:
    if value and re.fullmatch(r"\d{8}", value):
        return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    return None


def parse_ical(text: str, year: int) -> Dict[str, str]:
    """ISO date -> name for public holidays of `year` in an iCalendar feed.

    Google marks public holidays and other observances differently in the
    description; only the former count. A feed that never describes its events
    is taken as it comes.
    """
    if "BEGIN:VCALENDAR" not in text and "BEGIN:VEVENT" not in text:
        raise SourceError("공휴일 캘린더를 받지 못했습니다 (형식이 달랐습니다)")

    unfolded = re.sub(r"\r?\n[ \t]", "", text)
    events = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", unfolded, re.S)
    described = any(_field(e, "DESCRIPTION") for e in events)

    days: Dict[str, str] = {}
    for event in events:
        if described:
            description = (_field(event, "DESCRIPTION") or "").lower()
            if "공휴일" not in description and "public holiday" not in description:
                continue
        start = _day(_field(event, "DTSTART"))
        if start is None:
            continue
        end = _day(_field(event, "DTEND")) or start + timedelta(days=1)  # DTEND is exclusive
        name = _unescape(_field(event, "SUMMARY") or "").strip()
        day = start
        while day < end:
            if day.year == year:
                days[day.isoformat()] = name
            day += timedelta(days=1)
    return days


async def fetch_ical(client: httpx.AsyncClient, year: int) -> Dict[str, str]:
    try:
        response = await client.get(ICAL_URL, timeout=TIMEOUT_SECONDS, follow_redirects=True)
    except httpx.HTTPError:
        raise SourceError("공휴일 캘린더(구글)에 연결하지 못했습니다")
    if response.status_code != 200:
        raise SourceError(f"공휴일 캘린더(구글)가 오류로 응답했습니다 (HTTP {response.status_code})")
    return parse_ical(response.text, year)


# --- putting them together -------------------------------------------------------------------------

async def _one_year(client: httpx.AsyncClient, service_key: Optional[str], year: int) -> Dict[str, Any]:
    official_problem = ""
    if service_key:
        try:
            days = await fetch_kasi(client, service_key, year)
            if days:
                return {"year": year, "ok": True, "source": "official", "count": len(days), "days": days, "error": ""}
            official_problem = "공식 출처가 공휴일을 돌려주지 않았습니다"
        except SourceError as exc:
            official_problem = f"공식 출처 실패: {exc}"

    try:
        days = await fetch_ical(client, year)
        if days:
            return {"year": year, "ok": True, "source": "google", "count": len(days), "days": days,
                    "error": f"{official_problem} — 구글 캘린더로 대신 받았습니다" if official_problem else ""}
        problem = "구글 캘린더에서 받은 공휴일이 없습니다"
    except SourceError as exc:
        problem = str(exc)

    return {"year": year, "ok": False, "source": "", "count": 0, "days": {},
            "error": " / ".join(p for p in (official_problem, problem) if p)}


async def sync_years(years: List[int], service_key: Optional[str], client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """One result per year: ok, where it came from, how many days, and the days."""
    return [await _one_year(client, service_key, year) for year in years]
