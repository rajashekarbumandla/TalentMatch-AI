"""
Upload validation: decide whether an uploaded file is a genuine, safe PDF/DOCX
*before* any parser touches it.

Checks, in order:
1. A usable filename (any folder path is stripped, so "../../x.pdf" becomes "x.pdf").
2. The extension is .pdf or .docx.
3. The file is not empty and not larger than MAX_FILE_SIZE_MB.
4. The content really is that type ("magic bytes"): a renamed .exe -> .pdf is rejected.
5. DOCX only: the ZIP is a real Word document and is not a "zip bomb"
   (a tiny file that expands to gigabytes).

Uploaded content is only ever *read* as data; nothing in it is executed.
"""
import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePath

from app.config import settings

# A DOCX is a ZIP archive; refuse archives that expand beyond this size.
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024


class FileValidationError(ValueError):
    """Raised with a message that is safe to show to the recruiter."""


@dataclass
class ValidatedFile:
    filename: str
    extension: str  # ".pdf" or ".docx"
    size_bytes: int
    sha256: str
    content: bytes


def sanitize_filename(filename: str | None) -> str:
    """Keep only the base name and strip characters that are unsafe in file names."""
    name = PurePath((filename or "").replace("\\", "/")).name
    name = re.sub(r"[\x00-\x1f<>:\"|?*]", "", name).strip(" .")
    if len(name) > 150:  # keep the extension when shortening very long names
        stem, dot, ext = name.rpartition(".")
        name = (stem[: 150 - len(ext) - 1] + dot + ext) if dot else name[:150]
    return name


def _looks_like_pdf(content: bytes) -> bool:
    # The PDF header must appear near the start (some generators add a few junk bytes).
    return b"%PDF-" in content[:1024]


def _check_docx(content: bytes) -> None:
    if not content.startswith(b"PK\x03\x04"):
        raise FileValidationError("The file has a .docx extension but is not a Word document.")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
            if "word/document.xml" not in names:
                raise FileValidationError("The file is a ZIP archive but not a Word (.docx) document.")
            uncompressed = sum(info.file_size for info in archive.infolist())
            if uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise FileValidationError("The Word document is too large when decompressed.")
    except zipfile.BadZipFile as exc:
        raise FileValidationError("The Word document is damaged and cannot be opened.") from exc


def validate_document_file(filename: str | None, content: bytes) -> ValidatedFile:
    """Validate one uploaded PDF/DOCX (resume or JD). Returns a ValidatedFile or raises FileValidationError."""
    safe_name = sanitize_filename(filename)
    if not safe_name:
        raise FileValidationError("The file has no name.")

    extension = PurePath(safe_name).suffix.lower()
    if extension == ".doc":
        raise FileValidationError("Old Word (.doc) files are not supported. Please save the resume as .docx or PDF.")
    if extension not in settings.ALLOWED_EXTENSIONS:
        shown = extension or "(no extension)"
        raise FileValidationError(f"Unsupported file format '{shown}'. Only PDF and DOCX files are accepted.")

    size = len(content)
    if size == 0:
        raise FileValidationError("The file is empty (0 bytes).")
    if size > settings.max_file_size_bytes:
        raise FileValidationError(
            f"The file is {size / 1024 / 1024:.1f} MB; the maximum allowed size is {settings.MAX_FILE_SIZE_MB:g} MB."
        )

    if extension == ".pdf" and not _looks_like_pdf(content):
        raise FileValidationError("The file has a .pdf extension but is not a valid PDF.")
    if extension == ".docx":
        _check_docx(content)

    return ValidatedFile(
        filename=safe_name,
        extension=extension,
        size_bytes=size,
        sha256=hashlib.sha256(content).hexdigest(),
        content=content,
    )


# Resumes and JDs follow the same rules; this name reads better at resume call sites.
validate_resume_file = validate_document_file
