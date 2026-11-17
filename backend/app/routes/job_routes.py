"""Job Description endpoints: analyze, create, list, read, update, delete (the logged-in HR's jobs only)."""
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.config import settings
from app.database import get_db
from app.models import User
from app.nlp.jd_analyzer import analyze_job_description, analyze_job_description_file
from app.schemas import JDAnalysisResponse, JDAnalyzeRequest, JobCreate, JobListItem, JobRead, JobUpdate
from app.services import job_service

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


def get_job_or_404(db: Session, job_id: uuid.UUID, user: User):
    """This HR's job, or 404. Another HR's job is reported as 'not found' so its existence isn't revealed."""
    job = job_service.get_job(db, job_id, owner_id=user.id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


@router.post("/analyze", response_model=JDAnalysisResponse, summary="Extract requirements from JD text")
def analyze_jd_text(payload: JDAnalyzeRequest, _: User = Depends(get_current_user)) -> JDAnalysisResponse:
    """Returns *suggested* requirements. Nothing is saved; the recruiter edits them, then calls POST /api/jobs/."""
    return JDAnalysisResponse(**analyze_job_description(payload.description, payload.job_title).to_dict())


@router.post("/analyze-file", response_model=JDAnalysisResponse, summary="Extract requirements from a PDF/DOCX JD")
def analyze_jd_file(
    file: UploadFile = File(...), job_title: str | None = Form(default=None), _: User = Depends(get_current_user)
) -> JDAnalysisResponse:
    content = file.file.read(settings.max_file_size_bytes + 1)  # never read more than the limit + 1 byte
    return JDAnalysisResponse(**analyze_job_description_file(content, file.filename or "", job_title).to_dict())


@router.post("/", response_model=JobRead, status_code=status.HTTP_201_CREATED, summary="Save a job description")
def create_job(payload: JobCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return job_service.create_job(db, payload, owner_id=user.id)


@router.get("/", response_model=list[JobListItem], summary="List your saved jobs")
def list_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = []
    for row in job_service.list_jobs_with_stats(db, owner_id=user.id):
        job = row["job"]
        items.append(JobListItem(
            id=job.id, job_title=job.job_title, required_skills=job.required_skills,
            preferred_skills=job.preferred_skills, minimum_experience=job.minimum_experience,
            education_requirements=job.education_requirements, created_at=job.created_at,
            updated_at=job.updated_at, analysis_count=row["analysis_count"],
            latest_analysis_at=row["latest_analysis_at"],
        ))
    return items


@router.get("/{job_id}", response_model=JobRead, summary="Get one job")
def get_job(job_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_job_or_404(db, job_id, user)


@router.put("/{job_id}", response_model=JobRead, summary="Edit a job (only the fields sent are changed)")
def update_job(job_id: uuid.UUID, payload: JobUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return job_service.update_job(db, get_job_or_404(db, job_id, user), payload)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a job and its analyses")
def delete_job(job_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    job_service.delete_job(db, get_job_or_404(db, job_id, user))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
