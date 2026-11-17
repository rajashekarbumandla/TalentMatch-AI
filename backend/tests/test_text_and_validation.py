"""Tests for text cleaning and upload validation (no database needed)."""
import io
import zipfile

import docx
import pytest

from app.config import settings
from app.utils.file_validator import FileValidationError, sanitize_filename, validate_resume_file
from app.utils.text_cleaner import clean_text


# --- Text cleaning -----------------------------------------------------------------------------
def test_clean_text_preserves_technical_terms():
    text = "Skills: C++, C#, .NET, Node.js, CI/CD, Java and JavaScript"
    assert clean_text(text) == text


def test_clean_text_normalises_bullets_dashes_and_spaces():
    raw = "•  Built   APIs\n\uf0b7 Wrote tests\n▪ Deployed\nJan 2020 \u2013 Present\nPython • SQL • Docker"
    assert clean_text(raw).split("\n") == [
        "- Built APIs",
        "- Wrote tests",
        "- Deployed",
        "Jan 2020 - Present",
        "Python | SQL | Docker",
    ]


def test_clean_text_removes_invisible_characters_and_ligatures():
    assert clean_text("Py\u200bthon de\u00advelopment \ufb01nance") == "Python development finance"


def test_clean_text_collapses_blank_lines_and_handles_empty():
    assert clean_text("A\n\n\n\n\nB") == "A\n\nB"
    assert clean_text("") == "" and clean_text(None) == ""


# --- Upload validation ---------------------------------------------------------------------------
def make_docx_bytes(text: str = "Hello resume") -> bytes:
    buffer = io.BytesIO()
    document = docx.Document()
    document.add_paragraph(text)
    document.save(buffer)
    return buffer.getvalue()


PDF_BYTES = b"%PDF-1.7\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def test_valid_pdf_and_docx_accepted():
    pdf = validate_resume_file("resume.pdf", PDF_BYTES)
    assert pdf.extension == ".pdf" and pdf.size_bytes == len(PDF_BYTES) and len(pdf.sha256) == 64
    word = validate_resume_file("Resume.DOCX", make_docx_bytes())
    assert word.extension == ".docx"


@pytest.mark.parametrize(
    "filename, message",
    [
        ("resume.txt", "Unsupported file format '.txt'"),
        ("resume.exe", "Unsupported file format '.exe'"),
        ("resume", "Unsupported file format '(no extension)'"),
        ("resume.doc", "Old Word (.doc) files are not supported"),
        ("", "The file has no name"),
    ],
)
def test_unsupported_formats_rejected(filename, message):
    with pytest.raises(FileValidationError, match=message.replace("(", r"\(").replace(")", r"\)").replace(".", r"\.")):
        validate_resume_file(filename, b"some content")


def test_empty_file_rejected():
    with pytest.raises(FileValidationError, match="empty"):
        validate_resume_file("resume.pdf", b"")


def test_oversized_file_rejected():
    too_big = b"%PDF-" + b"0" * (settings.max_file_size_bytes + 1)
    with pytest.raises(FileValidationError, match="maximum allowed size"):
        validate_resume_file("resume.pdf", too_big)


def test_renamed_file_with_wrong_content_rejected():
    with pytest.raises(FileValidationError, match="not a valid PDF"):
        validate_resume_file("resume.pdf", b"MZ\x90\x00 this is really an exe")
    with pytest.raises(FileValidationError, match="not a Word document"):
        validate_resume_file("resume.docx", PDF_BYTES)


def test_zip_that_is_not_a_word_document_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notes.txt", "hello")
    with pytest.raises(FileValidationError, match="not a Word"):
        validate_resume_file("resume.docx", buffer.getvalue())


def test_zip_bomb_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "<w:document/>")
        archive.writestr("word/padding.bin", b"\0" * (60 * 1024 * 1024))  # compresses to ~60 KB
    content = buffer.getvalue()
    assert len(content) < settings.max_file_size_bytes  # small on disk...
    with pytest.raises(FileValidationError, match="too large when decompressed"):
        validate_resume_file("resume.docx", content)


def test_filename_is_sanitised():
    assert sanitize_filename("../../etc/passwd.pdf") == "passwd.pdf"
    assert sanitize_filename("C:\\Users\\x\\My Resume.docx") == "My Resume.docx"
    assert sanitize_filename('bad<name>?.pdf') == "badname.pdf"
    long_name = sanitize_filename("a" * 300 + ".pdf")
    assert len(long_name) == 150 and long_name.endswith(".pdf")
