"""
KFMS (Knowledge Flow Management System) - FastAPI Application Entry Point.
Text-to-SQL service with LLM integration (Ollama + Groq).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
from contextlib import asynccontextmanager

from app.config import settings
from app.dependencies import AsyncSessionLocal
from app.db.connection_pool import get_connection_pool
from app.db.repositories.database_repo import DatabaseRepository

# Import routers
from app.api.v1 import databases, query, excel, history, anomaly, llm_settings, glossary, auth, reports
from sqlalchemy import text
from app.db.repositories.llm_settings import LLMSettingsRepository
from app.llm.factory import create_provider
from app.llm.settings_resolver import resolve
from app.services.scheduler import scheduler_loop, state as scheduler_state
from app.auth.audit_rules import is_audited
from app.auth.deps import ADMIN, ANY_USER, AUDITOR, secret, token_from
from app.auth.security import read_token
from app.db.repositories.audit import AuditRepository
from app.dependencies import AsyncSessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Handles startup and shutdown events.
    """
    # Startup
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"📊 LLM Provider: {settings.LLM_PROVIDER}")
    print(f"🔗 Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'Not configured'}")

    # The pool is in-memory, so registered connections must be restored on every
    # start or queries fail until the connection is re-tested from the UI.
    pool = get_connection_pool()
    restored = 0
    try:
        async with AsyncSessionLocal() as session:
            repo = DatabaseRepository(session)
            for conn in await repo.get_all(active_only=True):
                await pool.add_connection(
                    connection_id=str(conn.id),
                    host=conn.host,
                    port=conn.port,
                    database=conn.database,
                    username=conn.username,
                    password=repo.get_decrypted_password(conn),
                    is_read_only=conn.is_read_only,
                )
                restored += 1
        print(f"🔌 Restored {restored} database connection(s)")
    except Exception as e:
        print(f"⚠️  Could not restore connection pool: {e}")

    # Scheduled reports, and dropping Excel tables once they expire.
    scheduler_task = asyncio.create_task(scheduler_loop(pool))

    yield

    # Shutdown
    print("👋 Shutting down KFMS...")
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    await pool.close_all()


# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Natural language to SQL query service with PostgreSQL and Excel support",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

@app.middleware("http")
async def audit_requests(request, call_next):
    """Log every change and every read of card numbers or saved results.

    Requests that write their own, richer entry (the SQL run, who signed in)
    are skipped by is_audited(generic=True).
    """
    response = await call_next(request)
    try:
        if request.url.path.startswith("/api/") and is_audited(request.method, request.url.path, generic=True):
            claims = read_token(token_from(request) or "", secret()) or {}
            async with AsyncSessionLocal() as session:
                await AuditRepository(session).add(
                    claims.get("name", ""), claims.get("role", ""), "request",
                    f"{request.method} {request.url.path}", {"status": response.status_code},
                    request.client.host if request.client else "",
                )
    except Exception:
        pass  # the log must never break the request it describes
    return response


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint. Deliberately public and free of anything sensitive:
    it says which parts answer, not what they hold.
    """
    components = {}
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        components["database"] = "ok"
    except Exception:
        components["database"] = "unreachable"

    components["connections"] = len(get_connection_pool()._engines)
    components["scheduler"] = "running" if scheduler_state["running"] else "stopped"

    try:
        async with AsyncSessionLocal() as session:
            saved = await LLMSettingsRepository(session).load()
        provider = create_provider(config=resolve(saved, settings))
        components["llm"] = "ok" if await asyncio.wait_for(provider.validate_connection(), timeout=4) else "unreachable"
    except Exception:
        components["llm"] = "unreachable"

    healthy = components["database"] == "ok"
    health_status = {
        "status": "healthy" if healthy and components["llm"] == "ok" else ("degraded" if healthy else "unhealthy"),
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "components": components,
    }

    return JSONResponse(content=health_status, status_code=200 if healthy else 503)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/api/docs",
        "health": "/api/v1/health"
    }


# Register API routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(databases.router, prefix="/api/v1", dependencies=[ANY_USER])
app.include_router(query.router, prefix="/api/v1", dependencies=[ANY_USER])
app.include_router(excel.router, prefix="/api/v1", dependencies=[AUDITOR])
app.include_router(history.router, prefix="/api/v1", dependencies=[ANY_USER])
app.include_router(anomaly.router, prefix="/api/v1", dependencies=[AUDITOR])
app.include_router(llm_settings.router, prefix="/api/v1", dependencies=[ADMIN])
app.include_router(glossary.router, prefix="/api/v1", dependencies=[ANY_USER])
app.include_router(reports.router, prefix="/api/v1", dependencies=[ANY_USER])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD
    )
