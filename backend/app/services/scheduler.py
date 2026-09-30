"""The background loop: due reports every minute, expired uploads every hour."""
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from app.db.repositories.database_repo import DatabaseRepository
from app.db.repositories.reports import ReportRepository
from app.dependencies import AsyncSessionLocal
from app.services.excel_service import ExcelService
from app.services.report_service import run_report

TICK_SECONDS = 60
CLEANUP_EVERY_TICKS = 60

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
                state["last_tick"] = now.isoformat()
                state["last_error"] = None
            except Exception as exc:  # one bad tick must not end the loop
                state["last_error"] = str(exc)[:300]
            tick += 1
            await asyncio.sleep(tick_seconds)
    finally:
        state["running"] = False
