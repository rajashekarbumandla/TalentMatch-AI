"""
Dashboard statistics for ONE HR, computed with SQL aggregates on their own data
(nothing hardcoded, nothing from other HRs).

Ownership: jobs and candidates carry owner_id; analyses and match results belong to
an HR through their job. Round trips are kept low: all headline counts come from
ONE query of scalar subqueries.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.matching.ranking import RankingFilters, rank_candidates
from app.models import AnalysisHistory, Candidate, Job, MatchResult

SCORE_BUCKETS = ["0-20", "20-40", "40-60", "60-80", "80-100"]


def _own_matches(owner_id: uuid.UUID):
    """match_results rows of this HR (via the job they belong to)."""
    return select(MatchResult).join(Job, Job.id == MatchResult.job_id).where(Job.owner_id == owner_id).subquery()


def headline_counts(db: Session, owner_id: uuid.UUID, high_match_threshold: float) -> dict:
    matches = _own_matches(owner_id)
    row = db.execute(select(
        select(func.count()).select_from(Job).where(Job.owner_id == owner_id).scalar_subquery().label("total_jobs"),
        select(func.count()).select_from(Candidate).where(Candidate.owner_id == owner_id).scalar_subquery().label("total_candidates"),
        select(func.count()).select_from(AnalysisHistory).join(Job, Job.id == AnalysisHistory.job_id)
        .where(Job.owner_id == owner_id).scalar_subquery().label("total_analyses"),
        select(func.count(func.distinct(matches.c.candidate_id))).scalar_subquery().label("resumes_analyzed"),
        select(func.count()).select_from(matches).scalar_subquery().label("total_matches"),
        select(func.avg(matches.c.final_score)).scalar_subquery().label("average_score"),
        select(func.count(func.distinct(matches.c.candidate_id)))
        .where(matches.c.final_score >= high_match_threshold).scalar_subquery().label("high_match_candidates"),
    )).one()
    data = dict(row._mapping)
    data["average_score"] = round(float(data["average_score"]), 2) if data["average_score"] is not None else None
    return data


def score_distribution(db: Session, owner_id: uuid.UUID) -> list[dict]:
    """How many of this HR's candidate results fall in each 20-point band."""
    matches = _own_matches(owner_id)
    bucket = func.least(cast(func.floor(matches.c.final_score / 20), Integer), 4).label("bucket")
    counts = dict(db.execute(select(bucket, func.count()).select_from(matches).group_by(bucket)).all())
    return [{"range": label, "count": counts.get(index, 0)} for index, label in enumerate(SCORE_BUCKETS)]


def _own_analyses(owner_id: uuid.UUID):
    return select(AnalysisHistory).join(Job, Job.id == AnalysisHistory.job_id).where(Job.owner_id == owner_id)


def recent_analyses(db: Session, owner_id: uuid.UUID, limit: int = 5) -> list[dict]:
    rows = db.execute(
        select(AnalysisHistory, Job.job_title)
        .join(Job, Job.id == AnalysisHistory.job_id)
        .where(Job.owner_id == owner_id)
        .order_by(AnalysisHistory.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": a.id, "job_id": a.job_id, "job_title": title, "total_resumes": a.total_resumes,
            "average_score": a.average_score, "created_at": a.created_at,
        }
        for a, title in rows
    ]


def activity_by_day(db: Session, owner_id: uuid.UUID, days: int = 30) -> list[dict]:
    """This HR's analyses and resumes analysed per day over the last `days` days (UTC), including empty days."""
    since = datetime.now(timezone.utc) - timedelta(days=days - 1)
    day = func.date(func.timezone("UTC", AnalysisHistory.created_at)).label("day")
    rows = db.execute(
        select(day, func.count(), func.sum(AnalysisHistory.total_resumes))
        .join(Job, Job.id == AnalysisHistory.job_id)
        .where(Job.owner_id == owner_id)
        .where(AnalysisHistory.created_at >= since.replace(hour=0, minute=0, second=0, microsecond=0))
        .group_by(day)
    ).all()
    by_day = {d: (count, int(resumes or 0)) for d, count, resumes in rows}
    result = []
    for offset in range(days):
        current = (since + timedelta(days=offset)).date()
        count, resumes = by_day.get(current, (0, 0))
        result.append({"date": current.isoformat(), "analyses": count, "resumes": resumes})
    return result


def latest_ranking_overview(db: Session, owner_id: uuid.UUID, top: int = 10) -> dict | None:
    """Top candidates of this HR's most recent analysis (for the ranking chart)."""
    latest = db.scalars(_own_analyses(owner_id).order_by(AnalysisHistory.created_at.desc()).limit(1)).first()
    if latest is None:
        return None
    page = rank_candidates(db, latest.id, RankingFilters(top=top, limit=top))
    return {
        "analysis_id": latest.id,
        "job_id": latest.job_id,
        "job_title": latest.job.job_title,
        "candidates": [
            {"rank": i.rank, "candidate_id": i.candidate.id, "name": i.candidate.name, "final_score": i.match.final_score}
            for i in page.items
        ],
    }


def get_dashboard_stats(db: Session, *, owner_id: uuid.UUID) -> dict:
    threshold = settings.HIGH_MATCH_THRESHOLD
    return {
        **headline_counts(db, owner_id, threshold),
        "high_match_threshold": threshold,
        "score_distribution": score_distribution(db, owner_id),
        "recent_analyses": recent_analyses(db, owner_id),
        "activity": activity_by_day(db, owner_id),
        "ranking_overview": latest_ranking_overview(db, owner_id),
    }
