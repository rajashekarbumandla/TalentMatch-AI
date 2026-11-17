"""
Job service: create, read, edit and delete Job Descriptions in Supabase.

Routes (Phase 7) stay thin and call these functions; keeping the database logic
here makes it easy to test and to explain.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, defer

from app.models import AnalysisHistory, Job
from app.schemas import JobCreate, JobUpdate, remove_required_from_preferred


def create_job(db: Session, data: JobCreate, *, owner_id: uuid.UUID) -> Job:
    """Save a (recruiter-reviewed) job description and its requirements, owned by the logged-in HR."""
    job = Job(**data.model_dump(), owner_id=owner_id)
    db.add(job)
    db.commit()
    db.refresh(job)  # load database-generated values (created_at, updated_at)
    return job


def get_job(db: Session, job_id: uuid.UUID, *, owner_id: uuid.UUID) -> Job | None:
    """The job, only if it belongs to this HR (another HR's job behaves as 'not found')."""
    job = db.get(Job, job_id)
    return job if job is not None and job.owner_id == owner_id else None


def list_jobs(db: Session, *, owner_id: uuid.UUID) -> list[Job]:
    return list(db.scalars(select(Job).where(Job.owner_id == owner_id).order_by(Job.created_at.desc())))


def list_jobs_with_stats(db: Session, *, owner_id: uuid.UUID) -> list[dict]:
    """This HR's jobs (newest first) with how many analyses ran and when the latest one was, in one query."""
    stats = (
        select(
            AnalysisHistory.job_id,
            func.count().label("analysis_count"),
            func.max(AnalysisHistory.created_at).label("latest_analysis_at"),
        )
        .group_by(AnalysisHistory.job_id)
        .subquery()
    )
    rows = db.execute(
        select(Job, stats.c.analysis_count, stats.c.latest_analysis_at)
        .outerjoin(stats, stats.c.job_id == Job.id)
        .where(Job.owner_id == owner_id)
        .options(defer(Job.description))
        .order_by(Job.created_at.desc())
    ).all()
    return [
        {"job": job, "analysis_count": count or 0, "latest_analysis_at": latest}
        for job, count, latest in rows
    ]


def update_job(db: Session, job: Job, data: JobUpdate) -> Job:
    """
    Apply a partial edit. Only fields the recruiter actually sent are changed
    (`exclude_unset`), so sending {"minimum_experience": 4} leaves skills untouched.
    Sending "minimum_experience": null explicitly removes the requirement.
    """
    changes = data.model_dump(exclude_unset=True)
    for field_name in ("job_title", "description", "required_skills", "preferred_skills",
                       "responsibilities", "keywords"):
        if field_name in changes and changes[field_name] is None:
            changes.pop(field_name)  # these columns cannot be NULL; ignore an explicit null
    for field_name, value in changes.items():
        setattr(job, field_name, value)
    # Re-check after merging: editing only required_skills may now overlap existing preferred skills.
    job.preferred_skills = remove_required_from_preferred(job.required_skills, job.preferred_skills)
    db.commit()
    db.refresh(job)
    return job


def delete_job(db: Session, job: Job) -> None:
    """Delete a job; its analyses and match results are removed by ON DELETE CASCADE."""
    db.delete(job)
    db.commit()
