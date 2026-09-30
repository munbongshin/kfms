"""The background loop: due reports every minute, expired uploads every hour."""
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from app.config import settings
from app.db.repositories.database_repo import DatabaseRepository
from app.db.repositories.holidays import HolidayRepository
from app.db.repositories.reports import ReportRepository
from app.dependencies import AsyncSessionLocal
from app.services.excel_service import ExcelService
from app.services.holiday_sync import run_sync
from app.services.report_service import run_report

TICK_SECONDS = 60
CLEANUP_EVERY_TICKS = 60
# Announced holidays are fetched about a minute after start-up and then once a day.
HOLIDAY_SYNC_EVERY_TICKS = 24 * 60

# What /health reports about the loop.
state: Dict[str, Any] = {"running": False, "last_tick": None, "last_error": None, "reports_run": 0}


async def run_due_reports(pool: Any, now: datetime) -> int:
    ran = 0
    async with AsyncSessionLocal() as session:
        repo = ReportRepository(session)
        for report in await repo.due(now):
            await run_report(report, pool, now)
            await repo.save(report)
            ran += 1
    return ran


async def cleanup_expired_uploads(pool: Any) -> int:
    async with AsyncSessionLocal() as session:
        connections = await DatabaseRepository(session).get_all(active_only=True)
        return await ExcelService(session, pool).cleanup_expired_everywhere([str(c.id) for c in connections])


async def sync_announced_holidays() -> None:
    """Fetch announced holidays. A failure is recorded by the sync itself and
    must never stop the loop, so an unreachable network only shows in the status."""
    async with AsyncSessionLocal() as session:
        async with httpx.AsyncClient() as client:
            await run_sync(HolidayRepository(session), client)


async def scheduler_loop(pool: Any, tick_seconds: int = TICK_SECONDS) -> None:
    state["running"] = True
    tick = 0
    try:
        while True:
            try:
                now = datetime.now().astimezone()
                state["reports_run"] += await run_due_reports(pool, now)
                if tick % CLEANUP_EVERY_TICKS == 0:
                    await cleanup_expired_uploads(pool)
                if settings.HOLIDAY_SYNC_ENABLED and tick % HOLIDAY_SYNC_EVERY_TICKS == 1:
                    try:
                        await sync_announced_holidays()
                    except Exception as exc:
                        state["last_error"] = f"holiday sync: {str(exc)[:200]}"
                state["last_tick"] = now.isoformat()
                state["last_error"] = None
            except Exception as exc:  # one bad tick must not end the loop
                state["last_error"] = str(exc)[:300]
            tick += 1
            await asyncio.sleep(tick_seconds)
    finally:
        state["running"] = False
