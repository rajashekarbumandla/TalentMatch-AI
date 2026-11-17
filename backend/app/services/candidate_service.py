"""
Candidate service: store parsed resumes as `candidates` rows.

The original file is NOT stored; only the extracted text and structured data.
Everything the matching engine needs later (experience entries with dates and
skills, how experience was determined, internships) goes into the `profile`
JSONB column, so an analysis can be re-run from the database at any time.
"""
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, defer

from app.matching.ranking import escape_like
from app.models import Candidate, Job, MatchResult
from app.parser.resume_parser import ParsedResume


def build_candidate(parsed: ParsedResume, filename: str, file_hash: str, *, owner_id: uuid.UUID | None) -> Candidate:
    """Map a parse result to a Candidate row owned by the uploading HR (not yet added to the session)."""
    return Candidate(
        owner_id=owner_id,
        name=parsed.name,
        email=parsed.email,
        phone=parsed.phone,
        education=parsed.education_text,
        total_experience=parsed.total_experience_years,
        extracted_skills=parsed.skills,
        certifications=parsed.certifications,
        profile={
            "summary": parsed.summary,
            "links": parsed.links,
            "skills_by_category": parsed.skills_by_category,
            "education_entries": parsed.education,
            "degree_levels": parsed.degree_levels,
            "projects": parsed.projects,
            "experience": parsed.experience,
            "experience_method": parsed.experience_method,
            "internship_experience_years": parsed.internship_experience_years,
            "stated_experience_years": parsed.stated_experience_years,
            "is_fresher": parsed.is_fresher,
            "sections_found": parsed.sections_found,
            "parse_warnings": parsed.warnings,
            "parse_meta": parsed.meta,
        },
        resume_filename=filename,
        file_hash=file_hash,
        resume_text=parsed.text,
    )


def create_candidate(
    db: Session, parsed: ParsedResume, filename: str, file_hash: str, *, owner_id: uuid.UUID | None, commit: bool = True
) -> Candidate:
    candidate = build_candidate(parsed, filename, file_hash, owner_id=owner_id)
    db.add(candidate)
    if commit:
        db.commit()
        db.refresh(candidate)
    return candidate


def get_candidate(db: Session, candidate_id: uuid.UUID, *, owner_id: uuid.UUID) -> Candidate | None:
    """The candidate, only if this HR uploaded them (another HR's candidate behaves as 'not found')."""
    candidate = db.get(Candidate, candidate_id)
    return candidate if candidate is not None and candidate.owner_id == owner_id else None


def get_candidates(db: Session, candidate_ids: list[uuid.UUID], *, owner_id: uuid.UUID) -> list[Candidate]:
    """Fetch several of this HR's candidates in ONE query, in the order of `candidate_ids`."""
    if not candidate_ids:
        return []
    query = select(Candidate).where(Candidate.id.in_(candidate_ids), Candidate.owner_id == owner_id)
    rows = {c.id: c for c in db.scalars(query)}
    return [rows[i] for i in candidate_ids if i in rows]


def list_candidates(
    db: Session, *, owner_id: uuid.UUID, search: str | None = None, limit: int = 50, offset: int = 0
) -> tuple[list[dict], int]:
    """
    This HR's candidates (newest first) with a summary of their results:
    number of analyses, best score, and their most recent match (job + score).
    One query: aggregates and "latest match per candidate" (PostgreSQL DISTINCT ON) are subqueries.
    """
    stats = (
        select(
            MatchResult.candidate_id,
            func.count().label("analyses_count"),
            func.max(MatchResult.final_score).label("best_score"),
        )
        .group_by(MatchResult.candidate_id)
        .subquery()
    )
    latest = (
        select(
            MatchResult.candidate_id,
            MatchResult.final_score.label("latest_score"),
            MatchResult.analysis_id.label("latest_analysis_id"),
            MatchResult.job_id.label("latest_job_id"),
            Job.job_title.label("latest_job_title"),
        )
        .join(Job, Job.id == MatchResult.job_id)
        .distinct(MatchResult.candidate_id)
        .order_by(MatchResult.candidate_id, MatchResult.created_at.desc())
        .subquery()
    )
    query = (
        select(Candidate, stats, latest, func.count().over().label("total"))
        .outerjoin(stats, stats.c.candidate_id == Candidate.id)
        .outerjoin(latest, latest.c.candidate_id == Candidate.id)
        .where(Candidate.owner_id == owner_id)
        .options(defer(Candidate.resume_text))
        .order_by(Candidate.created_at.desc(), Candidate.id)
        .limit(limit)
        .offset(offset)
    )
    if search and search.strip():
        pattern = f"%{escape_like(search.strip())}%"
        query = query.where(or_(Candidate.name.ilike(pattern, escape="\\"), Candidate.email.ilike(pattern, escape="\\")))
    rows = db.execute(query).all()
    items = [
        {
            "candidate": row.Candidate,
            "analyses_count": row.analyses_count or 0,
            "best_score": row.best_score,
            "latest_score": row.latest_score,
            "latest_analysis_id": row.latest_analysis_id,
            "latest_job_id": row.latest_job_id,
            "latest_job_title": row.latest_job_title,
        }
        for row in rows
    ]
    return items, (rows[0].total if rows else 0)


def candidate_match_history(db: Session, candidate_id: uuid.UUID) -> list[tuple[MatchResult, str]]:
    """Every result this candidate has, newest first, with the job title."""
    return [
        (match, title)
        for match, title in db.execute(
            select(MatchResult, Job.job_title)
            .join(Job, Job.id == MatchResult.job_id)
            .where(MatchResult.candidate_id == candidate_id)
            .order_by(MatchResult.created_at.desc())
        ).all()
    ]


def delete_candidate(db: Session, candidate: Candidate) -> int:
    """
    Permanently delete a candidate and their match results (e.g. on a data-removal request).
    The analyses they appeared in keep their other results; each analysis' resume count and
    average score are recalculated so the history stays accurate. Returns the number of
    analyses that were updated.
    """
    from app.models import AnalysisHistory

    analysis_ids = list(db.scalars(select(MatchResult.analysis_id).where(MatchResult.candidate_id == candidate.id)))
    db.delete(candidate)  # ON DELETE CASCADE removes the match_results rows
    db.flush()
    for analysis in db.scalars(select(AnalysisHistory).where(AnalysisHistory.id.in_(analysis_ids))):
        count, average = db.execute(
            select(func.count(), func.avg(MatchResult.final_score)).where(MatchResult.analysis_id == analysis.id)
        ).one()
        analysis.total_resumes = count
        analysis.average_score = round(float(average), 2) if average is not None else None
    db.commit()
    return len(analysis_ids)


def find_match(
    db: Session, candidate_id: uuid.UUID, job_id: uuid.UUID, analysis_id: uuid.UUID | None = None
) -> MatchResult | None:
    """This candidate's result for a job: from a specific analysis, or the most recent one."""
    query = select(MatchResult).where(MatchResult.candidate_id == candidate_id, MatchResult.job_id == job_id)
    if analysis_id is not None:
        query = query.where(MatchResult.analysis_id == analysis_id)
    return db.scalars(query.order_by(MatchResult.created_at.desc()).limit(1)).first()
