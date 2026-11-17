"""
PDF text extraction using PyMuPDF.

Strategy:
1. Open the PDF from bytes (uploads never need to be written to disk) or from a path.
2. Extract the text layer page by page; `sort=True` returns blocks in natural
   reading order (top-to-bottom, left-to-right).
3. If the document has (almost) no text layer it is probably a scanned image.
   -> Run the optional Tesseract OCR fallback, or raise OCRRequiredError so the
      recruiter knows exactly why the resume could not be processed.
"""
from pathlib import Path

import pymupdf  # PyMuPDF (formerly imported as "fitz")

from app.config import settings
from app.parser import ocr_parser
from app.parser.errors import CorruptedFileError, EmptyDocumentError, OCRRequiredError


def _open_pdf(source: str | Path | bytes) -> pymupdf.Document:
    try:
        if isinstance(source, bytes):
            return pymupdf.open(stream=source, filetype="pdf")
        return pymupdf.open(str(source))
    except Exception as exc:  # PyMuPDF raises several different types for damaged files
        raise CorruptedFileError("The PDF file is damaged or is not a valid PDF.") from exc


def extract_pages_from_pdf(doc: pymupdf.Document) -> list[str]:
    """Return the text of each page, in page order."""
    try:
        return [page.get_text("text", sort=True) for page in doc]
    except Exception as exc:
        raise CorruptedFileError("The PDF could not be read (damaged content).") from exc


def extract_text_from_pdf(source: str | Path | bytes) -> tuple[str, dict]:
    """Return (text, metadata). Metadata: page count, characters per page, whether OCR was used."""
    doc = _open_pdf(source)
    with doc:
        if doc.needs_pass:
            raise CorruptedFileError("The PDF is password protected. Please upload an unlocked copy.")
        if doc.page_count == 0:
            raise EmptyDocumentError("The PDF has no pages.")

        pages = extract_pages_from_pdf(doc)
        text = "\n".join(pages).strip()
        meta = {
            "pages": doc.page_count,
            "page_char_counts": [len(page.strip()) for page in pages],
            "ocr_used": False,
        }

        # Heuristic: average characters per page below threshold => scanned document.
        if len(text) >= settings.MIN_TEXT_CHARS_PER_PAGE * doc.page_count:
            return text, meta

        if settings.OCR_ENABLED and ocr_parser.is_ocr_available():
            ocr_text = ocr_parser.ocr_pdf(doc)
            if ocr_text.strip():
                meta["ocr_used"] = True
                return ocr_text.strip(), meta
            raise EmptyDocumentError("OCR ran on this scanned PDF but found no readable text.")

        has_images = any(page.get_images() for page in doc)
        if not text and not has_images:
            raise EmptyDocumentError("The PDF is empty (its pages contain no text or images).")
        if text:
            # Some text exists but too little to be a real resume.
            raise EmptyDocumentError(
                "The PDF contains almost no extractable text. If it is a scanned resume, "
                "install Tesseract OCR to process it."
            )
        raise OCRRequiredError(
            "This PDF appears to be scanned (it contains no text layer). "
            "OCR is required: install Tesseract OCR and set OCR_ENABLED=true."
        )
