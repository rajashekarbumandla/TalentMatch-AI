"""
Pydantic request/response models (the API's data contract).

FastAPI uses these to validate input, serialise output and generate the
Swagger documentation at /docs. Validators here also *clean* recruiter input:
skills are normalised ("postgres" -> "PostgreSQL"), duplicates removed, and a
skill can never be both required and preferred.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.nlp.skill_extractor import normalize_skill_list, split_alternatives

MAX_SKILLS = 60
MAX_SKILL_LENGTH = 100
MAX_LIST_ITEM_LENGTH = 500


# --- System -------------------------------------------------------------------------------------
class DatabaseStatus(BaseModel):
    configured: bool
    connected: bool
    message: str


class ModelStatus(BaseModel):
    name: str
    loaded: bool  # False until loaded (startup, or the first analysis if LOAD_MODEL_ON_STARTUP=false)
    error: str | None = None


class HealthResponse(BaseModel):
    status: str  # "ok" when everything works, "degraded" when the database is unreachable
    service: str
    version: str
    database: DatabaseStatus
    model: ModelStatus


# --- Shared cleaning helpers -------------------------------------------------------------------------
def clean_skill_list(values: list[str] | None) -> list[str]:
    skills = normalize_skill_list([v for v in (values or []) if isinstance(v, str)])
    too_long = [s for s in skills if len(s) > MAX_SKILL_LENGTH]
    if too_long:
        raise ValueError(f"Skill names must be at most {MAX_SKILL_LENGTH} characters: {too_long[0][:30]}...")
    return skills


def clean_text_list(values: list[str] | None) -> list[str]:
    """Strip, drop empty entries and remove case-insensitive duplicates, keeping order."""
    seen: dict[str, str] = {}
    for value in values or []:
        text = " ".join(str(value).split())
        if len(text) > MAX_LIST_ITEM_LENGTH:
            raise ValueError(f"Each entry must be at most {MAX_LIST_ITEM_LENGTH} characters.")
        if text:
            seen.setdefault(text.lower(), text)
    return list(seen.values())


def remove_required_from_preferred(required: list[str], preferred: list[str]) -> list[str]:
    """A skill (or every alternative of an 'A or B' entry) that is required is not also preferred."""
    required_parts = {part.lower() for skill in required for part in split_alternatives(skill)}
    return [s for s in preferred if not {p.lower() for p in split_alternatives(s)} <= required_parts]


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


# --- Jobs ------------------------------------------------------------------------------------------
class JobRequirementsMixin(BaseModel):
    """The requirement fields a recruiter can review and edit."""

    @field_validator("job_title", mode="before", check_fields=False)
    @classmethod
    def _strip_title(cls, value):
        return " ".join(value.split()) if isinstance(value, str) else value

    @field_validator("description", mode="before", check_fields=False)
    @classmethod
    def _strip_description(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("required_skills", "preferred_skills", check_fields=False)
    @classmethod
    def _clean_skills(cls, value):
        return None if value is None else clean_skill_list(value)

    @field_validator("responsibilities", "keywords", check_fields=False)
    @classmethod
    def _clean_lists(cls, value):
        return None if value is None else clean_text_list(value)

    @field_validator("education_requirements", mode="before", check_fields=False)
    @classmethod
    def _clean_education(cls, value):
        return _clean_optional_text(value)

    @model_validator(mode="after")
    def _no_double_counting(self):
        if getattr(self, "required_skills", None) is not None and getattr(self, "preferred_skills", None) is not None:
            self.preferred_skills = remove_required_from_preferred(self.required_skills, self.preferred_skills)
        return self


class JobCreate(JobRequirementsMixin):
    job_title: str = Field(min_length=2, max_length=200, examples=["Python Developer"])
    description: str = Field(min_length=30, max_length=50_000)
    required_skills: list[str] = Field(default_factory=list, max_length=MAX_SKILLS, examples=[["Python", "FastAPI or Django"]])
    preferred_skills: list[str] = Field(default_factory=list, max_length=MAX_SKILLS)
    # None = no experience requirement.
    minimum_experience: float | None = Field(default=None, ge=0, le=50)
    education_requirements: str | None = Field(default=None, max_length=2000)
    responsibilities: list[str] = Field(default_factory=list, max_length=50)
    keywords: list[str] = Field(default_factory=list, max_length=100)


class JobUpdate(JobRequirementsMixin):
    """Partial update: only the fields that are sent are changed."""

    job_title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, min_length=30, max_length=50_000)
    required_skills: list[str] | None = Field(default=None, max_length=MAX_SKILLS)
    preferred_skills: list[str] | None = Field(default=None, max_length=MAX_SKILLS)
    minimum_experience: float | None = Field(default=None, ge=0, le=50)
    education_requirements: str | None = Field(default=None, max_length=2000)
    responsibilities: list[str] | None = Field(default=None, max_length=50)
    keywords: list[str] | None = Field(default=None, max_length=100)


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_title: str
    description: str
    required_skills: list[str]
    preferred_skills: list[str]
    minimum_experience: float | None
    education_requirements: str | None
    responsibilities: list[str]
    keywords: list[str]
    created_at: datetime
    updated_at: datetime


# --- JD analysis -----------------------------------------------------------------------------------
class JDAnalyzeRequest(BaseModel):
    description: str = Field(min_length=30, max_length=50_000)
    job_title: str | None = Field(default=None, max_length=200)


class JobListItem(BaseModel):
    id: uuid.UUID
    job_title: str
    required_skills: list[str]
    preferred_skills: list[str]
    minimum_experience: float | None
    education_requirements: str | None
    created_at: datetime
    updated_at: datetime
    analysis_count: int
    latest_analysis_at: datetime | None


class JDAnalysisResponse(BaseModel):
    """Suggested requirements; the recruiter edits them and then saves a JobCreate."""

    job_title: str | None
    required_skills: list[str]
    preferred_skills: list[str]
    minimum_experience: float | None
    maximum_experience: float | None
    experience_evidence: str | None
    education_requirements: str | None
    education_level: str | None
    responsibilities: list[str]
    keywords: list[str]
    skill_evidence: dict[str, str]
    sections_found: list[str]
    warnings: list[str]
    description: str  # cleaned JD text, so a JD uploaded as a file can be saved as a job


# --- Resume upload ------------------------------------------------------------------------------------
class UploadFileResult(BaseModel):
    filename: str
    status: str  # parsed | duplicate | error
    size_bytes: int
    candidate_id: uuid.UUID | None = None
    duplicate_of: str | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    skills: list[str] = []
    total_experience: float | None = None
    experience_method: str | None = None
    warnings: list[str] = []
    error: str | None = None


class UploadResponse(BaseModel):
    total_files: int
    parsed: int
    duplicates: int
    failed: int
    candidate_ids: list[uuid.UUID]  # pass these to POST /api/analyze/{job_id}
    files: list[UploadFileResult]


# --- Analysis and ranking -------------------------------------------------------------------------------
def round2(value: float | None) -> float | None:
    """Scores are stored unrounded; the API shows them with two decimals."""
    return None if value is None else round(value, 2)


class AnalyzeRequest(BaseModel):
    candidate_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class AnalysisSummary(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    total_resumes: int
    average_score: float | None
    created_at: datetime


class RankedCandidateOut(BaseModel):
    rank: int
    candidate_id: uuid.UUID
    match_id: uuid.UUID
    name: str | None
    email: str | None
    phone: str | None
    total_experience: float | None
    relevant_experience: float | None
    final_score: float
    semantic_score: float | None
    skills_score: float | None
    experience_score: float | None
    matched_skills: list[str]
    missing_skills: list[str]
    additional_skills: list[str]
    status: str  # complete | incomplete
    resume_filename: str


class ResultsResponse(BaseModel):
    job: JobRead
    analysis: AnalysisSummary
    total_candidates: int  # in the whole analysis
    filtered_count: int  # after search/filters (before pagination)
    items: list[RankedCandidateOut]


class AnalyzeResponse(ResultsResponse):
    skipped_duplicates: list[str]
    missing_candidate_ids: list[uuid.UUID]


# --- Candidates -------------------------------------------------------------------------------------------
class CandidateMatchSummary(BaseModel):
    analysis_id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    final_score: float
    created_at: datetime


class CandidateDetail(BaseModel):
    id: uuid.UUID
    name: str | None
    email: str | None
    phone: str | None
    education: list[str]
    degree_levels: list[str]
    total_experience: float | None
    internship_experience: float | None
    experience_method: str
    is_fresher: bool
    skills: list[str]
    skills_by_category: dict[str, list[str]]
    certifications: list[str]
    projects: list[dict]
    experience: list[dict]
    links: list[str]
    summary: str | None
    resume_filename: str
    parse_warnings: list[str]
    created_at: datetime
    matches: list[CandidateMatchSummary] = []


class CandidateListItem(BaseModel):
    id: uuid.UUID
    name: str | None
    email: str | None
    total_experience: float | None
    skills: list[str]
    resume_filename: str
    created_at: datetime
    analyses_count: int
    best_score: float | None
    latest_score: float | None
    latest_analysis_id: uuid.UUID | None
    latest_job_id: uuid.UUID | None
    latest_job_title: str | None


class CandidateListResponse(BaseModel):
    total: int
    items: list[CandidateListItem]


class MatchDetail(BaseModel):
    match_id: uuid.UUID
    rank: int
    total_candidates: int
    final_score: float
    semantic_score: float | None
    skills_score: float | None
    experience_score: float | None
    status: str
    cosine_similarity: float | None
    weights_used: dict[str, float]
    missing_components: list[str]
    matched_required_skills: list[str]
    matched_preferred_skills: list[str]
    missing_required_skills: list[str]
    missing_preferred_skills: list[str]
    additional_skills: list[str]
    satisfied_by: dict[str, str]
    required_experience: float | None
    relevant_experience: float | None
    experience_status: str  # met | not_met | not_required | unknown
    experience_method: str
    relevant_experience_entries: list[str]
    explanation: str


class CandidateAnalysisResponse(BaseModel):
    candidate: CandidateDetail
    job: JobRead
    analysis: AnalysisSummary
    match: MatchDetail


# --- Dashboard -----------------------------------------------------------------------------------------------
class ScoreBucket(BaseModel):
    range: str
    count: int


class ActivityPoint(BaseModel):
    date: str
    analyses: int
    resumes: int


class RankingOverviewCandidate(BaseModel):
    rank: int
    candidate_id: uuid.UUID
    name: str | None
    final_score: float


class RankingOverview(BaseModel):
    analysis_id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    candidates: list[RankingOverviewCandidate]


class RecentAnalysis(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    total_resumes: int
    average_score: float | None
    created_at: datetime


class DashboardStats(BaseModel):
    total_jobs: int
    total_candidates: int
    total_analyses: int
    resumes_analyzed: int  # distinct candidates that appear in at least one analysis
    total_matches: int
    average_score: float | None
    high_match_candidates: int
    high_match_threshold: float
    score_distribution: list[ScoreBucket]
    recent_analyses: list[RecentAnalysis]
    activity: list[ActivityPoint]
    ranking_overview: RankingOverview | None


# --- Accounts & login --------------------------------------------------------------------------------------
class SetupStatus(BaseModel):
    needs_setup: bool  # true until the first (admin) account exists


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class SetupRequest(BaseModel):
    full_name: str = Field(max_length=120)
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    role: str  # admin | hr
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead


class UserCreate(BaseModel):
    full_name: str = Field(max_length=120)
    email: str = Field(max_length=254)
    password: str = Field(max_length=128, description="Temporary password; the HR can change it after logging in.")
    role: str = Field(default="hr", pattern="^(admin|hr)$")


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, pattern="^(admin|hr)$")
    is_active: bool | None = None


class PasswordReset(BaseModel):
    new_password: str = Field(max_length=128)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)
