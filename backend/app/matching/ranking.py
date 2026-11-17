"""
Candidate ranking, done in PostgreSQL (not in the browser).

The core query (simplified):

    WITH ranked AS (
        SELECT id, RANK() OVER (ORDER BY final_score DESC) AS rank
        FROM match_results WHERE analysis_id = :analysis_id
    )
    SELECT match_results.*, candidates.*, ranked.rank, COUNT(*) OVER () AS filtered_count
    FROM match_results
    JOIN ranked     ON ranked.id = match_results.id
    JOIN candidates ON candidates.id = match_results.candidate_id
    WHERE <search / filters>
    ORDER BY <sort>, <tie-breakers>
    LIMIT ... OFFSET ...

Rules
- RANK() gives equal scores the same rank: 91.5, 84.2, 84.2, 76.8 -> 1, 2, 2, 4.
- Ranks are computed over the WHOLE analysis before filtering, so a candidate who is
  #7 stays #7 when the recruiter searches or filters.
- "Top N" means rank <= N: a tie at position N is included instead of being cut arbitrarily.
- Equal scores are always listed in the same order, using tie-breakers:
  skills score, experience score, semantic score (higher first), then name, then id.
"""
import uuid
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, defer

from app.models import Candidate, MatchResult


class SortField(str, Enum):
    rank = "rank"  # final score, highest first (default)
    final_score = "final_score"
    name = "name"
    relevant_experience = "relevant_experience"
    total_experience = "total_experience"
    skills_score = "skills_score"
    semantic_score = "semantic_score"
    experience_score = "experience_score"


@dataclass
class RankingFilters:
    search: str | None = None  # matches candidate name or email (case-insensitive)
    min_score: float | None = None
    max_score: float | None = None
    min_experience: float | None = None  # relevant experience, in years
    max_experience: float | None = None
    top: int | None = None  # 5, 10, ... -> rank <= top; None = all
    sort_by: SortField = SortField.rank
    descending: bool | None = None  # None = the natural direction for the field
    limit: int | None = None
    offset: int = 0


@dataclass
class RankedCandidate:
    rank: int
    match: MatchResult
    candidate: Candidate


@dataclass
class RankingPage:
    items: list[RankedCandidate]
    filtered_count: int  # candidates matching the filters (before limit/offset)


# Higher-is-better columns are sorted descending by default; text ascending.
_SORT_COLUMNS = {
    SortField.rank: (MatchResult.final_score, True),
    SortField.final_score: (MatchResult.final_score, True),
    SortField.name: (Candidate.name, False),
    SortField.relevant_experience: (MatchResult.relevant_experience, True),
    SortField.total_experience: (Candidate.total_experience, True),
    SortField.skills_score: (MatchResult.skills_score, True),
    SortField.semantic_score: (MatchResult.semantic_score, True),
    SortField.experience_score: (MatchResult.experience_score, True),
}
_TIE_BREAKERS = (
    MatchResult.final_score.desc(),
    MatchResult.skills_score.desc().nulls_last(),
    MatchResult.experience_score.desc().nulls_last(),
    MatchResult.semantic_score.desc().nulls_last(),
    Candidate.name.asc().nulls_last(),
    Candidate.id.asc(),
)


def escape_like(text: str) -> str:
    """Treat % and _ typed by the user as literal characters, not SQL wildcards."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def ranking_query(analysis_id: uuid.UUID, filters: RankingFilters) -> Select:
    ranked = (
        select(
            MatchResult.id.label("match_id"),
            func.rank().over(order_by=MatchResult.final_score.desc()).label("rank"),
        )
        .where(MatchResult.analysis_id == analysis_id)
        .cte("ranked")
    )
    query = (
        select(MatchResult, Candidate, ranked.c.rank, func.count().over().label("filtered_count"))
        .join(ranked, ranked.c.match_id == MatchResult.id)
        .join(Candidate, Candidate.id == MatchResult.candidate_id)
    )

    if filters.search and filters.search.strip():
        pattern = f"%{escape_like(filters.search.strip())}%"
        query = query.where(or_(Candidate.name.ilike(pattern, escape="\\"), Candidate.email.ilike(pattern, escape="\\")))
    if filters.min_score is not None:
        query = query.where(MatchResult.final_score >= filters.min_score)
    if filters.max_score is not None:
        query = query.where(MatchResult.final_score <= filters.max_score)
    if filters.min_experience is not None:
        query = query.where(MatchResult.relevant_experience >= filters.min_experience)
    if filters.max_experience is not None:
        query = query.where(MatchResult.relevant_experience <= filters.max_experience)
    if filters.top is not None:
        query = query.where(ranked.c.rank <= filters.top)

    column, natural_descending = _SORT_COLUMNS[filters.sort_by]
    descending = natural_descending if filters.descending is None else filters.descending
    primary = column.desc().nulls_last() if descending else column.asc().nulls_last()
    query = query.order_by(primary, *_TIE_BREAKERS)

    if filters.offset:
        query = query.offset(filters.offset)
    if filters.limit is not None:
        query = query.limit(filters.limit)
    return query


def rank_candidates(db: Session, analysis_id: uuid.UUID, filters: RankingFilters | None = None) -> RankingPage:
    """
    Ranked, filtered, sorted candidates of one analysis, in a single database round trip.
    The full resume text is not needed for a ranking table, so it is not downloaded
    (defer); it loads automatically only if something accesses it.
    """
    query = ranking_query(analysis_id, filters or RankingFilters()).options(defer(Candidate.resume_text))
    rows = db.execute(query).all()
    items = [RankedCandidate(rank=row.rank, match=row.MatchResult, candidate=row.Candidate) for row in rows]
    return RankingPage(items=items, filtered_count=rows[0].filtered_count if rows else 0)


def get_ranked_candidate(db: Session, analysis_id: uuid.UUID, candidate_id: uuid.UUID) -> RankedCandidate | None:
    """One candidate's result within an analysis, including their rank in that analysis."""
    query = ranking_query(analysis_id, RankingFilters()).where(MatchResult.candidate_id == candidate_id)
    row = db.execute(query).first()
    return RankedCandidate(rank=row.rank, match=row.MatchResult, candidate=row.Candidate) if row else None
