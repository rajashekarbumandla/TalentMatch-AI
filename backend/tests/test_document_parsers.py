"""Tests for PDF (PyMuPDF) and DOCX (python-docx) text extraction, including failure cases."""
import io

import docx
import pymupdf
import pytest
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

from app.parser import (
    CorruptedFileError,
    DocumentParseError,
    EmptyDocumentError,
    OCRRequiredError,
    extract_text,
)
from app.parser import ocr_parser
from app.parser.docx_parser import extract_text_from_docx
from app.parser.pdf_parser import extract_text_from_pdf

RESUME_LINE = "Jane Example - Python developer with FastAPI, SQL and Docker experience. "


def make_pdf(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def make_docx(build) -> bytes:
    document = docx.Document()
    build(document)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


# --- PDF -----------------------------------------------------------------------------------------
def test_pdf_text_extracted_page_by_page():
    text, meta = extract_text_from_pdf(make_pdf(["Page one " + RESUME_LINE, "Page two " + RESUME_LINE]))
    assert "Page one" in text and "Page two" in text
    assert text.index("Page one") < text.index("Page two")
    assert meta["pages"] == 2 and len(meta["page_char_counts"]) == 2 and not meta["ocr_used"]


def test_pdf_from_path(tmp_path):
    path = tmp_path / "resume.pdf"
    path.write_bytes(make_pdf([RESUME_LINE * 2]))
    text, _ = extract_text(path)
    assert "FastAPI" in text


def test_blank_pdf_is_reported_as_empty():
    with pytest.raises(EmptyDocumentError, match="empty"):
        extract_text_from_pdf(make_pdf([""]))


def test_scanned_pdf_without_ocr_asks_for_ocr(monkeypatch):
    monkeypatch.setattr(ocr_parser, "is_ocr_available", lambda: False)
    doc = pymupdf.open()
    page = doc.new_page()
    image = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 200), False)
    image.clear_with(200)
    page.insert_image(pymupdf.Rect(50, 50, 250, 250), pixmap=image)
    with pytest.raises(OCRRequiredError, match="scanned"):
        extract_text_from_pdf(doc.tobytes())


def test_corrupted_pdf_rejected():
    with pytest.raises(CorruptedFileError):
        extract_text_from_pdf(b"%PDF-1.7 this is not really a pdf at all")


def test_password_protected_pdf_rejected():
    doc = pymupdf.open(stream=make_pdf([RESUME_LINE * 2]), filetype="pdf")
    data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")
    with pytest.raises(CorruptedFileError, match="password"):
        extract_text_from_pdf(data)


def test_too_little_text_is_not_a_resume():
    with pytest.raises(EmptyDocumentError, match="too little text"):
        extract_text(make_pdf(["Just a short line of text that is still above the scan threshold"]), ".pdf")


# --- DOCX ----------------------------------------------------------------------------------------
def test_docx_paragraphs_tables_header_and_bullets():
    def build(document):
        document.sections[0].header.paragraphs[0].text = "Header Name"
        document.add_paragraph("Experience")
        document.add_paragraph("Built APIs with FastAPI", style="List Bullet")
        table = document.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = "Left column: Python"
        table.rows[0].cells[1].text = "Right column: Docker"

    text, _ = extract_text_from_docx(make_docx(build))
    lines = text.split("\n")
    assert lines[0] == "Header Name"  # header text comes first
    assert "- Built APIs with FastAPI" in lines  # list items get a bullet marker
    assert "Left column: Python" in lines and "Right column: Docker" in lines
    assert lines.index("Experience") < lines.index("Left column: Python")  # document order kept


def test_docx_merged_table_cells_not_duplicated():
    def build(document):
        table = document.add_table(rows=1, cols=3)
        merged = table.rows[0].cells[0].merge(table.rows[0].cells[1])
        merged.text = "Merged skills cell"

    text, _ = extract_text_from_docx(make_docx(build))
    assert text.count("Merged skills cell") == 1


def test_docx_text_box_content_extracted():
    def build(document):
        run = document.add_paragraph("Main body").add_run()
        run._r.append(parse_xml(
            f"<w:txbxContent {nsdecls('w')}><w:p><w:r><w:t>Sidebar: Kubernetes</w:t></w:r></w:p></w:txbxContent>"
        ))

    text, _ = extract_text_from_docx(make_docx(build))
    assert "Sidebar: Kubernetes" in text


def test_empty_docx_rejected():
    with pytest.raises(EmptyDocumentError, match="empty"):
        extract_text_from_docx(make_docx(lambda document: None))


def test_corrupted_docx_rejected():
    with pytest.raises(CorruptedFileError):
        extract_text_from_docx(b"PK\x03\x04 broken zip content")


def test_unsupported_extension_rejected():
    with pytest.raises(DocumentParseError, match="Unsupported"):
        extract_text(b"plain text", ".txt")
