"""
Central configuration for the TalentMatch AI backend.

All tunable settings are read from environment variables (or a `.env` file in
the `backend/` folder) so nothing is hardcoded in the business logic.
See `backend/.env.example` for documentation of every variable.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# backend/ directory (one level above this "app" package)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# Vercel sets VERCEL=1 in its environment. Serverless functions start often ("cold starts"),
# can only write to /tmp and run several instances at once, so some defaults differ there.
ON_VERCEL = bool(os.getenv("VERCEL"))


class Settings:
    ON_VERCEL: bool = ON_VERCEL

    APP_NAME: str = "TalentMatch AI"
    APP_VERSION: str = "0.1.0"

    # --- Database (Supabase PostgreSQL) -------------------------------------
    # SQLAlchemy URL using the psycopg (v3) driver, e.g.
    # postgresql+psycopg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
    # Never commit the real value; it lives only in backend/.env.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()
    # Connections kept open per server instance (serverless runs many small instances).
    DB_POOL_SIZE: int = _env_int("DB_POOL_SIZE", 2 if ON_VERCEL else 5)
    DB_MAX_OVERFLOW: int = _env_int("DB_MAX_OVERFLOW", 3 if ON_VERCEL else 5)
    # Create missing tables / run migrations when the API starts. Off on Vercel, where the
    # tables already exist (run `python -m app.create_tables` once instead).
    RUN_DB_INIT_ON_STARTUP: bool = _env_bool("RUN_DB_INIT_ON_STARTUP", not ON_VERCEL)

    # --- Authentication ------------------------------------------------------
    # Secret used to sign login tokens. Must be long and random, and kept private.
    # If it is missing, a temporary one is generated at startup (everyone is logged out on restart).
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "").strip()
    ACCESS_TOKEN_EXPIRE_MINUTES: int = _env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 480)  # one working day
    MIN_PASSWORD_LENGTH: int = _env_int("MIN_PASSWORD_LENGTH", 8)

    # --- Upload limits -----------------------------------------------------
    # Vercel rejects request bodies over 4.5 MB, so a single file must stay below that there.
    MAX_FILE_SIZE_MB: float = _env_float("MAX_FILE_SIZE_MB", 4 if ON_VERCEL else 5)
    MAX_FILES_PER_BATCH: int = _env_int("MAX_FILES_PER_BATCH", 50)
    ALLOWED_EXTENSIONS: tuple = (".pdf", ".docx")

    # --- NLP model ---------------------------------------------------------
    MODEL_NAME: str = os.getenv("MODEL_NAME", "all-MiniLM-L6-v2")
    MODEL_REVISION: str = os.getenv("MODEL_REVISION", "main")  # Hugging Face branch/commit of the model files
    # Where the ONNX model files are stored. Serverless hosts (Vercel) only allow writing to /tmp.
    MODEL_CACHE_DIR: str = os.getenv(
        "MODEL_CACHE_DIR", "/tmp/talentmatch-models" if ON_VERCEL else str(Path.home() / ".cache" / "talentmatch-models")
    )
    SPACY_MODEL: str = os.getenv("SPACY_MODEL", "en_core_web_sm")
    # true: load the AI models when the server starts, so no request waits for them.
    # false (default on Vercel): load on first use, so cold starts for login/dashboard stay fast.
    LOAD_MODEL_ON_STARTUP: bool = _env_bool("LOAD_MODEL_ON_STARTUP", not ON_VERCEL)

    # --- OCR (optional) ----------------------------------------------------
    OCR_ENABLED: bool = _env_bool("OCR_ENABLED", True)
    TESSERACT_CMD: str | None = os.getenv("TESSERACT_CMD") or None
    # A PDF page with fewer extractable characters than this is treated as scanned.
    MIN_TEXT_CHARS_PER_PAGE: int = _env_int("MIN_TEXT_CHARS_PER_PAGE", 30)

    # --- Scoring weights (must sum to 1.0) ---------------------------------
    WEIGHT_SEMANTIC: float = _env_float("WEIGHT_SEMANTIC", 0.40)
    WEIGHT_SKILLS: float = _env_float("WEIGHT_SKILLS", 0.35)
    WEIGHT_EXPERIENCE: float = _env_float("WEIGHT_EXPERIENCE", 0.25)

    # Required skills count double compared with preferred skills.
    REQUIRED_SKILL_WEIGHT: float = _env_float("REQUIRED_SKILL_WEIGHT", 2.0)
    PREFERRED_SKILL_WEIGHT: float = _env_float("PREFERRED_SKILL_WEIGHT", 1.0)

    # Cosine similarity calibration for all-MiniLM-L6-v2 (documented in README).
    # Similarity <= FLOOR maps to 0, >= CEIL maps to 100, linear in between.
    SEMANTIC_COSINE_FLOOR: float = _env_float("SEMANTIC_COSINE_FLOOR", 0.15)
    SEMANTIC_COSINE_CEIL: float = _env_float("SEMANTIC_COSINE_CEIL", 0.75)

    # Candidates scoring at least this much count as "high match" on the dashboard.
    HIGH_MATCH_THRESHOLD: float = _env_float("HIGH_MATCH_THRESHOLD", 75)

    # --- API ---------------------------------------------------------------
    CORS_ORIGINS: list[str] = [
        o.strip().rstrip("/")
        for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if o.strip()
    ]
    # Optional regular expression for extra allowed origins, e.g. Vercel preview deployments:
    # ^https://talentmatch-[a-z0-9-]+\.vercel\.app$
    CORS_ORIGIN_REGEX: str | None = os.getenv("CORS_ORIGIN_REGEX") or None

    @property
    def max_file_size_bytes(self) -> int:
        return int(self.MAX_FILE_SIZE_MB * 1024 * 1024)

    @property
    def database_configured(self) -> bool:
        return bool(self.DATABASE_URL)


settings = Settings()
