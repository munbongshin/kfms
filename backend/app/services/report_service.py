"""Running saved reports."""
from datetime import datetime
from typing import Any

from app.config import settings
from app.services.report_schedule import next_run
from app.utils.sql_validator import SQLValidator

MAX_STORED_ROWS = 200


async def run_report(report: Any, pool: Any, now: datetime) -> None:
    """Run one report and record the outcome on it.

    A failure is recorded, not raised: one broken report must not stop the
    others, and the next run is scheduled either way so a broken query is tried
    again at its next slot rather than every minute.
    """
    validator = SQLValidator()
    try:
        check = validator.validate(report.sql)
        if not check["is_safe"]:
            raise ValueError("이 SQL은 안전 검사를 통과하지 못해 실행하지 않았습니다")
        sql = validator.enforce_limit(report.sql, settings.QUERY_RESULT_LIMIT)
        rows = await pool.execute_query(report.database_id, sql)
        report.last_status = "ok"
        report.last_error = None
        report.last_row_count = len(rows)
        report.last_results = rows[:MAX_STORED_ROWS]
    except Exception as exc:
        report.last_status = "error"
        report.last_error = str(exc).strip().splitlines()[0][:500] if str(exc).strip() else "오류"
        report.last_row_count = None
        report.last_results = None

    report.last_run_at = now
    report.next_run_at = next_run(
        report.frequency, report.run_hour, now, report.run_weekday, report.run_day
    )
