"""
FastAPI application entry point.

Run locally (from the backend/ folder):
    python -m uvicorn app.main:app --reload --port 8000
Interactive API docs: http://localhost:8000/docs
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import DB_CONFIG_ERROR, check_database_connection, describe_db_error, engine, init_db
from app.errors import register_exception_handlers
from app.nlp.semantic_matcher import semantic_matcher
from app.routes import ALL_ROUTERS
from app.nlp.spacy_model import get_spacy_model
from app.schemas import DatabaseStatus, HealthResponse, ModelStatus

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")
for noisy in ("httpx", "httpx2"):
    logging.getLogger(noisy).setLevel(logging.WARNING)  # keep startup logs readable
logger = logging.getLogger("talentmatch")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Runs once when the server starts (before `yield`) and once when it stops."""
    if engine is None:
        logger.warning("Database disabled: %s", DB_CONFIG_ERROR)
    elif not settings.RUN_DB_INIT_ON_STARTUP:
        logger.info("Skipping table creation at startup (RUN_DB_INIT_ON_STARTUP=false).")
    else:
        try:
            tables = init_db()
            logger.info("Database ready (%d tables verified).", len(tables))
        except Exception as exc:
            # Keep the API running so /api/health can report the problem.
            logger.error("Database initialisation failed: %s", describe_db_error(exc))

    # Load the NLP models ONCE here, so no request ever waits for (or repeats) model loading.
    if settings.LOAD_MODEL_ON_STARTUP:
        await asyncio.to_thread(semantic_matcher.load)  # ~10-15 s on first start (downloads ~90 MB once)
        await asyncio.to_thread(get_spacy_model)
    yield
    if engine is not None:
        engine.dispose()


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version=settings.APP_VERSION,
    description="Intelligent Resume Screening. Smarter Hiring Decisions.",
    lifespan=lifespan,
)

# CORS lets the React app (a different origin, e.g. localhost:5173) call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # lets the browser read the CSV file name
)
register_exception_handlers(app)
for router in ALL_ROUTERS:
    app.include_router(router)


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health() -> HealthResponse:
    """Reports whether the API is running and whether Supabase is reachable."""
    connected, message = check_database_connection()
    return HealthResponse(
        status="ok" if connected else "degraded",
        service=f"{settings.APP_NAME} API",
        version=settings.APP_VERSION,
        database=DatabaseStatus(configured=engine is not None, connected=connected, message=message),
        model=ModelStatus(
            name=semantic_matcher.model_name, loaded=semantic_matcher.available, error=semantic_matcher.error
        ),
    )
