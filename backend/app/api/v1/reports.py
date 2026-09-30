"""
Saved reports: a question that runs on a schedule and keeps its last result.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import ANY_USER, CurrentUser, record
from app.auth.masking import mask_results
from app.auth.sql_visibility import can_see_sql, report_meta
from app.services.result_labels import ResultLabeler
from app.db.models import SavedReport
from app.db.repositories.history import HistoryRepository
from app.db.repositories.reports import ReportRepository
from app.dependencies import get_db, get_db_pool
from app.services.report_schedule import is_valid, next_run
from app.services.report_service import run_report
from app.utils.sql_validator import SQLValidator

router = APIRouter(prefix="/reports", tags=["Reports"])


class NewReport(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    question: str = Field(default="", max_length=2000)
    # Either the SQL, or the history record it came from: someone who cannot
    # read SQL saves a report by naming the record and the server looks it up.
    sql: Optional[str] = Field(None, min_length=1, max_length=20000)
    history_id: Optional[int] = None
    database_id: int
    frequency: str = "daily"
    hour: int = 9
    weekday: Optional[int] = None
    day: Optional[int] = None


class ReportChange(BaseModel):
    is_active: Optional[bool] = None


def _now() -> datetime:
    # The server's own zone: the hour a report is set to is the operators' local hour.
    return datetime.now().astimezone()


def _meta(r: SavedReport) -> dict:
    iso = lambda d: d.isoformat() if d else None
    return {
        "id": r.id, "name": r.name, "question": r.question, "sql": r.sql,
        "database_id": r.database_id, "frequency": r.frequency, "hour": r.run_hour,
        "weekday": r.run_weekday, "day": r.run_day, "is_active": r.is_active,
        "next_run_at": iso(r.next_run_at), "last_run_at": iso(r.last_run_at),
        "last_status": r.last_status, "last_error": r.last_error,
        "last_row_count": r.last_row_count, "created_by": r.created_by,
    }


async def _shown(report: SavedReport, user: CurrentUser, db: AsyncSession, pool) -> list:
    """The last result as this user may see it: card numbers masked, and Korean
    column names only unless they are an administrator."""
    rows = mask_results(report.last_results or [], user.role)
    if rows and not can_see_sql(user.role):
        rows = (await ResultLabeler.load(pool, db, report.database_id)).relabel(rows, report.sql)
    return rows


async def _get(repo: ReportRepository, report_id: int) -> SavedReport:
    report = await repo.get(report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="보고서를 찾을 수 없습니다")
    return report


@router.get("")
async def list_reports(user: CurrentUser = ANY_USER, db: AsyncSession = Depends(get_db)):
    return [report_meta(_meta(r), user.role) for r in await ReportRepository(db).list_all()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_report(body: NewReport, user: CurrentUser = ANY_USER, db: AsyncSession = Depends(get_db)):
    if not is_valid(body.frequency, body.hour, body.weekday, body.day):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="실행 일정이 올바르지 않습니다")
    sql = body.sql
    if body.history_id is not None:
        saved = await HistoryRepository(db).get_by_id(body.history_id)
        if saved is None or saved.status != "success":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="저장할 질문 결과를 찾을 수 없습니다")
        sql = saved.generated_sql
    elif user.role != "admin":
        # Someone who cannot read SQL has no business supplying it either.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="저장할 질문 결과를 골라 주세요")
    if not sql:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="저장할 SQL이 없습니다")
    if not SQLValidator().validate(sql)["is_safe"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="조회(SELECT)만 보고서로 저장할 수 있습니다")
    report = SavedReport(
        name=body.name.strip(), question=body.question, sql=sql, database_id=str(body.database_id),
        frequency=body.frequency, run_hour=body.hour, run_weekday=body.weekday, run_day=body.day,
        next_run_at=next_run(body.frequency, body.hour, _now(), body.weekday, body.day),
        created_by=user.username,
    )
    return report_meta(_meta(await ReportRepository(db).add(report)), user.role)


@router.get("/{report_id}")
async def get_report(
    report_id: int, user: CurrentUser = ANY_USER, db: AsyncSession = Depends(get_db), pool=Depends(get_db_pool)
):
    """The report and its last result, with card numbers masked for viewers."""
    report = await _get(ReportRepository(db), report_id)
    return {**report_meta(_meta(report), user.role), "results": await _shown(report, user, db, pool)}


@router.post("/{report_id}/run")
async def run_now(
    report_id: int, http_request: Request, user: CurrentUser = ANY_USER,
    db: AsyncSession = Depends(get_db), pool=Depends(get_db_pool),
):
    repo = ReportRepository(db)
    report = await _get(repo, report_id)
    await run_report(report, pool, _now())
    await repo.save(report)
    await record(db, user, http_request, "report_run", report.name, status=report.last_status, rows=report.last_row_count)
    return {**report_meta(_meta(report), user.role), "results": await _shown(report, user, db, pool)}


@router.patch("/{report_id}")
async def change_report(
    report_id: int, body: ReportChange, user: CurrentUser = ANY_USER, db: AsyncSession = Depends(get_db)
):
    repo = ReportRepository(db)
    report = await _get(repo, report_id)
    if body.is_active is not None:
        report.is_active = body.is_active
        if body.is_active:
            # Resuming must not fire for every slot missed while paused.
            report.next_run_at = next_run(report.frequency, report.run_hour, _now(), report.run_weekday, report.run_day)
    return report_meta(_meta(await repo.save(report)), user.role)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(report_id: int, user: CurrentUser = ANY_USER, db: AsyncSession = Depends(get_db)):
    repo = ReportRepository(db)
    report = await _get(repo, report_id)
    # Its author or an administrator; not any other signed-in user.
    if user.role != "admin" and report.created_by != user.username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="만든 사람이나 관리자만 삭제할 수 있습니다")
    await repo.delete(report_id)
