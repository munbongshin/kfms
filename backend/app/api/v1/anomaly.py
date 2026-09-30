"""Anomaly detection endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status as http_status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.anomaly.rules import RULES, SOURCES, TEMPLATES, build_rules
from app.anomaly.settings import apply_overrides, describe, validate
from app.auth.deps import ADMIN, CurrentUser, record
from app.db.repositories.anomaly_settings import AnomalySettingsRepository
from app.db.repositories.anomaly import AnomalyRepository
from app.dependencies import get_db, get_db_pool
from app.services.anomaly_service import AnomalyService

router = APIRouter(prefix="/anomaly", tags=["Anomaly"])

# A finding covers a handful of transactions; a large seq list would be someone
# using this as a bulk row reader rather than expanding a row.
MAX_DETAIL_SEQS = 50


async def get_anomaly_service(
    db: AsyncSession = Depends(get_db),
    pool=Depends(get_db_pool),
) -> AnomalyService:
    overrides = await AnomalySettingsRepository(db).load()
    rules = build_rules(SOURCES, apply_overrides(TEMPLATES, overrides)) if overrides else None
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
    admin: CurrentUser = ADMIN,
    db: AsyncSession = Depends(get_db),
):
    """Save edited thresholds. `body` is {template: {parameter: value}}; a value
    equal to the default is dropped, so resetting a field really resets it."""
    clean, errors = validate(body.get("overrides", {}))
    if errors:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=" · ".join(errors))

    defaults = describe(TEMPLATES, {})
    kept = {}
    for rule in defaults:
        for param in rule["params"]:
            value = (clean.get(rule["template"]) or {}).get(param["key"])
            if value is None:
                continue
            comparable = int(value) if param["unit"] == "hour" else value
            if comparable != param["default"]:
                kept.setdefault(rule["template"], {})[param["key"]] = value

    await AnomalySettingsRepository(db).save(kept)
    await record(db, admin, http_request, "anomaly_settings", "", changed=sorted(kept))
    return {"rules": describe(TEMPLATES, kept)}


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


@router.get("/findings")
async def list_findings(
    database_id: str = Query(...),
    template: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
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
        return await service.list_findings(
            database_id,
            template=template,
            status=status,
            source=source,
            date_from=date_from,
            date_to=date_to,
        )
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
    service: AnomalyService = Depends(get_anomaly_service),
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

    return {"transactions": await service.get_transactions(database_id, source, seq)}


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
