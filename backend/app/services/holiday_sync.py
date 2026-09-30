"""Fetching announced holidays and keeping them, so the off-hours rule knows
about a 임시공휴일 declared after the built-in calendar was made.

A year's stored days are replaced only when that year was fetched successfully;
a failed fetch leaves what was already there untouched.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.anomaly.holiday_sources import sync_years
from app.anomaly.holidays_kr import calendar_version


async def status_of(repo: Any) -> Dict[str, Any]:
    """What the screen shows about the sync. The service key itself is never included."""
    state = await repo.state()
    synced = await repo.synced()
    return {
        **state,
        "synced_count": len(synced),
        "synced_years": sorted({int(day[:4]) for day in synced}),
        "package_version": calendar_version(),
    }


async def run_sync(repo: Any, client: httpx.AsyncClient, years: Optional[List[int]] = None) -> Dict[str, Any]:
    """Sync this year and next (or `years`), record the outcome, and return the status."""
    if years is None:
        this_year = datetime.now().year
        years = [this_year, this_year + 1]

    results = await sync_years(years, await repo.service_key(), client)

    for result in results:
        if result["ok"]:
            await repo.replace_year(result["year"], result["days"], result["source"])

    good = [r for r in results if r["ok"]]
    bad = [r for r in results if not r["ok"]]
    notes = [f"{r['year']}년: {r['error']}" for r in results if r["error"]]

    if not bad:
        status = "ok"
    elif good:
        status = "partial"
    else:
        status = "error"
    # The source that supplied the most recent good year; the screen names it.
    source = good[-1]["source"] if good else ""
    await repo.record(status, " / ".join(notes), source)
    return await status_of(repo)
