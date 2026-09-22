"""Anomaly detection endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.anomaly.rules import RULES
from app.db.repositories.anomaly import AnomalyRepository
from app.dependencies import get_db, get_db_pool
from app.services.anomaly_service import AnomalyService

router = APIRouter(prefix="/anomaly", tags=["Anomaly"])


def get_anomaly_service(
    db: AsyncSession = Depends(get_db),
    pool=Depends(get_db_pool),
) -> AnomalyService:
    return AnomalyService(pool, AnomalyRepository(db))


class ReviewRequest(BaseModel):
    database_id: str
    status: str
    fingerprint: str
    note: Optional[str] = None


@router.get("/findings")
async def list_findings(
    database_id: str = Query(...),
    rule_code: Optional[str] = None,
    status: Optional[str] = None,
    service: AnomalyService = Depends(get_anomaly_service),
):
    """Findings for one connection, with review state merged in."""
    return await service.list_findings(database_id, rule_code=rule_code, status=status)


@router.patch("/findings/{finding_key:path}/review")
async def review_finding(
    finding_key: str,
    request: ReviewRequest,
    db: AsyncSession = Depends(get_db),
):
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
