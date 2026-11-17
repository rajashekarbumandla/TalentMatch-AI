"""Analysis endpoints: run an analysis, read ranked results, export CSV, list history."""
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.matching.ranking import RankingFilters, SortField, rank_candidates
from app.models import AnalysisHistory, User
from app.routes.job_routes import get_job_or_404
from app.routes.serializers import analysis_summary, ranked_candidate
from app.schemas import AnalysisSummary, AnalyzeRequest, AnalyzeResponse, JobRead, ResultsResponse
from app.services import analysis_service
from app.services.export_service import ranked_candidates_to_csv

router = APIRouter(prefix="/api", tags=["Analysis"])


def ranking_filters(
    search: str | None = Query(None, max_length=100, description="Candidate name or email contains"),
    min_score: float | None = Query(None, ge=0, le=100),
    max_score: float | None = Query(None, ge=0, le=100),
    min_experience: float | None = Query(None, ge=0, le=50, description="Minimum RELEVANT experience (years)"),
    max_experience: float | None = Query(None, ge=0, le=50),
    top: int | None = Query(None, ge=1, le=500, description="Only rank <= top (5, 10, ...); ties included"),
    sort_by: SortField = Query(SortField.rank),
    order: str | None = Query(None, pattern="^(asc|desc)$"),
    limit: int | None = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> RankingFilters:
    """Query-string parameters shared by the results and export endpoints (FastAPI dependency)."""
    return RankingFilters(
        search=search, min_score=min_score, max_score=max_score, min_experience=min_experience,
        max_experience=max_experience, top=top, sort_by=sort_by,
        descending=None if order is None else order == "desc", limit=limit, offset=offset,
    )


def resolve_analysis(db: Session, job_id: uuid.UUID, analysis_id: uuid.UUID | None, user: User) -> AnalysisHistory:
    """The requested analysis of this job, or its most recent one."""
    if analysis_id is not None:
        analysis = analysis_service.get_analysis(db, analysis_id, owner_id=user.id)
        if analysis is None or analysis.job_id != job_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found for this job.")
        return analysis
    analysis = analysis_service.latest_analysis_for_job(db, job_id)
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This job has not been analyzed yet.")
    return analysis


@router.post("/analyze/{job_id}", response_model=AnalyzeResponse, summary="Match uploaded resumes against a job")
def analyze(job_id: uuid.UUID, payload: AnalyzeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Scores the given candidates (semantic + skills + experience), saves the analysis in
    Supabase and returns the full ranking. Each call creates a new analysis.
    """
    job = get_job_or_404(db, job_id, user)
    run = analysis_service.run_analysis(db, job.id, payload.candidate_ids, owner_id=user.id)
    page = rank_candidates(db, run.analysis.id)
    return AnalyzeResponse(
        job=JobRead.model_validate(job),
        analysis=analysis_summary(run.analysis),
        total_candidates=run.analysis.total_resumes,
        filtered_count=page.filtered_count,
        items=[ranked_candidate(item) for item in page.items],
        skipped_duplicates=run.skipped_duplicates,
        missing_candidate_ids=run.missing_candidate_ids,
    )


@router.get("/results/{job_id}", response_model=ResultsResponse, summary="Ranked results for a job")
def get_results(
    job_id: uuid.UUID,
    analysis_id: uuid.UUID | None = Query(None, description="Defaults to the job's most recent analysis"),
    filters: RankingFilters = Depends(ranking_filters),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = get_job_or_404(db, job_id, user)
    analysis = resolve_analysis(db, job_id, analysis_id, user)
    page = rank_candidates(db, analysis.id, filters)
    return ResultsResponse(
        job=JobRead.model_validate(job),
        analysis=analysis_summary(analysis),
        total_candidates=analysis.total_resumes,
        filtered_count=page.filtered_count,
        items=[ranked_candidate(item) for item in page.items],
    )


@router.get("/results/{job_id}/export", summary="Download ranked results as CSV",
            response_class=Response, responses={200: {"content": {"text/csv": {}}}})
def export_results(
    job_id: uuid.UUID,
    analysis_id: uuid.UUID | None = Query(None),
    filters: RankingFilters = Depends(ranking_filters),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    job = get_job_or_404(db, job_id, user)
    analysis = resolve_analysis(db, job_id, analysis_id, user)
    page = rank_candidates(db, analysis.id, filters)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", job.job_title).strip("_").lower() or "job"
    filename = f"talentmatch_{slug}_{analysis.created_at:%Y%m%d_%H%M}.csv"
    return Response(
        content=ranked_candidates_to_csv(page.items),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/analyses/", response_model=list[AnalysisSummary], summary="Analysis history (newest first)")
def list_analyses(
    job_id: uuid.UUID | None = Query(None), limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    return [analysis_summary(a) for a in analysis_service.list_analyses(db, owner_id=user.id, job_id=job_id, limit=limit)]
