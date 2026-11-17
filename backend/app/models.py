"""
SQLAlchemy ORM models: the tables stored in Supabase PostgreSQL.

    users 1 ──< jobs 1 ──< analysis_history 1 ──< match_results >── 1 candidates >── 1 users
                jobs 1 ──────────────────────────< match_results

- users             HR accounts (admin / hr); each HR owns their jobs and candidates

- jobs              a Job Description and its (recruiter-editable) extracted requirements
- candidates        one parsed resume: contact details, skills, cleaned text
- analysis_history  one run of "match these resumes against this job"
- match_results     one candidate's scores within one analysis

Design notes
- Primary keys are UUIDs (hard to guess, safe to expose in URLs).
- Lists (skills, responsibilities, ...) are JSONB columns.
- NULL means "unknown / not found", never "zero". For example, a NULL
  total_experience means the resume did not state it, not 0 years.
- relevant_experience is stored per match, not per candidate, because how much
  experience is *relevant* depends on the job being matched.
- Deleting a job deletes its analyses and match results (ON DELETE CASCADE).
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# --- Reusable column definitions ---------------------------------------------------
def uuid_primary_key() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))


def json_list() -> Mapped[list]:
    return mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))


def json_object() -> Mapped[dict]:
    return mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))


def created_at_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def score_check(column: str) -> CheckConstraint:
    """Database-level guarantee that a score is NULL or between 0 and 100."""
    return CheckConstraint(f"{column} IS NULL OR ({column} >= 0 AND {column} <= 100)", name=f"{column}_range")


# --- Tables ---------------------------------------------------------------------------
class User(Base):
    """
    An HR account. Only a password HASH is stored (see app/auth/security.py).
    role: "admin" (can manage accounts) or "hr". Accounts are disabled, never deleted
    through the app, so their data and history stay intact.
    """

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'hr')", name="role_valid"),)

    id: Mapped[uuid.UUID] = uuid_primary_key()
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)  # stored lower-case
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="hr", server_default=text("'hr'"))
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default=text("true"))
    # Incremented on password change/reset or deactivation: invalidates all older login tokens.
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_column()


def owner_column() -> Mapped[uuid.UUID | None]:
    """
    The HR who owns this row. Every query is filtered by it, so each HR only sees their
    own jobs, candidates and (through the job) analyses and results.
    Nullable only so existing databases can be migrated; new rows always get an owner.
    """
    return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("minimum_experience IS NULL OR minimum_experience >= 0", name="minimum_experience_positive"),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    owner_id: Mapped[uuid.UUID | None] = owner_column()
    job_title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required_skills: Mapped[list] = json_list()
    preferred_skills: Mapped[list] = json_list()
    # NULL = the JD states no experience requirement.
    minimum_experience: Mapped[float | None] = mapped_column(Float, nullable=True)
    education_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsibilities: Mapped[list] = json_list()
    keywords: Mapped[list] = json_list()
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    analyses: Mapped[list["AnalysisHistory"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )
    match_results: Mapped[list["MatchResult"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        CheckConstraint("total_experience IS NULL OR total_experience >= 0", name="total_experience_positive"),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    owner_id: Mapped[uuid.UUID | None] = owner_column()
    # Contact details are NULL when not found in the resume; they are never guessed.
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    education: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_experience: Mapped[float | None] = mapped_column(Float, nullable=True)
    extracted_skills: Mapped[list] = json_list()
    certifications: Mapped[list] = json_list()
    # Other parsed details: work-experience entries, projects, parse warnings.
    profile: Mapped[dict] = json_object()
    resume_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # SHA-256 of the uploaded file, used to skip duplicate files in one upload batch.
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resume_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at_column()

    match_results: Mapped[list["MatchResult"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )


class AnalysisHistory(Base):
    __tablename__ = "analysis_history"
    __table_args__ = (
        CheckConstraint("total_resumes >= 0", name="total_resumes_positive"),
        score_check("average_score"),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    total_resumes: Mapped[int] = mapped_column(Integer, nullable=False)
    average_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    job: Mapped[Job] = relationship(back_populates="analyses")
    match_results: Mapped[list["MatchResult"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", passive_deletes=True
    )


class MatchResult(Base):
    __tablename__ = "match_results"
    __table_args__ = (
        # A candidate appears at most once in a given analysis.
        UniqueConstraint("analysis_id", "candidate_id", name="uq_match_results_analysis_candidate"),
        score_check("semantic_score"),
        score_check("skills_score"),
        score_check("experience_score"),
        score_check("final_score"),
        CheckConstraint("relevant_experience IS NULL OR relevant_experience >= 0", name="relevant_experience_positive"),
        # Speeds up "rank the candidates of this analysis" (ORDER BY final_score DESC).
        Index("ix_match_results_analysis_rank", "analysis_id", text("final_score DESC")),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_history.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Component scores, 0-100. NULL = that component could not be calculated
    # (e.g. experience unknown); the reason is recorded in `details`.
    semantic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    skills_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    experience_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)

    relevant_experience: Mapped[float | None] = mapped_column(Float, nullable=True)
    matched_skills: Mapped[list] = json_list()
    missing_skills: Mapped[list] = json_list()
    additional_skills: Mapped[list] = json_list()
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    # Full breakdown: weights used, raw cosine similarity, experience evidence, notes.
    details: Mapped[dict] = json_object()
    created_at: Mapped[datetime] = created_at_column()

    analysis: Mapped[AnalysisHistory] = relationship(back_populates="match_results")
    job: Mapped[Job] = relationship(back_populates="match_results")
    candidate: Mapped[Candidate] = relationship(back_populates="match_results")
