"""Document parsing package: turns uploaded PDF/DOCX files into plain text and candidate data."""
from pathlib import Path

from app.parser.docx_parser import extract_text_from_docx
from app.parser.errors import CorruptedFileError, DocumentParseError, EmptyDocumentError, OCRRequiredError
from app.parser.pdf_parser import extract_text_from_pdf

__all__ = [
    "extract_text",
    "DocumentParseError",
    "CorruptedFileError",
    "EmptyDocumentError",
    "OCRRequiredError",
]

# Minimum characters for a document to be considered a resume rather than noise.
MIN_RESUME_CHARS = 80


def extract_text(source: str | Path | bytes, extension: str | None = None) -> tuple[str, dict]:
    """
    Extract raw text from a PDF or DOCX.

    `source` is a file path or the file's bytes. For bytes, pass `extension`
    (".pdf" or ".docx"); for a path it is taken from the file name.
    """
    suffix = (extension or (Path(source).suffix if not isinstance(source, bytes) else "")).lower()
    if suffix == ".pdf":
        text, meta = extract_text_from_pdf(source)
    elif suffix == ".docx":
        text, meta = extract_text_from_docx(source)
    else:
        raise DocumentParseError(f"Unsupported file type '{suffix}'. Only PDF and DOCX are accepted.")

    if len(text.strip()) < MIN_RESUME_CHARS:
        raise EmptyDocumentError("The document contains too little text to be a resume.")
    return text, meta
