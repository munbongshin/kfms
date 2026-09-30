"""
Accuracy evaluation: a set of questions with known-correct SQL, scored against
whichever LLM is currently chosen.
"""
import asyncio
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import ADMIN, CurrentUser, record
from app.config import settings
from app.db.models import EvalCase, EvalRun
from app.db.repositories.database_repo import DatabaseRepository
from app.db.repositories.eval import EvalRepository
from app.db.repositories.glossary import GlossaryRepository
from app.db.repositories.history import HistoryRepository
from app.db.repositories.llm_settings import LLMSettingsRepository
from app.dependencies import AsyncSessionLocal, get_db, get_db_pool
from app.llm.settings_resolver import resolve
from app.services.eval_service import run_evaluation, summarize
from app.services.llm_service import get_llm_service
from app.services.query_service import QueryService
from app.utils.sql_validator import SQLValidator

router = APIRouter(prefix="/eval", tags=["Evaluation"], dependencies=[ADMIN])

# One scoring at a time: each question waits on the LLM, and two at once would
# only slow both and blur the timing.
_active: Optional[int] = None
_progress: Dict[int, Dict[str, Any]] = {}


class NewCase(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    expected_sql: str = Field(..., min_length=1, max_length=20000)
    database_id: int


class RunRequest(BaseModel):
    database_id: int


def _case(c: EvalCase) -> dict:
    return {"id": c.id, "question": c.question, "expected_sql": c.expected_sql,
            "database_id": c.database_id, "created_by": c.created_by}


def _run(r: EvalRun, with_details: bool = False) -> dict:
    live = _progress.get(r.id)
    out = {
        "id": r.id, "status": r.status, "provider": r.provider, "model": r.model,
        "database_id": r.database_id, "total": live["total"] if live else r.total,
        "passed": live["passed"] if live else r.passed,
        "done": live["done"] if live else r.total,
        "seconds": r.seconds, "error": r.error, "started_by": r.started_by,
        "started_at": r.started_at.isoformat() if r.started_at else None,
    }
    if with_details:
        out["details"] = live["results"] if live else (r.details or [])
    return out


def _safe_select(sql: str) -> None:
    if not SQLValidator().validate(sql)["is_safe"]:
        raise ValueError("조회(SELECT)가 아닌 SQL은 실행하지 않습니다")


async def _score(run_id: int, database_id: str, cases: list) -> None:
    """The background scoring. It owns its database session: the request that
    started it has long since returned."""
    global _active
    started = time.perf_counter()
    pool = get_db_pool()
    try:
        async with AsyncSessionLocal() as session:
            saved = await LLMSettingsRepository(session).load()
            llm = get_llm_service(config=resolve(saved, settings))
            service = QueryService(pool, HistoryRepository(session), llm, GlossaryRepository(session))
            conn = await DatabaseRepository(session).get_by_id(int(database_id))
            excluded = list(conn.excluded_tables or []) if conn else []

            async def generate(question: str) -> str:
                # Bookmarked examples off: they may hold this very answer.
                result = await service.generate_sql(
                    question, database_id, excluded_tables=excluded, use_examples=False
                )
                _safe_select(result["sql"])
                return result["sql"]

            async def execute(sql: str):
                _safe_select(sql)
                return await pool.execute_query(database_id, sql)

            def progress(done: int, total: int, results: list) -> None:
                _progress[run_id] = {
                    "done": done, "total": total, "results": list(results),
                    "passed": sum(1 for r in results if r["passed"]),
                }

            results = await run_evaluation(cases, generate, execute, progress)
            summary = summarize(results)

            repo = EvalRepository(session)
            run = await repo.run(run_id)
            run.status, run.total, run.passed = "done", summary["total"], summary["passed"]
            run.details = results
            run.seconds = round(time.perf_counter() - started, 1)
            run.provider = llm.provider.name
            run.model = llm.provider.model
            await repo.save(run)
    except Exception as exc:
        async with AsyncSessionLocal() as session:
            repo = EvalRepository(session)
            run = await repo.run(run_id)
            if run is not None:
                run.status, run.error = "error", str(exc)[:500]
                run.seconds = round(time.perf_counter() - started, 1)
                await repo.save(run)
    finally:
        _progress.pop(run_id, None)
        _active = None


@router.get("/cases")
async def list_cases(database_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    return [_case(c) for c in await EvalRepository(db).cases(str(database_id) if database_id else None)]


@router.post("/cases", status_code=status.HTTP_201_CREATED)
async def add_case(body: NewCase, admin: CurrentUser = ADMIN, db: AsyncSession = Depends(get_db)):
    try:
        _safe_select(body.expected_sql)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    case = EvalCase(question=body.question.strip(), expected_sql=body.expected_sql.strip(),
                    database_id=str(body.database_id), created_by=admin.username)
    return _case(await EvalRepository(db).add_case(case))


@router.post("/cases/from-bookmarks")
async def import_bookmarks(database_id: int, admin: CurrentUser = ADMIN, db: AsyncSession = Depends(get_db)):
    """Turn bookmarked, successful questions into cases. A question already in the set is skipped."""
    repo = EvalRepository(db)
    have = {c.question for c in await repo.cases(str(database_id))}
    saved = await HistoryRepository(db).get_all(database_id=str(database_id), status="success", bookmarked=True, limit=200)
    added = 0
    for h in saved:
        if h.question.strip() in have or not SQLValidator().validate(h.generated_sql)["is_safe"]:
            continue
        await repo.add_case(EvalCase(question=h.question.strip(), expected_sql=h.generated_sql,
                                     database_id=str(database_id), created_by=admin.username))
        have.add(h.question.strip())
        added += 1
    return {"added": added}


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(case_id: int, db: AsyncSession = Depends(get_db)):
    if not await EvalRepository(db).delete_case(case_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사례를 찾을 수 없습니다")


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def start_run(body: RunRequest, http_request: Request, admin: CurrentUser = ADMIN, db: AsyncSession = Depends(get_db)):
    global _active
    if _active is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 평가가 실행 중입니다")
    repo = EvalRepository(db)
    cases = [
        {"id": c.id, "question": c.question, "expected_sql": c.expected_sql}
        for c in await repo.cases(str(body.database_id))
    ]
    if not cases:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="평가 사례가 없습니다 — 먼저 사례를 추가하세요")

    run = await repo.add_run(EvalRun(database_id=str(body.database_id), total=len(cases), started_by=admin.username))
    _active = run.id
    _progress[run.id] = {"done": 0, "total": len(cases), "results": [], "passed": 0}
    asyncio.create_task(_score(run.id, str(body.database_id), cases))
    await record(db, admin, http_request, "eval_run", str(body.database_id), cases=len(cases))
    return _run(run)


@router.get("/runs")
async def list_runs(db: AsyncSession = Depends(get_db)):
    return [_run(r) for r in await EvalRepository(db).runs()]


@router.get("/runs/{run_id}")
async def get_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await EvalRepository(db).run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="실행 기록을 찾을 수 없습니다")
    return _run(run, with_details=True)
