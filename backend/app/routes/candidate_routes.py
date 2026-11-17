"""Candidate endpoints: list, details, delete, and one candidate's analysis for a job (logged-in HR's candidates only)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.matching.ranking import get_ranked_candidate
from app.models import User
from app.routes.job_routes import get_job_or_404
from app.routes.serializers import analysis_summary, candidate_detail, match_detail
from app.schemas import CandidateAnalysisResponse, CandidateDetail, CandidateListItem, CandidateListResponse, JobRead, round2
from app.services import candidate_service

router = APIRouter(prefix="/api/candidates", tags=["Candidates"])


def get_candidate_or_404(db: Session, candidate_id: uuid.UUID, user: User):
    """This HR's candidate, or 404 (another HR's candidate is reported as 'not found')."""
    candidate = candidate_service.get_candidate(db, candidate_id, owner_id=user.id)
    if candidate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found.")
    return candidate


@router.get("/", response_model=CandidateListResponse, summary="Your candidates with their best and latest scores")
def list_candidates(
    search: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total = candidate_service.list_candidates(db, owner_id=user.id, search=search, limit=limit, offset=offset)
    return CandidateListResponse(
        total=total,
        items=[
            CandidateListItem(
                id=row["candidate"].id,
                name=row["candidate"].name,
                email=row["candidate"].email,
                total_experience=row["candidate"].total_experience,
                skills=row["candidate"].extracted_skills,
                resume_filename=row["candidate"].resume_filename,
                created_at=row["candidate"].created_at,
                analyses_count=row["analyses_count"],
                best_score=round2(row["best_score"]),
                latest_score=round2(row["latest_score"]),
                latest_analysis_id=row["latest_analysis_id"],
                latest_job_id=row["latest_job_id"],
                latest_job_title=row["latest_job_title"],
            )
            for row in items
        ],
    )


@router.get("/{candidate_id}", response_model=CandidateDetail, summary="Extracted resume details of one candidate")
def get_candidate(candidate_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = get_candidate_or_404(db, candidate_id, user)
    return candidate_detail(candidate, candidate_service.candidate_match_history(db, candidate_id))


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Permanently delete a candidate's data (e.g. on request)")
def delete_candidate(candidate_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    """Removes the extracted resume data and all of this candidate's results; analysis totals are recalculated."""
    candidate_service.delete_candidate(db, get_candidate_or_404(db, candidate_id, user))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{candidate_id}/analysis/{job_id}", response_model=CandidateAnalysisResponse,
            summary="Score breakdown and explanation for one candidate and job")
def get_candidate_analysis(
    candidate_id: uuid.UUID,
    job_id: uuid.UUID,
    analysis_id: uuid.UUID | None = Query(None, description="Defaults to the candidate's most recent analysis for this job"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    candidate = get_candidate_or_404(db, candidate_id, user)
    job = get_job_or_404(db, job_id, user)
    match = candidate_service.find_match(db, candidate_id, job_id, analysis_id)
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This candidate has not been analyzed for this job.")
    ranked = get_ranked_candidate(db, match.analysis_id, candidate_id)
    return CandidateAnalysisResponse(
        candidate=candidate_detail(candidate),
        job=JobRead.model_validate(job),
        analysis=analysis_summary(match.analysis),
        match=match_detail(ranked, match.analysis.total_resumes),
    )
