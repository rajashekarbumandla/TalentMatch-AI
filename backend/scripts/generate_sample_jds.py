"""
Create PDF and DOCX copies of two sample JDs so JD *file upload* can be tested.

    cd backend
    python scripts/generate_sample_jds.py

Reads <repo>/sample_jds/*.txt (hand-written, fictional companies) and writes:
    06_java_developer.docx          (headings as bold paragraphs, bullets as a Word list)
    07_ml_engineer_fresher.pdf
"""
import sys
from pathlib import Path

import docx
import pymupdf

JD_DIR = Path(__file__).resolve().parents[2] / "sample_jds"


def txt_to_docx(source: Path, target: Path) -> None:
    document = docx.Document()
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        if line.startswith("- "):
            document.add_paragraph(line[2:], style="List Bullet")
        elif len(line.split()) <= 4:
            document.add_paragraph().add_run(line).bold = True
        else:
            document.add_paragraph(line)
    document.save(target)


def txt_to_pdf(source: Path, target: Path) -> None:
    html = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        escaped = line.replace("&", "&amp;").replace("<", "&lt;")
        if line.startswith("- "):
            html.append(f"<li>{escaped[2:]}</li>")
        elif len(line.split()) <= 4:
            html.append(f"<h3>{escaped}</h3>")
        else:
            html.append(f"<p>{escaped}</p>")
    story = pymupdf.Story(html="".join(html), user_css="* {font-family: sans-serif; font-size: 11px;} h3 {font-size: 13px;}")
    writer = pymupdf.DocumentWriter(str(target))
    mediabox = pymupdf.paper_rect("a4")
    more = True
    while more:
        device = writer.begin_page(mediabox)
        more, _ = story.place(mediabox + (50, 50, -50, -50))
        story.draw(device)
        writer.end_page()
    writer.close()


def main() -> int:
    txt_to_docx(JD_DIR / "06_java_developer.txt", JD_DIR / "06_java_developer.docx")
    txt_to_pdf(JD_DIR / "07_ml_engineer_fresher.txt", JD_DIR / "07_ml_engineer_fresher.pdf")
    print("wrote sample_jds/06_java_developer.docx and sample_jds/07_ml_engineer_fresher.pdf")
    return 0


if __name__ == "__main__":
    sys.exit(main())
