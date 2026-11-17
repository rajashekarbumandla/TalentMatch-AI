"""
Bulk resume upload: validate -> parse -> save, one file at a time, with a result per file.

A batch can partially succeed: a damaged or scanned PDF gets an error message while
the other resumes are still processed. All successfully parsed candidates are saved
in ONE transaction at the end. Files with identical content in the same batch are
stored once (later copies are reported as duplicates).

Privacy: only counts are logged, never names, emails or resume text. The original
files are not stored; only the extracted text and structured data are.
"""
import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.config import settings
from app.parser import DocumentParseError
from app.parser.resume_parser import parse_resume
from app.services.candidate_service import build_candidate
from app.utils.file_validator import FileValidationError, sanitize_filename, validate_resume_file

logger = logging.getLogger(__name__)


class UploadError(ValueError):
    """The batch as a whole is invalid (no files, too many files)."""


@dataclass
class UploadedFile:
    filename: str
    content: bytes  # at most MAX_FILE_SIZE + 1 bytes are read, so huge uploads can't exhaust memory


@dataclass
class FileOutcome:
    filename: str
    status: str  # parsed | duplicate | error
    size_bytes: int = 0
    candidate_id: str | None = None
    duplicate_of: str | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    skills: list[str] = field(default_factory=list)
    total_experience: float | None = None
    experience_method: str | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def process_resume_batch(db: Session, files: list[UploadedFile], *, owner_id) -> list[FileOutcome]:
    """Validate, parse and store a batch; every stored candidate belongs to `owner_id` (the uploading HR)."""
    if not files:
        raise UploadError("No files were uploaded. Select at least one PDF or DOCX resume.")
    if len(files) > settings.MAX_FILES_PER_BATCH:
        raise UploadError(
            f"{len(files)} files were uploaded; the maximum per batch is {settings.MAX_FILES_PER_BATCH}."
        )

    outcomes: list[FileOutcome] = []
    candidates = []
    first_by_hash: dict[str, FileOutcome] = {}
    duplicates: list[tuple[FileOutcome, FileOutcome]] = []  # (duplicate, first copy)
    for upload in files:
        outcome = FileOutcome(filename=sanitize_filename(upload.filename) or "(unnamed file)", status="error",
                              size_bytes=len(upload.content))
        outcomes.append(outcome)
        try:
            validated = validate_resume_file(upload.filename, upload.content)
            if validated.sha256 in first_by_hash:
                outcome.status = "duplicate"
                outcome.duplicate_of = first_by_hash[validated.sha256].filename
                duplicates.append((outcome, first_by_hash[validated.sha256]))
                continue
            parsed = parse_resume(validated.content, validated.extension)
        except (FileValidationError, DocumentParseError) as exc:
            outcome.error = str(exc)
            continue
        except Exception as exc:  # unexpected parser failure: report it, keep going with the batch
            logger.warning("Unexpected error while parsing an uploaded file: %s", type(exc).__name__)
            outcome.error = "This file could not be processed. Please check that it is a valid resume."
            continue

        candidate = build_candidate(parsed, validated.filename, validated.sha256, owner_id=owner_id)
        db.add(candidate)
        candidates.append((candidate, outcome))
        first_by_hash[validated.sha256] = outcome
        outcome.status = "parsed"
        outcome.filename = validated.filename
        outcome.name, outcome.email, outcome.phone = parsed.name, parsed.email, parsed.phone
        outcome.skills = parsed.skills
        outcome.total_experience = parsed.total_experience_years
        outcome.experience_method = parsed.experience_method
        outcome.warnings = parsed.warnings

    if candidates:
        try:
            db.flush()  # sends the INSERTs (batched) and assigns the UUIDs
            for candidate, outcome in candidates:
                outcome.candidate_id = str(candidate.id)
            for duplicate, first_copy in duplicates:  # a duplicate points at the stored first copy
                duplicate.candidate_id = first_copy.candidate_id
            db.commit()
        except Exception:
            db.rollback()
            raise

    logger.info(
        "Resume batch processed: %d files, %d parsed, %d duplicates, %d failed",
        len(outcomes),
        sum(o.status == "parsed" for o in outcomes),
        sum(o.status == "duplicate" for o in outcomes),
        sum(o.status == "error" for o in outcomes),
    )
    return outcomes
