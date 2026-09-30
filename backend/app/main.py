"""
KFMS (Knowledge Flow Management System) - FastAPI Application Entry Point.
Text-to-SQL service with LLM integration (Ollama + Groq).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.config import settings
from app.dependencies import AsyncSessionLocal
from app.db.connection_pool import get_connection_pool
from app.db.repositories.database_repo import DatabaseRepository

# Import routers
from app.api.v1 import databases, query, excel, history, anomaly, llm_settings, glossary


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

    # TODO: Start Excel cleanup scheduler

    yield

    # Shutdown
    print("👋 Shutting down KFMS...")
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
    Health check endpoint.
    Returns application status and component availability.
    """
    health_status = {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "llm_provider": settings.LLM_PROVIDER,
        "components": {
            "database": "not_implemented",  # TODO: Check DB connection
            "ollama": "not_implemented",     # TODO: Check Ollama availability
            "groq": "not_implemented"        # TODO: Check Groq availability
        }
    }

    return JSONResponse(content=health_status, status_code=200)


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
app.include_router(databases.router, prefix="/api/v1")
app.include_router(query.router, prefix="/api/v1")
app.include_router(excel.router, prefix="/api/v1")
app.include_router(history.router, prefix="/api/v1")
app.include_router(anomaly.router, prefix="/api/v1")
app.include_router(llm_settings.router, prefix="/api/v1")
app.include_router(glossary.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD
    )
