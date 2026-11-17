"""
Analysis service: "match these candidates against this job" and save the results.

Workflow of run_analysis():
    1. Load the job and the candidates (one query each).
    2. Remove duplicates: the same candidate id twice, or two uploads of the same file
       (same SHA-256), so a person appears only once per analysis.
    3. Score everyone with the hybrid engine (matching/scoring.py).
    4. Save ONE analysis_history row plus one match_results row per candidate in a
       SINGLE transaction: either everything is stored or nothing is
       (a failure rolls back, so no half-finished analysis is ever visible).

Each run creates a new analysis, so earlier results for the same job remain
available in the history.
"""
import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.matching.scoring import CandidateProfile, JobProfile, score_candidates
from app.models import AnalysisHistory, Job, MatchResult
from app.services.candidate_service import get_candidates


class AnalysisError(ValueError):
    """Invalid analysis request (message is safe to show to the recruiter)."""


@dataclass
class AnalysisRun:
    analysis: AnalysisHistory
    results: list[MatchResult]
    skipped_duplicates: list[str] = field(default_factory=list)  # resume file names
    missing_candidate_ids: list[uuid.UUID] = field(default_factory=list)


def run_analysis(
    db: Session, job_id: uuid.UUID, candidate_ids: list[uuid.UUID], *, owner_id: uuid.UUID, today: date | None = None
) -> AnalysisRun:
    """Only this HR's job and candidates can be used; anything else is treated as not found."""
    job = db.get(Job, job_id)
    if job is None or job.owner_id != owner_id:
        raise AnalysisError("Job not found.")
    unique_ids = list(dict.fromkeys(candidate_ids))  # same id twice -> once
    if not unique_ids:
        raise AnalysisError("Select at least one resume to analyze.")

    candidates = get_candidates(db, unique_ids, owner_id=owner_id)
    found = {c.id for c in candidates}
    missing = [i for i in unique_ids if i not in found]
    if not candidates:
        raise AnalysisError("None of the selected resumes were found. Please upload them again.")

    # The same file uploaded twice (identical content) is analysed once.
    seen_hashes: set[str] = set()
    unique_candidates, skipped = [], []
    for candidate in candidates:
        if candidate.file_hash in seen_hashes:
            skipped.append(candidate.resume_filename)
            continue
        seen_hashes.add(candidate.file_hash)
        unique_candidates.append(candidate)

    outcomes = score_candidates(
        JobProfile.from_model(job), [CandidateProfile.from_model(c) for c in unique_candidates], today=today
    )

    analysis = AnalysisHistory(
        job_id=job.id,
        total_resumes=len(outcomes),
        average_score=round(sum(o.final_score for o in outcomes) / len(outcomes), 2),
    )
    by_key = {str(c.id): c for c in unique_candidates}
    results = [
        MatchResult(
            analysis=analysis,
            job_id=job.id,
            candidate_id=by_key[o.candidate_key].id,
            semantic_score=o.semantic_score,
            skills_score=o.skills_score,
            experience_score=o.experience_score,
            final_score=o.final_score,
            relevant_experience=o.relevant_experience,
            matched_skills=o.matched_skills,
            missing_skills=o.missing_skills,
            additional_skills=o.additional_skills,
            explanation=o.explanation,
            details={**o.details, "status": o.status},
        )
        for o in outcomes
    ]
    try:
        db.add(analysis)
        db.add_all(results)
        db.commit()  # one transaction for the analysis and all its results
    except Exception:
        db.rollback()
        raise
    db.refresh(analysis)
    return AnalysisRun(analysis, results, skipped, missing)


def get_analysis(db: Session, analysis_id: uuid.UUID, *, owner_id: uuid.UUID) -> AnalysisHistory | None:
    """The analysis, only if its job belongs to this HR."""
    analysis = db.get(AnalysisHistory, analysis_id)
    return analysis if analysis is not None and analysis.job.owner_id == owner_id else None


def latest_analysis_for_job(db: Session, job_id: uuid.UUID) -> AnalysisHistory | None:
    return db.scalars(
        select(AnalysisHistory)
        .where(AnalysisHistory.job_id == job_id)
        .order_by(AnalysisHistory.created_at.desc(), AnalysisHistory.id)
        .limit(1)
    ).first()


def list_analyses(
    db: Session, *, owner_id: uuid.UUID, job_id: uuid.UUID | None = None, limit: int = 50
) -> list[AnalysisHistory]:
    """This HR's analysis history, newest first (optionally for one job)."""
    query = (
        select(AnalysisHistory)
        .join(Job, Job.id == AnalysisHistory.job_id)
        .where(Job.owner_id == owner_id)
        .order_by(AnalysisHistory.created_at.desc())
        .limit(limit)
    )
    if job_id is not None:
        query = query.where(AnalysisHistory.job_id == job_id)
    return list(db.scalars(query))
