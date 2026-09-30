"""Anomaly detection endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.anomaly.holidays_kr import calendar as holiday_calendar, check_day
from app.anomaly.rules import RULES, SOURCES, TEMPLATES, build_rules
from app.anomaly.settings import apply_overrides, describe, validate, with_synced_holidays, without_defaults
from app.anomaly.settings_history import changes as settings_changes
from app.auth.deps import ADMIN, ANY_USER, AUDITOR, CurrentUser, record
from app.auth.sql_visibility import can_see_sql
from app.db.column_privacy import anonymize_detail, hide_rule_caveats
from app.services.result_labels import ResultLabeler
from app.db.repositories.anomaly_settings import AnomalySettingsRepository
from app.db.repositories.holidays import HolidayRepository
from app.db.repositories.anomaly import AnomalyRepository
from app.dependencies import get_db, get_db_pool
from app.services.anomaly_service import AnomalyService
from app.services.holiday_sync import run_sync, status_of

router = APIRouter(prefix="/anomaly", tags=["Anomaly"])

# A finding covers a handful of transactions; a large seq list would be someone
# using this as a bulk row reader rather than expanding a row.
MAX_DETAIL_SEQS = 50


async def get_anomaly_service(
    db: AsyncSession = Depends(get_db),
    pool=Depends(get_db_pool),
) -> AnomalyService:
    overrides = await AnomalySettingsRepository(db).load()
    synced = await HolidayRepository(db).synced()
    rules = None
    if overrides or synced:
        templates = apply_overrides(TEMPLATES, overrides)
        rules = build_rules(SOURCES, with_synced_holidays(templates, synced) if synced else templates)
    return AnomalyService(pool, AnomalyRepository(db), rules)


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Every editable threshold with its current value and its default."""
    overrides = await AnomalySettingsRepository(db).load()
    return {"rules": describe(TEMPLATES, overrides)}


@router.put("/settings")
async def save_settings(
    body: dict,
    http_request: Request,
    admin: CurrentUser = AUDITOR,
    db: AsyncSession = Depends(get_db),
):
    """Save edited thresholds (administrators and auditors). `body` is {template: {parameter: value}}; a value
    equal to the default is dropped, so resetting a field really resets it."""
    clean, errors = validate(body.get("overrides", {}))
    if errors:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=" · ".join(errors))

    kept = without_defaults(TEMPLATES, clean)
    await _store(db, admin, http_request, kept, "anomaly_settings")
    return {"rules": describe(TEMPLATES, kept)}


async def _store(db: AsyncSession, admin: CurrentUser, request: Request, kept: dict, action: str) -> list:
    """Save the settings and, if anything actually changed, keep a history entry
    (the values before and after, so an earlier state can be restored)."""
    repo = AnomalySettingsRepository(db)
    before = await repo.load()
    changed = settings_changes(TEMPLATES, before, kept)
    if not changed:
        return []
    await repo.save(kept)
    await repo.add_history(admin.username, before, kept, changed)
    await record(db, admin, request, action, "", changed=[f"{c['rule']} {c['label']}" for c in changed])
    return changed


def _history_out(entry) -> dict:
    return {
        "id": entry.id,
        "changed_at": entry.changed_at.isoformat(),
        "changed_by": entry.changed_by,
        "changes": entry.changes,
    }


