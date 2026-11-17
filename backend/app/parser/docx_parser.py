"""
DOCX text extraction using python-docx.

Resumes often put content in places a simple paragraph loop misses, so we read:
1. Page headers (many templates put the candidate's name and contacts there).
2. Body paragraphs and tables, in document order (tables = two-column layouts).
3. Text boxes (sidebars in designer templates), which python-docx does not expose.
"""
import io
import zipfile
from pathlib import Path

import docx
from docx.document import Document as DocumentType
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.parser.errors import CorruptedFileError, EmptyDocumentError


def _iter_block_items(document: DocumentType):
    """Yield paragraphs and tables in the order they appear in the document body."""
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def _paragraph_text(paragraph: Paragraph) -> str:
    """
    Paragraph text, prefixed with "- " for bulleted/numbered list items.
    Word stores bullets as list formatting (w:numPr), not as characters, so
    without this the parser could not tell description bullets from headings.
    """
    text = paragraph.text
    if not text.strip():
        return text
    properties = paragraph._p.pPr
    is_list = properties is not None and properties.numPr is not None
    style_name = (paragraph.style.name if paragraph.style is not None else "") or ""
    if is_list or style_name.lower().startswith("list"):
        return f"- {text.strip()}"
    return text


def _table_lines(table: Table) -> list[str]:
    lines = []
    for row in table.rows:
        seen = set()
        for cell in row.cells:
            # Merged cells appear multiple times in python-docx; skip repeats.
            if id(cell._tc) in seen:
                continue
            seen.add(id(cell._tc))
            for paragraph in cell.paragraphs:
                if paragraph.text.strip():
                    lines.append(_paragraph_text(paragraph))
            for nested in cell.tables:
                lines.extend(_table_lines(nested))
    return lines


def _header_lines(document: DocumentType) -> list[str]:
    lines: list[str] = []
    for section in document.sections:
        for paragraph in section.header.paragraphs:
            if paragraph.text.strip() and paragraph.text not in lines:
                lines.append(paragraph.text)
    return lines


def _text_box_lines(document: DocumentType) -> list[str]:
    """Text inside text boxes (w:txbxContent). Word stores each box twice (modern + fallback), so de-duplicate."""
    lines: list[str] = []
    for box in document.element.body.iter(qn("w:txbxContent")):
        for paragraph in box.iter(qn("w:p")):
            text = "".join(node.text or "" for node in paragraph.iter(qn("w:t")))
            if text.strip() and text not in lines:
                lines.append(text)
    return lines


def extract_text_from_docx(source: str | Path | bytes) -> tuple[str, dict]:
    """Return (text, metadata)."""
    try:
        document = docx.Document(io.BytesIO(source) if isinstance(source, bytes) else str(source))
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise CorruptedFileError("The DOCX file is damaged or is not a valid Word document.") from exc
    except Exception as exc:
        raise CorruptedFileError("The DOCX file could not be opened.") from exc

    lines: list[str] = _header_lines(document)
    for block in _iter_block_items(document):
        if isinstance(block, Paragraph):
            lines.append(_paragraph_text(block))
        else:
            lines.extend(_table_lines(block))
    lines.extend(_text_box_lines(document))

    text = "\n".join(lines).strip()
    if not text:
        raise EmptyDocumentError("The Word document is empty (no text found).")
    return text, {"pages": None, "ocr_used": False}
