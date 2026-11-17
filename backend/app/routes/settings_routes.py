"""Read-only view of the scoring configuration and upload limits (set in backend/.env)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.config import settings
from app.matching.scoring import scoring_weights

router = APIRouter(prefix="/api/settings", tags=["Settings"], dependencies=[Depends(get_current_user)])


class SettingsResponse(BaseModel):
    weights: dict[str, float]  # semantic / skills / experience, sum = 1
    required_skill_weight: float
    preferred_skill_weight: float
    high_match_threshold: float
    semantic_model: str
    semantic_cosine_floor: float
    semantic_cosine_ceil: float
    max_file_size_mb: float
    max_files_per_batch: int
    allowed_extensions: list[str]


@router.get("/", response_model=SettingsResponse, summary="Scoring configuration and upload limits")
def get_settings() -> SettingsResponse:
    """The frontend shows how scores are calculated and validates uploads with the same limits as the server."""
    return SettingsResponse(
        weights=scoring_weights(),
        required_skill_weight=settings.REQUIRED_SKILL_WEIGHT,
        preferred_skill_weight=settings.PREFERRED_SKILL_WEIGHT,
        high_match_threshold=settings.HIGH_MATCH_THRESHOLD,
        semantic_model=settings.MODEL_NAME,
        semantic_cosine_floor=settings.SEMANTIC_COSINE_FLOOR,
        semantic_cosine_ceil=settings.SEMANTIC_COSINE_CEIL,
        max_file_size_mb=settings.MAX_FILE_SIZE_MB,
        max_files_per_batch=settings.MAX_FILES_PER_BATCH,
        allowed_extensions=list(settings.ALLOWED_EXTENSIONS),
    )