@router.get("/settings/history")
async def settings_history(limit: int = Query(30, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    """Recent changes to the thresholds, newest first."""
    return [_history_out(e) for e in await AnomalySettingsRepository(db).history(limit)]


@router.post("/settings/history/{entry_id}/restore")
async def restore_settings(
    entry_id: int,
    http_request: Request,
    admin: CurrentUser = AUDITOR,
    db: AsyncSession = Depends(get_db),
):
    """Put the settings back as they were before that change.

    It is a new change like any other, so it shows in the history and can itself
    be undone.
    """
    repo = AnomalySettingsRepository(db)
    entry = await repo.get_history(entry_id)
    if entry is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="변경 이력을 찾을 수 없습니다")

    clean, errors = validate(entry.before or {})
    if errors:
        # The rules moved on since then; a value that no longer validates must not be restored.
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="그 시점의 값을 지금은 쓸 수 없습니다: " + " · ".join(errors),
        )
    kept = without_defaults(TEMPLATES, clean)
    changed = await _store(db, admin, http_request, kept, "anomaly_settings_restore")
    if not changed:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="이미 그 시점과 같은 값입니다")
    return {"rules": describe(TEMPLATES, kept), "changes": changed}


class HolidayPreview(BaseModel):
    """The holiday settings as they stand on screen (saved or not)."""
    year: int = Field(..., ge=2000, le=2100)
    auto_holidays: bool = True
    holidays: List[str] = []
    holiday_exceptions: List[str] = []


@router.post("/holidays")
async def holiday_preview(body: HolidayPreview, db: AsyncSession = Depends(get_db)):
    """The holidays that would apply in a year with these settings, so the
    administrator can see what "자동" brought in before saving."""
    clean, errors = validate({"OFF_HOURS": {"holidays": body.holidays, "holiday_exceptions": body.holiday_exceptions}})
    if errors:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=" · ".join(errors))
    off = clean.get("OFF_HOURS", {})
    synced = await HolidayRepository(db).synced()
    return {
        "year": body.year,
        "holidays": holiday_calendar(
            body.year, body.auto_holidays, off.get("holidays", []), off.get("holiday_exceptions", []), synced
        ),
    }


class HolidayCheck(BaseModel):
    """One date to look up, under the settings as they stand on screen."""
    date: str
    auto_holidays: bool = True
    holidays: List[str] = []
    holiday_exceptions: List[str] = []


@router.post("/holidays/check")
async def holiday_check(body: HolidayCheck, db: AsyncSession = Depends(get_db)):
    """Is this date counted as a holiday, and why (or why not)."""
    clean, errors = validate({"OFF_HOURS": {"holidays": [body.date], "holiday_exceptions": body.holiday_exceptions}})
    if errors:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="날짜는 YYYY-MM-DD 형식으로 입력하세요")
    extra, _ = validate({"OFF_HOURS": {"holidays": body.holidays}})
    synced = await HolidayRepository(db).synced()
    return check_day(
        body.date, body.auto_holidays, extra.get("OFF_HOURS", {}).get("holidays", []),
        clean["OFF_HOURS"].get("holiday_exceptions", []), synced,
    )


@router.get("/holidays/status")
async def holiday_status(db: AsyncSession = Depends(get_db)):
    """Where the holiday list comes from and how the last sync went (never the key)."""
    return await status_of(HolidayRepository(db))


@router.post("/holidays/sync")
async def holiday_sync_now(http_request: Request, user: CurrentUser = AUDITOR, db: AsyncSession = Depends(get_db)):
    """Fetch announced holidays now, instead of waiting for the daily run."""
    import httpx

    async with httpx.AsyncClient() as client:
        status = await run_sync(HolidayRepository(db), client)
    await record(db, user, http_request, "holiday_sync", "", status=status["last_status"], source=status["last_source"])
    return status


class ServiceKey(BaseModel):
    key: str = Field("", max_length=500)


@router.put("/holidays/service-key")
async def holiday_service_key(
    body: ServiceKey, http_request: Request, admin: CurrentUser = ADMIN, db: AsyncSession = Depends(get_db)
):
    """Save the 공공데이터포털 service key (encrypted), or forget it when blank.

    Administrators only: it is a secret. It is never sent back to the browser."""
    repo = HolidayRepository(db)
    await repo.set_key(body.key.strip() or None)
    await record(db, admin, http_request, "holiday_key", "", saved=bool(body.key.strip()))
    return await status_of(repo)


