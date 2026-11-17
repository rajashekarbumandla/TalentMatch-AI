"""Resume upload endpoint (uploaded candidates belong to the logged-in HR)."""
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import UploadFileResult, UploadResponse
from app.services.resume_service import UploadedFile, process_resume_batch

router = APIRouter(prefix="/api/resumes", tags=["Resumes"])


@router.post("/upload", response_model=UploadResponse, summary="Upload and parse multiple PDF/DOCX resumes")
def upload_resumes(
    files: list[UploadFile] = File(..., description="PDF or DOCX resumes"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Validates and parses every file and stores the extracted candidate data.
    Each file gets its own result, so one damaged file does not reject the batch.
    Use the returned `candidate_ids` with POST /api/analyze/{job_id}.
    """
    # Read at most limit+1 bytes per file: enough to detect "too large" without loading huge files.
    uploads = [UploadedFile(f.filename or "", f.file.read(settings.max_file_size_bytes + 1)) for f in files]
    outcomes = process_resume_batch(db, uploads, owner_id=user.id)
    parsed = [o for o in outcomes if o.status == "parsed"]
    return UploadResponse(
        total_files=len(outcomes),
        parsed=len(parsed),
        duplicates=sum(o.status == "duplicate" for o in outcomes),
        failed=sum(o.status == "error" for o in outcomes),
        candidate_ids=[o.candidate_id for o in parsed],
        files=[UploadFileResult(**o.__dict__) for o in outcomes],
    )