class ReviewRequest(BaseModel):
    """I1: finding_key travels in the body, never the URL path.

    The SPLIT_PAYMENT subject is `cardno|merchno|transdate`, so the key embeds a
    full 16-digit card number. In the path it would be written into proxy access
    logs, browser history and referrer headers by every hop in between.
    """

    database_id: str
    finding_key: str
    status: str
    fingerprint: str
    note: Optional[str] = None


@router.get("/sources")
async def list_sources(
    database_id: str = Query(...),
    service: AnomalyService = Depends(get_anomaly_service),
):
    """Sources this connection can actually be checked against, with their date range.

    Not every table is checkable: the rules are written against specific columns,
    so the catalogue decides the list. The screen seeds its date picker from the
    range returned here.
    """
    return {"sources": await service.list_sources(database_id)}


@router.get("/categories")
async def list_categories(
    database_id: str = Query(...),
    service: AnomalyService = Depends(get_anomaly_service),
):
    """The merchant categories in the data, to suggest and check 주의 업종 names."""
    return {"categories": await service.list_categories(database_id)}


@router.get("/findings")
async def list_findings(
    database_id: str = Query(...),
    template: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user: CurrentUser = ANY_USER,
    service: AnomalyService = Depends(get_anomaly_service),
):
    """Findings for one connection, with review state merged in.

    Omitting `source` checks every source at once. `template` filters by the
    kind of rule (고액 결제), not by its source-specific code, so the screen's
    filter keeps meaning the same thing when 점검대상 changes.
    """
    if source is not None and source not in SOURCES:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown source: {source}",
        )

    try:
        found = await service.list_findings(
            database_id,
            template=template,
            status=status,
            source=source,
            date_from=date_from,
            date_to=date_to,
        )
        if not can_see_sql(user.role):
            found["applicable_rules"] = hide_rule_caveats(found["applicable_rules"])
        return found
    except ValueError as exc:
        # A malformed or inverted period is a caller bug, not a server fault.
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )


@router.get("/findings/transactions")
async def finding_transactions(
    database_id: str = Query(...),
    source: str = Query("approval"),
    seq: List[int] = Query(default=[]),
    user: CurrentUser = ANY_USER,
    service: AnomalyService = Depends(get_anomaly_service),
    db: AsyncSession = Depends(get_db),
    pool=Depends(get_db_pool),
):
    """Full approvals behind one finding, fetched only when a reviewer expands it.

    Unlike the list endpoint this carries the card number, so it stays a
    separate deliberate request rather than riding along with every page load.
    """
    if len(seq) > MAX_DETAIL_SEQS:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"at most {MAX_DETAIL_SEQS} transactions per request",
        )

    if source not in SOURCES:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown source: {source}",
        )

    detail = await service.get_transactions(database_id, source, seq)
    if not can_see_sql(user.role):
        # The detail names raw columns; everyone but an administrator gets Korean names.
        labels = (await ResultLabeler.load(pool, db, database_id)).labels_of(SOURCES[source].view)
        detail = [anonymize_detail(d, labels) for d in detail]
    return {"transactions": detail}


@router.patch("/findings/review")
async def review_finding(
    request: ReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    finding_key = request.finding_key
    if request.status not in ("confirmed", "dismissed"):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="status must be 'confirmed' or 'dismissed'",
        )

    rule_code = finding_key.split(":", 1)[0]
    if rule_code not in {r.code for r in RULES}:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown rule in finding_key: {rule_code}",
        )

    review = await AnomalyRepository(db).upsert_review(
        database_id=request.database_id,
        finding_key=finding_key,
        rule_code=rule_code,
        status=request.status,
        fingerprint=request.fingerprint,
        note=request.note,
    )

    return {
        "finding_key": review.finding_key,
        "status": review.status,
        "note": review.note,
        "reviewed_at": review.reviewed_at.isoformat(),
    }
