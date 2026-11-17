"""
Builds the two TalentMatch AI documents:

    TalentMatch_AI_Project_Report.pdf   formal technical report for the interview panel
    TalentMatch_AI_Study_Guide.pdf      plain-language guide + interview preparation for the developer

Run from the repository root (uses the backend virtual environment, which has ReportLab):
    backend\\.venv\\Scripts\\python.exe docs\\build_docs.py

Set AUTHOR below (or the TM_AUTHOR environment variable) to print your name on the covers.
Screenshots in docs/images/ were taken from the running app with fictional demo data.
"""
import json
import os
from datetime import date
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer, Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

AUTHOR = os.getenv("TM_AUTHOR", "")  # e.g. "Your Name"; left blank -> a line to fill in by hand
DOCS = Path(__file__).resolve().parent
IMAGES = DOCS / "images"
TODAY = date.today().strftime("%B %Y")

# --- Fonts & colours ------------------------------------------------------------------------------------------
FONT_DIR = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
pdfmetrics.registerFont(TTFont("Body", str(FONT_DIR / "segoeui.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", str(FONT_DIR / "segoeuib.ttf")))
pdfmetrics.registerFont(TTFont("Body-Italic", str(FONT_DIR / "segoeuii.ttf")))
pdfmetrics.registerFont(TTFont("Body-Semi", str(FONT_DIR / "seguisb.ttf")))
pdfmetrics.registerFont(TTFont("Mono", str(FONT_DIR / "consola.ttf")))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-Bold")

NAVY = colors.HexColor("#0B1B3F")
NAVY_2 = colors.HexColor("#1D3A78")
BLUE = colors.HexColor("#2563EB")
SERIES = colors.HexColor("#2A78D6")
LIGHT_BLUE = colors.HexColor("#EFF6FF")
PURPLE = colors.HexColor("#7C3AED")
LIGHT_PURPLE = colors.HexColor("#F5F3FF")
GREEN = colors.HexColor("#047857")
LIGHT_GREEN = colors.HexColor("#ECFDF5")
AMBER_BG = colors.HexColor("#FFFBEB")
AMBER = colors.HexColor("#B45309")
INK = colors.HexColor("#1E293B")
MUTED = colors.HexColor("#64748B")
RULE = colors.HexColor("#E2E8F0")
ZEBRA = colors.HexColor("#F8FAFC")

PAGE_W, PAGE_H = A4
MARGIN = 2 * cm
CONTENT_W = PAGE_W - 2 * MARGIN

STYLES = {
    "body": ParagraphStyle("body", fontName="Body", fontSize=10, leading=15, textColor=INK, spaceAfter=6),
    "small": ParagraphStyle("small", fontName="Body", fontSize=8.5, leading=12, textColor=MUTED),
    "h1": ParagraphStyle("h1", fontName="Body-Bold", fontSize=18, leading=23, textColor=NAVY, spaceBefore=4, spaceAfter=10, keepWithNext=1),
    "h2": ParagraphStyle("h2", fontName="Body-Bold", fontSize=12.5, leading=17, textColor=NAVY_2, spaceBefore=10, spaceAfter=5, keepWithNext=1),
    "h3": ParagraphStyle("h3", fontName="Body-Semi", fontSize=10.5, leading=15, textColor=INK, spaceBefore=6, spaceAfter=3, keepWithNext=1),
    "bullet": ParagraphStyle("bullet", fontName="Body", fontSize=10, leading=14.5, textColor=INK, leftIndent=14, bulletIndent=3, spaceAfter=3),
    "cell": ParagraphStyle("cell", fontName="Body", fontSize=8.8, leading=12, textColor=INK),
    "cell_b": ParagraphStyle("cell_b", fontName="Body-Semi", fontSize=8.8, leading=12, textColor=INK),
    "head": ParagraphStyle("head", fontName="Body-Bold", fontSize=8.8, leading=12, textColor=colors.white),
    "caption": ParagraphStyle("caption", fontName="Body-Italic", fontSize=8.5, leading=12, textColor=MUTED, alignment=TA_CENTER, spaceBefore=3, spaceAfter=10),
    "formula": ParagraphStyle("formula", fontName="Mono", fontSize=9.5, leading=14, textColor=NAVY),
    "callout": ParagraphStyle("callout", fontName="Body", fontSize=9.5, leading=14, textColor=INK),
    "toc": ParagraphStyle("toc", fontName="Body", fontSize=10.5, leading=17, textColor=INK),
    "q": ParagraphStyle("q", fontName="Body-Bold", fontSize=10.5, leading=15, textColor=NAVY_2, spaceBefore=8, spaceAfter=2, keepWithNext=1),
}


# --- Document template with cover, running header/footer and a table of contents ---------------------------------
class Report(BaseDocTemplate):
    def __init__(self, filename, title, subtitle, kind, cover_facts, **kwargs):
        super().__init__(filename, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN + 6 * mm,
                         bottomMargin=MARGIN, title=f"TalentMatch AI - {title}", author=AUTHOR or "TalentMatch AI",
                         subject=subtitle, **kwargs)
        self.doc_title, self.subtitle, self.kind, self.cover_facts = title, subtitle, kind, cover_facts
        frame = Frame(MARGIN, MARGIN, CONTENT_W, PAGE_H - 2 * MARGIN - 6 * mm, id="body")
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[frame], onPage=self.draw_cover),
            PageTemplate(id="content", frames=[frame], onPage=self.draw_chrome),
        ])

    def afterFlowable(self, flowable):
        """Register H1/H2 headings for the table of contents and the PDF bookmarks."""
        if isinstance(flowable, Paragraph) and flowable.style.name in ("h1", "h2"):
            level = 0 if flowable.style.name == "h1" else 1
            text = flowable.getPlainText()
            key = f"h{self.seq.nextf('heading')}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
            if level == 0:
                self.notify("TOCEntry", (level, text, self.page, key))

    def draw_cover(self, canv, _doc):
        canv.saveState()
        canv.setFillColor(NAVY)
        canv.rect(0, PAGE_H * 0.42, PAGE_W, PAGE_H * 0.58, fill=1, stroke=0)
        canv.setFillColor(BLUE)
        canv.rect(0, PAGE_H * 0.42, PAGE_W, 5, fill=1, stroke=0)
        canv.setFillColor(PURPLE)
        canv.rect(0, PAGE_H * 0.42 + 5, PAGE_W * 0.35, 3, fill=1, stroke=0)
        x = MARGIN + 4 * mm
        # Logo mark
        canv.setFillColor(BLUE)
        canv.roundRect(x, PAGE_H - 5.2 * cm, 1.3 * cm, 1.3 * cm, 6, fill=1, stroke=0)
        canv.setFillColor(colors.white)
        canv.setFont("Body-Bold", 20)
        canv.drawCentredString(x + 0.65 * cm, PAGE_H - 4.8 * cm, "T")
        canv.setFont("Body-Semi", 12)
        canv.drawString(x + 1.7 * cm, PAGE_H - 4.65 * cm, "TalentMatch AI")
        canv.setFont("Body", 9)
        canv.setFillColor(colors.HexColor("#BFDBFE"))
        canv.drawString(x + 1.7 * cm, PAGE_H - 5.05 * cm, "Intelligent Resume Screening. Smarter Hiring Decisions.")
        # Title block
        canv.setFillColor(colors.HexColor("#93C5FD"))
        canv.setFont("Body-Semi", 10)
        canv.drawString(x, PAGE_H - 9.3 * cm, self.kind.upper())
        canv.setFillColor(colors.white)
        canv.setFont("Body-Bold", 30)
        y = PAGE_H - 10.7 * cm
        for line in self.doc_title.split("\n"):
            canv.drawString(x, y, line)
            y -= 1.25 * cm
        canv.setFont("Body", 12.5)
        canv.setFillColor(colors.HexColor("#DBEAFE"))
        for line in self.subtitle.split("\n"):
            canv.drawString(x, y - 0.1 * cm, line)
            y -= 0.62 * cm
        # Key facts row
        fy = PAGE_H * 0.42 - 2.6 * cm
        width = (CONTENT_W - 6 * mm) / len(self.cover_facts)
        for i, (value, label) in enumerate(self.cover_facts):
            fx = MARGIN + i * (width + 2 * mm)
            canv.setFillColor(LIGHT_BLUE)
            canv.roundRect(fx, fy, width, 1.9 * cm, 6, fill=1, stroke=0)
            canv.setFillColor(NAVY)
            canv.setFont("Body-Bold", 16)
            canv.drawString(fx + 4 * mm, fy + 1.05 * cm, value)
            canv.setFillColor(MUTED)
            canv.setFont("Body", 8.2)
            canv.drawString(fx + 4 * mm, fy + 0.45 * cm, label)
        # Meta
        canv.setFillColor(INK)
        canv.setFont("Body-Semi", 10.5)
        my = 5.2 * cm
        canv.drawString(MARGIN, my, "Prepared by")
        canv.setFont("Body", 10.5)
        if AUTHOR:
            canv.drawString(MARGIN + 3 * cm, my, AUTHOR)
        else:
            canv.setStrokeColor(MUTED)
            canv.line(MARGIN + 3 * cm, my - 1, MARGIN + 10 * cm, my - 1)
        canv.setFont("Body-Semi", 10.5)
        canv.drawString(MARGIN, my - 0.75 * cm, "Date")
        canv.setFont("Body", 10.5)
        canv.drawString(MARGIN + 3 * cm, my - 0.75 * cm, TODAY)
        canv.setFont("Body-Semi", 10.5)
        canv.drawString(MARGIN, my - 1.5 * cm, "Stack")
        canv.setFont("Body", 10.5)
        canv.drawString(MARGIN + 3 * cm, my - 1.5 * cm, "React · FastAPI · Sentence Transformers · spaCy · Supabase PostgreSQL")
        canv.setStrokeColor(RULE)
        canv.line(MARGIN, 2.2 * cm, PAGE_W - MARGIN, 2.2 * cm)
        canv.setFont("Body", 8)
        canv.setFillColor(MUTED)
        canv.drawString(MARGIN, 1.6 * cm, "All candidate data shown in this document is synthetic (fictional people and companies).")
        canv.restoreState()

    def draw_chrome(self, canv, doc):
        canv.saveState()
        canv.setStrokeColor(RULE)
        canv.setLineWidth(0.6)
        top = PAGE_H - MARGIN + 2 * mm
        canv.line(MARGIN, top, PAGE_W - MARGIN, top)
        canv.setFont("Body-Semi", 8)
        canv.setFillColor(NAVY)
        canv.drawString(MARGIN, top + 2.5 * mm, "TalentMatch AI")
        canv.setFont("Body", 8)
        canv.setFillColor(MUTED)
        canv.drawRightString(PAGE_W - MARGIN, top + 2.5 * mm, self.doc_title.replace("\n", " "))
        canv.line(MARGIN, MARGIN - 6 * mm, PAGE_W - MARGIN, MARGIN - 6 * mm)
        canv.drawString(MARGIN, MARGIN - 10 * mm, "Intelligent Resume Screening. Smarter Hiring Decisions.")
        canv.drawRightString(PAGE_W - MARGIN, MARGIN - 10 * mm, f"Page {doc.page}")
        canv.restoreState()


# --- Story helpers -------------------------------------------------------------------------------------------------
class Story(list):
    def h1(self, text):
        self.append(Paragraph(text, STYLES["h1"]))

    def h2(self, text):
        self.append(Paragraph(text, STYLES["h2"]))

    def h3(self, text):
        self.append(Paragraph(text, STYLES["h3"]))

    def p(self, text, style="body"):
        self.append(Paragraph(text, STYLES[style]))

    def bullets(self, items):
        for item in items:
            self.append(Paragraph(item, STYLES["bullet"], bulletText="•"))
        self.append(Spacer(1, 4))

    def numbered(self, items):
        for i, item in enumerate(items, 1):
            self.append(Paragraph(item, STYLES["bullet"], bulletText=f"{i}."))
        self.append(Spacer(1, 4))

    def table(self, rows, widths, header=True, first_col_bold=False, zebra=True, font_size=None):
        cell, bold = STYLES["cell"], STYLES["cell_b"]
        if font_size:
            cell = ParagraphStyle("c2", parent=cell, fontSize=font_size, leading=font_size * 1.38)
            bold = ParagraphStyle("c3", parent=bold, fontSize=font_size, leading=font_size * 1.38)
        data = []
        for r, row in enumerate(rows):
            styled = []
            for c, value in enumerate(row):
                style = STYLES["head"] if header and r == 0 else (bold if first_col_bold and c == 0 else cell)
                styled.append(value if not isinstance(value, str) else Paragraph(value, style))
            data.append(styled)
        widths = [w * CONTENT_W for w in widths]
        table = Table(data, colWidths=widths, repeatRows=1 if header else 0)
        commands = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
            ("BOX", (0, 0), (-1, -1), 0.6, RULE),
        ]
        if header:
            commands += [("BACKGROUND", (0, 0), (-1, 0), NAVY)]
        if zebra:
            for r in range(1 if header else 0, len(rows)):
                if (r % 2 == 0) == header:
                    commands.append(("BACKGROUND", (0, r), (-1, r), ZEBRA))
        table.setStyle(TableStyle(commands))
        self.append(table)
        self.append(Spacer(1, 10))

    def callout(self, title, text, tone="info"):
        bg, bar = {"info": (LIGHT_BLUE, BLUE), "good": (LIGHT_GREEN, GREEN), "note": (AMBER_BG, AMBER),
                   "idea": (LIGHT_PURPLE, PURPLE)}[tone]
        content = [Paragraph(f"<b>{title}</b>", STYLES["callout"])] if title else []
        content += [Paragraph(t, STYLES["callout"]) for t in ([text] if isinstance(text, str) else text)]
        box = Table([[content]], colWidths=[CONTENT_W])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg), ("LINEBEFORE", (0, 0), (0, -1), 3, bar),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        self.append(KeepTogether([box, Spacer(1, 10)]))

    def formula(self, lines):
        content = [Paragraph(line.replace(" ", "&nbsp;"), STYLES["formula"]) for line in lines]
        box = Table([[content]], colWidths=[CONTENT_W])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")), ("BOX", (0, 0), (-1, -1), 0.6, RULE),
            ("LEFTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        self.append(KeepTogether([box, Spacer(1, 10)]))

    def image(self, name, caption, width_ratio=1.0, max_height=None):
        path = IMAGES / name
        from PIL import Image as PILImage

        w, h = PILImage.open(path).size
        width = CONTENT_W * width_ratio
        height = width * h / w
        if max_height and height > max_height:
            height, width = max_height, max_height * w / h
        img = Image(str(path), width=width, height=height)
        frame = Table([[img]], colWidths=[width + 2])
        frame.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, RULE), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                   ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        self.append(KeepTogether([frame, Paragraph(caption, STYLES["caption"])]))

    def space(self, height=8):
        self.append(Spacer(1, height))

    def page(self):
        self.append(PageBreak())


def toc_page(story, intro):
    story.append(NextPageTemplate("content"))
    story.append(PageBreak())
    # Same look as a section heading, but a different style name so it doesn't list itself in the contents.
    story.append(Paragraph("Contents", ParagraphStyle("contents_title", parent=STYLES["h1"])))
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("toc0", parent=STYLES["toc"], leftIndent=0)]
    toc.dotsMinLevel = 0
    story.append(toc)
    story.space(10)
    story.callout(None, intro, "info")
    story.page()


# --- Diagrams --------------------------------------------------------------------------------------------------------
def box(d, x, y, w, h, title, lines=(), fill=LIGHT_BLUE, stroke=BLUE, title_color=NAVY):
    d.add(Rect(x, y, w, h, rx=6, ry=6, fillColor=fill, strokeColor=stroke, strokeWidth=1))
    d.add(String(x + w / 2, y + h - 15, title, fontName="Body-Bold", fontSize=9.5, fillColor=title_color, textAnchor="middle"))
    for i, line in enumerate(lines):
        d.add(String(x + w / 2, y + h - 30 - i * 11.5, line, fontName="Body", fontSize=7.6, fillColor=INK, textAnchor="middle"))


def arrow(d, x1, y1, x2, y2, label=None, color=NAVY_2, label_dy=4):
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1.2))
    import math

    angle = math.atan2(y2 - y1, x2 - x1)
    size = 5
    p1 = (x2 - size * math.cos(angle - 0.45), y2 - size * math.sin(angle - 0.45))
    p2 = (x2 - size * math.cos(angle + 0.45), y2 - size * math.sin(angle + 0.45))
    d.add(Polygon([x2, y2, *p1, *p2], fillColor=color, strokeColor=color))
    if label:
        d.add(String((x1 + x2) / 2, (y1 + y2) / 2 + label_dy, label, fontName="Body", fontSize=7, fillColor=MUTED, textAnchor="middle"))


def architecture_diagram():
    """Browser  <-HTTPS/JSON->  FastAPI backend  <-SQL->  Supabase;  backend -> local AI models."""
    w, h = CONTENT_W, 250
    side_w, gap = 104, 54  # outer boxes and the connector gaps (wide enough for arrows and labels)
    mid_x, mid_w = side_w + gap, w - 2 * (side_w + gap)
    right_x = w - side_w
    d = Drawing(w, h)
    box(d, 0, 140, side_w, 100, "Recruiter's browser", ["React 19 + Vite", "Tailwind · Recharts", "Axios + login token", "Hosted on Vercel"],
        fill=LIGHT_PURPLE, stroke=PURPLE)
    d.add(Rect(mid_x, 10, mid_w, 230, rx=8, ry=8, fillColor=colors.white, strokeColor=NAVY, strokeWidth=1.2))
    d.add(String(mid_x + mid_w / 2, 225, "FastAPI backend (Python)", fontName="Body-Bold", fontSize=9.5, fillColor=NAVY, textAnchor="middle"))
    d.add(String(mid_x + mid_w / 2, 213, "routes → services → modules · Render", fontName="Body", fontSize=7, fillColor=MUTED, textAnchor="middle"))
    modules = [
        ("auth", "login, tokens, owner checks"), ("parser", "PDF/DOCX → text → fields"), ("nlp", "skills, JD analysis, embeddings"),
        ("matching", "scoring, explanation, ranking"), ("services", "upload, analysis, dashboard, export"),
    ]
    for i, (name, desc) in enumerate(modules):
        y = 170 - i * 34
        d.add(Rect(mid_x + 10, y, mid_w - 20, 28, rx=4, ry=4, fillColor=LIGHT_BLUE, strokeColor=colors.HexColor("#BFDBFE"), strokeWidth=0.8))
        d.add(String(mid_x + 18, y + 16, name, fontName="Body-Bold", fontSize=8.2, fillColor=NAVY))
        d.add(String(mid_x + 18, y + 5.5, desc, fontName="Body", fontSize=7.2, fillColor=INK))
    box(d, right_x, 140, side_w, 100, "Supabase", ["PostgreSQL 17", "users · jobs", "candidates", "analysis_history", "match_results"],
        fill=LIGHT_GREEN, stroke=GREEN)
    box(d, right_x, 10, side_w, 100, "Local AI models", ["all-MiniLM-L6-v2", "Sentence Transformers", "spaCy en_core_web_sm", "loaded at startup"],
        fill=AMBER_BG, stroke=AMBER)
    arrow(d, side_w + 3, 202, mid_x - 3, 202, "HTTPS/JSON", label_dy=6)
    arrow(d, mid_x - 3, 180, side_w + 3, 180)
    arrow(d, mid_x + mid_w + 3, 202, right_x - 3, 202, "SQL", label_dy=6)
    arrow(d, right_x - 3, 180, mid_x + mid_w + 3, 180)
    arrow(d, mid_x + mid_w + 3, 60, right_x - 3, 60, "in-process", label_dy=6)
    return d


def pipeline_diagram(steps, colors_cycle=(LIGHT_BLUE,)):
    w, h = CONTENT_W, 64
    d = Drawing(w, h)
    gap = 9
    bw = (w - gap * (len(steps) - 1)) / len(steps)
    for i, (title, sub) in enumerate(steps):
        x = i * (bw + gap)
        d.add(Rect(x, 8, bw, 48, rx=5, ry=5, fillColor=colors_cycle[i % len(colors_cycle)], strokeColor=BLUE, strokeWidth=0.8))
        d.add(String(x + bw / 2, 37, title, fontName="Body-Bold", fontSize=7.8, fillColor=NAVY, textAnchor="middle"))
        d.add(String(x + bw / 2, 24, sub, fontName="Body", fontSize=6.6, fillColor=INK, textAnchor="middle"))
        if i < len(steps) - 1:
            arrow(d, x + bw + 1, 32, x + bw + gap - 1, 32)
    return d


def score_chart(results):
    """Horizontal bar chart of final scores (one hue, value labels, recessive grid)."""
    row_h, label_w, right_pad = 17, 110, 40
    w = CONTENT_W
    h = len(results) * row_h + 26
    d = Drawing(w, h)
    plot_w = w - label_w - right_pad
    for tick in (0, 25, 50, 75, 100):
        x = label_w + plot_w * tick / 100
        d.add(Line(x, 16, x, h, strokeColor=RULE, strokeWidth=0.5))
        d.add(String(x, 4, str(tick), fontName="Body", fontSize=7, fillColor=MUTED, textAnchor="middle"))
    for i, r in enumerate(results):
        y = h - (i + 1) * row_h
        d.add(String(label_w - 6, y + 4, f"{r['rank']}. {r['name']}", fontName="Body", fontSize=7.8, fillColor=INK, textAnchor="end"))
        bar = max(plot_w * r["final"] / 100, 1)
        d.add(Rect(label_w, y + 1, bar, row_h - 6, rx=2, ry=2, fillColor=SERIES, strokeColor=None))
        d.add(String(label_w + bar + 4, y + 4, f"{r['final']:.2f}", fontName="Body-Semi", fontSize=7.6, fillColor=INK))
    return d


def facts_grid(story, facts):
    """Row of KPI tiles."""
    cells = []
    for value, label in facts:
        cells.append([Paragraph(f"<font name='Body-Bold' size='15' color='#0B1B3F'>{value}</font>", STYLES["cell"]),
                      Paragraph(label, STYLES["small"])])
    table = Table([cells], colWidths=[CONTENT_W / len(facts)] * len(facts))
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE), ("BOX", (0, 0), (-1, -1), 0.6, colors.white),
        ("INNERGRID", (0, 0), (-1, -1), 3, colors.white), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(table)
    story.space(12)


RESULTS = json.loads((IMAGES / "python_results.json").read_text(encoding="utf-8"))


# =====================================================================================================================
# 1. PROJECT REPORT (for the interview panel)
# =====================================================================================================================
def build_report():
    s = Story()
    s.space(1)
    toc_page(s, "This report describes the design, implementation and validation of TalentMatch AI, a working "
                "full-stack application that ranks candidate resumes against a job description with an explainable, "
                "AI-assisted score. All candidates shown are synthetic; scores and timings are measured from the running system.")

    # 1 Executive summary ------------------------------------------------------------------------------------------
    s.h1("1. Executive Summary")
    s.p("Recruiters often receive dozens of resumes for one role and must shortlist quickly, consistently and fairly. "
        "<b>TalentMatch AI</b> is a full-stack web application that reads a batch of PDF/DOCX resumes, analyses a job "
        "description (JD), and ranks every candidate with a <b>0–100 match score</b> that is fully explained: which "
        "required skills were found or missing, how much <i>relevant</i> experience the candidate has, and how closely "
        "the resume's content matches the JD in meaning.")
    s.p("The score combines three independent signals: <b>semantic similarity</b> from a Sentence Transformers language "
        "model (40%), <b>weighted skill matching</b> against a curated skill dictionary (35%) and <b>relevant-experience "
        "matching</b> (25%). Results are stored in Supabase PostgreSQL, ranked in SQL, and presented in an HR-focused "
        "dashboard. Each recruiter has their own login and sees only their own data.")
    facts_grid(s, [("≈ 8 s", "to upload, parse and rank<br/>12 resumes end to end"), ("3-part", "explainable score:<br/>semantic · skills · experience"),
                   ("335", "automated tests<br/>(322 backend + 13 browser)"), ("0 paid APIs", "all AI runs locally<br/>on open-source models")])
    s.h2("Key outcomes")
    s.bullets([
        "Complete working system: React frontend, FastAPI backend, Supabase database, local NLP models.",
        "On the sample data the expected candidate ranks first for every job description tested "
        "(Python Developer, Java Developer, Data Scientist), with clear score gaps to unrelated profiles.",
        "Every score is calculated dynamically and is reproducible: the same inputs always produce the same output.",
        "Missing information (e.g. no experience dates) is flagged as <i>unknown</i>, never silently treated as zero.",
        "Responsible-AI safeguards: decision-support only, no sensitive attributes used, human review encouraged.",
    ])

    # 2 Problem & objectives -----------------------------------------------------------------------------------------
    s.h1("2. Problem Statement and Objectives")
    s.h2("Problem")
    s.p("Manual resume screening is slow and inconsistent. Simple keyword filters miss qualified candidates who describe "
        "their skills differently (\"RESTful services\" vs \"REST APIs\"), produce false matches (\"Java\" inside "
        "\"JavaScript\"), and give recruiters a number without a reason. Recruiters need a fast, consistent first pass "
        "that they can understand and override.")
    s.h2("Objectives")
    s.table([
        ["#", "Objective", "How it is met"],
        ["1", "Accept a JD by text or file and extract its requirements", "JD analyser with editable results (title, skills, experience, education, responsibilities)"],
        ["2", "Upload 10+ PDF/DOCX resumes in one batch", "Bulk upload with per-file validation and status; tested with 12 files"],
        ["3", "Extract candidate information automatically", "Name, email, phone, skills, education, certifications, projects, dated experience"],
        ["4", "Score each candidate 0–100", "Hybrid score: 40% semantic + 35% skills + 25% experience"],
        ["5", "Explain every score", "Matched/missing skills, experience comparison, points breakdown, plain-English explanation"],
        ["6", "Rank, search, filter and export", "SQL ranking with ties handled; filters; CSV export"],
        ["7", "Persist and retrieve past analyses", "Supabase PostgreSQL with full analysis history"],
        ["8", "Secure multi-user access", "HR accounts with admin management; each HR sees only their own data"],
    ], [0.05, 0.38, 0.57])

    # 3 Solution overview -----------------------------------------------------------------------------------------
    s.h1("3. Solution Overview")
    s.p("The recruiter works through a guided, three-step flow: <b>describe the job → upload resumes → review the "
        "ranking</b>. The table below summarises the main capabilities.")
    s.table([
        ["Area", "Capabilities"],
        ["Job descriptions", "Paste text or upload PDF/DOCX; automatic extraction of required vs preferred skills, minimum experience, "
                             "education and responsibilities; recruiter review and editing before saving; \"A or B\" skill alternatives."],
        ["Resume processing", "Batch upload (default limit 50, 5 MB each); content-based file validation; text extraction from PDF and "
                              "Word (including tables, headers and text boxes); scanned-PDF detection; duplicate detection."],
        ["Matching", "Semantic similarity, weighted skills, relevant experience with overlap merging; configurable weights; "
                     "transparent handling of missing data."],
        ["Ranking & results", "Rank with shared ranks for ties; Top 5/10; search; score-band and experience filters; sortable columns; CSV export."],
        ["Candidate view", "Score ring, points breakdown, skills checklist, experience comparison, explanation, "
                           "\"points to verify in interview\", print/PDF, data deletion on request."],
        ["Dashboard", "Totals, score distribution, latest shortlist, 30-day activity, recent analyses (per recruiter)."],
        ["Accounts", "Admin-created HR accounts, roles, disable/enable, password reset, own-data isolation."],
    ], [0.2, 0.8], first_col_bold=True)

    # 4 Architecture --------------------------------------------------------------------------------------------------
    s.h1("4. System Architecture")
    s.p("TalentMatch AI is a classic three-tier web application. The browser only talks to the FastAPI backend over "
        "HTTPS/JSON; database credentials and AI models live on the server.")
    s.append(architecture_diagram())
    s.p("Figure 1 - High-level architecture.", "caption")
    s.h2("Backend design")
    s.bullets([
        "<b>Layered:</b> thin <i>routes</i> (HTTP, validation, auth) call <i>services</i> (workflow, transactions), which use "
        "pure, testable modules for parsing, NLP and scoring.",
        "<b>Dependency injection:</b> FastAPI dependencies supply the database session and the logged-in user to every endpoint.",
        "<b>Models loaded once:</b> the Sentence Transformer and spaCy models are loaded at startup and reused by every request.",
        "<b>Consistent errors:</b> global exception handlers return <font name='Mono'>{\"detail\": \"…\"}</font> with the correct status code (400/401/403/404/409/422/503).",
    ])
    s.h2("Technology choices")
    s.table([
        ["Layer", "Technology", "Why it was chosen"],
        ["Frontend", "React 19, Vite 8, Tailwind CSS 4, React Router 7, Axios, Recharts, Lucide", "Component-based UI, fast builds, consistent design system, accessible charts"],
        ["Backend", "Python 3.14, FastAPI, Pydantic, Uvicorn", "Python is the natural home of NLP libraries; FastAPI gives validation and Swagger docs automatically"],
        ["Database", "Supabase PostgreSQL 17, SQLAlchemy 2, psycopg 3", "Relational data with joins, constraints, transactions, JSONB and window functions for ranking"],
        ["AI / NLP", "Sentence Transformers (all-MiniLM-L6-v2), spaCy, scikit-learn", "Free, local, fast on CPU (384-dimension embeddings); no paid API or data leaving the server"],
        ["Parsing", "PyMuPDF, python-docx", "Reliable text extraction with page and layout awareness"],
        ["Security", "scrypt (Python stdlib), PyJWT", "Memory-hard password hashing; signed, expiring session tokens"],
        ["Testing", "pytest, FastAPI TestClient, Playwright (Microsoft Edge)", "Unit, API and real-browser end-to-end tests"],
    ], [0.13, 0.37, 0.5], first_col_bold=True)

    # 5 Processing pipeline ----------------------------------------------------------------------------------------------
    s.h1("5. Data Processing Pipeline")
    s.h2("5.1 Resume parsing")
    s.append(pipeline_diagram([("Validate", "type · size · signature"), ("Extract", "PyMuPDF / python-docx"),
                               ("Clean", "bullets · dashes · Unicode"), ("Sections", "skills · experience …"),
                               ("Fields", "regex · dictionary · NER"), ("Store", "Supabase")]))
    s.p("Figure 2 - Resume processing pipeline.", "caption")
    s.bullets([
        "<b>Validation</b> checks the real file content (\"magic bytes\"), not just the extension, enforces size limits while "
        "reading, rejects zip bombs and strips folder paths from names. Files are never executed or stored permanently.",
        "<b>Extraction</b> reads PDFs page by page in reading order and Word files including page headers, tables and text boxes. "
        "Image-only PDFs are reported as scanned (OCR is an optional extension).",
        "<b>Cleaning</b> normalises bullets, dashes and invisible characters but deliberately keeps case and symbols, so "
        "<font name='Mono'>C++</font>, <font name='Mono'>C#</font>, <font name='Mono'>.NET</font> and <font name='Mono'>Node.js</font> survive.",
    ])
    s.table([
        ["Field", "Method"],
        ["Email / phone", "Regular expressions; phone numbers validated by digit count, excluding year ranges"],
        ["Name", "Layout heuristic (2–4 capitalised words near the top, no job-title or skill words), spaCy PERSON entity as fallback"],
        ["Skills", "Curated dictionary: 126 skills, 235 aliases, 12 categories; URLs and e-mails removed first"],
        ["Education / certifications / projects", "Section detection plus degree keywords; degree level (bachelor, master …) recorded"],
        ["Experience", "Date ranges inside Experience/Internship sections only; overlapping jobs merged; internships counted separately; "
                       "otherwise the stated \"N years of experience\"; otherwise <i>unknown</i>"],
    ], [0.27, 0.73], first_col_bold=True)
    s.callout("Never invent information", "Anything not found is stored as empty and shown as \"Not found\", with a warning. "
              "For example, a resume without dates is flagged \"experience unknown\" rather than scored as 0 years.", "note")
    s.h2("5.2 Skill extraction without false matches")
    s.p("Each alias is matched with custom word boundaries and overlapping matches are resolved longest-first:")
    s.table([
        ["Text", "Detected", "Not detected (correctly)"],
        ["Languages: C++ and C#", "C++, C#", "C"],
        ["Built UIs in JavaScript", "JavaScript", "Java"],
        ["Database: PostgreSQL", "PostgreSQL", "SQL"],
        ["Mobile apps in React Native", "React Native", "React"],
        ["Objective-C · John C. Smith · I react quickly", "-", "C, React"],
        ["ML, Postgres, RESTful API, K8s", "Machine Learning, PostgreSQL, REST APIs, Kubernetes", "-"],
    ], [0.42, 0.35, 0.23])
    s.h2("5.3 Job description analysis")
    s.bullets([
        "The JD is split into sections (Responsibilities, Requirements, Nice to have, About us …) and into sentences with spaCy.",
        "Each sentence is classified as <b>required</b>, <b>preferred</b> (\"nice to have\", \"is a plus\", \"preferred\") or "
        "<b>company context</b> (About us / Benefits - never requirements). A skill in both is kept only as required.",
        "\"FastAPI <b>or</b> Django\" becomes one requirement satisfied by either skill; \"HTML/CSS\" means both.",
        "Minimum experience understands \"3+ years\", \"at least 3\", \"four (4) years\", \"2-4 years\", \"6 months\"; the overall "
        "minimum is the largest required lower bound; no statement means <i>no requirement</i>.",
        "Responsibilities come from their section or from verb-first sentences (spaCy part-of-speech tags plus a verb list).",
        "The recruiter reviews and edits everything before saving; each skill keeps the sentence it came from as evidence.",
    ])

    # 6 Matching engine ----------------------------------------------------------------------------------------------------
    s.h1("6. AI Matching Engine")
    s.formula(["Final Score = 0.40 × Semantic + 0.35 × Skills + 0.25 × Experience",
               "each component 0-100 · weights configurable · rounded to 2 decimals"])
    s.h2("6.1 Semantic similarity (40%)")
    s.p("The JD and each resume are converted into <b>embeddings</b> - 384-number vectors that capture meaning - with "
        "the open-source model <b>all-MiniLM-L6-v2</b>. Texts about similar topics produce vectors pointing in similar "
        "directions, even with different wording. Similarity is the cosine of the angle between the vectors:")
    s.formula(["cos(A, B) = (A · B) / (||A|| × ||B||)            range -1 … 1",
               "Semantic score = clip((cos - 0.15) / (0.75 - 0.15) × 100, 0, 100)"])
    s.bullets([
        "<b>Calibration:</b> across 84 measured JD/resume pairs, unrelated pairs scored ≈ 0.18–0.30 and strong matches ≈ 0.60–0.71, "
        "so 0.15 maps to 0 and 0.75 to 100 (both configurable).",
        "<b>Long resumes:</b> the model reads ~256 word-pieces, so text is split into 150-word chunks (30-word overlap) and the "
        "chunk embeddings are averaged - the whole resume counts.",
        "<b>What is compared:</b> professional content only (summary, skills, experience, projects); never names or contact details.",
        "<b>Efficiency:</b> the model is loaded once; all resumes are encoded in one batch (12 resumes scored in ≈ 0.3 s on a laptop CPU).",
    ])
    s.h2("6.2 Skills matching (35%)")
    s.formula(["Skills score = Σ weights of matched JD skills / Σ weights of all JD skills × 100",
               "required skill = 2 · preferred skill = 1        (configurable)"])
    s.p("Example from the brief: JD requires Python, SQL, FastAPI, Docker, REST APIs; the resume has Python, SQL, REST APIs "
        "and Flask. Matched 3 × 2 = 6 of 5 × 2 = 10 → <b>60.00</b>; FastAPI and Docker are reported missing, Flask as additional. "
        "Only skills written in the resume earn credit - nothing is inferred.")
    s.h2("6.3 Experience matching (25%)")
    s.formula(["Experience score = min(relevant years / required years, 1) × 100",
               "required 3, relevant 4 → 100.00        required 3, relevant 2 → 66.67"])
    s.p("<b>Relevant</b> experience counts only past jobs related to the role: the job title shares a meaningful word with the "
        "JD title, or uses the JD's title skill (a Django job counts as Python work), or shares at least two required skills. "
        "Overlapping periods are merged so parallel jobs are not double counted; internships are listed separately.")
    s.table([
        ["Situation", "Experience score"],
        ["JD states no experience requirement", "100 for every candidate (\"not required\")"],
        ["Fresher, or no relevant jobs", "0 (when experience is required)"],
        ["Only a stated total (\"4 years of experience\")", "Stated value, if the resume shows JD skills"],
        ["Experience cannot be determined", "<b>Not available</b>: excluded and flagged - never assumed to be 0"],
    ], [0.5, 0.5])
    s.h2("6.4 Missing data and explanations")
    s.p("If a component cannot be calculated (unknown experience, JD without recognised skills, or the model unavailable), "
        "the remaining weights are rescaled to sum to 1 and the result is marked <b>incomplete</b>. Every result includes a "
        "plain-English explanation generated only from computed facts, so it can never claim something the resume does not support.")
    s.h2("6.5 Worked example (measured)")
    priya = next(r for r in RESULTS if r["name"] == "Priya Nair")
    s.table([
        ["Component", "Calculation", "Score", "Points"],
        ["Semantic", "cosine 0.6648 → (0.6648 - 0.15) / 0.60 × 100", f"{priya['semantic']:.2f}", "× 0.40 = 34.324"],
        ["Skills", "4 of 6 required skills matched (8 / 12 weight)", "66.67", "× 0.35 = 23.333"],
        ["Experience", "4.3 relevant years vs 3 required (capped at 1)", "100.00", "× 0.25 = 25.000"],
        ["<b>Final</b>", "<b>Sum of the unrounded points = 82.657 → rounded</b>", "", f"<b>{priya['final']:.2f}</b>"],
    ], [0.15, 0.5, 0.12, 0.23])

    # 7 Ranking & persistence ----------------------------------------------------------------------------------------------------
    s.h1("7. Ranking and Persistence")
    s.p("An analysis and all of its results are saved in <b>one database transaction</b>: either everything is stored or nothing is. "
        "Re-running a job creates a new analysis, so history is preserved. Ranking is performed by PostgreSQL, not the browser:")
    s.formula(["WITH ranked AS (",
               "  SELECT id, RANK() OVER (ORDER BY final_score DESC) AS rank",
               "  FROM match_results WHERE analysis_id = :analysis_id)",
               "SELECT …, ranked.rank, COUNT(*) OVER () AS filtered_count",
               "FROM match_results JOIN ranked … JOIN candidates …",
               "WHERE <search / score / experience / top-N> ORDER BY <sort>, <tie-breakers>"])
    s.bullets([
        "<b>Ties share a rank</b> (91.5, 84.2, 84.2 → 1, 2, 2) and are always listed in the same order "
        "(skills, experience, semantic score, then name).",
        "<b>Ranks are fixed per analysis:</b> computed before filters, so the #7 candidate stays #7 when searching.",
        "<b>Top N</b> means rank ≤ N, so a tie at the cut-off is included rather than cut arbitrarily.",
        "One round trip per page: the filtered count is returned with the rows; full resume text is not downloaded for lists.",
    ])

    # 8 Database --------------------------------------------------------------------------------------------------------------
    s.h1("8. Database Design")
    s.p("users 1─< jobs 1─< analysis_history 1─< match_results >─1 candidates >─1 users", "formula")
    s.space(4)
    s.table([
        ["Table", "Purpose", "Key columns"],
        ["users", "HR accounts", "id (UUID), full_name, email (unique), password_hash, role (admin/hr), is_active, token_version, last_login_at"],
        ["jobs", "Job descriptions", "id, owner_id → users, job_title, description, required_skills / preferred_skills (JSONB), minimum_experience, education_requirements"],
        ["candidates", "Parsed resumes", "id, owner_id → users, name, email, phone, education, total_experience, extracted_skills (JSONB), profile (JSONB), file_hash, resume_text"],
        ["analysis_history", "One run of a job", "id, job_id → jobs, total_resumes, average_score, created_at"],
        ["match_results", "One candidate's result", "id, analysis_id, job_id, candidate_id, semantic / skills / experience / final score, matched / missing / additional skills, explanation, details (JSONB)"],
    ], [0.17, 0.18, 0.65], first_col_bold=True)
    s.bullets([
        "UUID primary keys, foreign keys with ON DELETE CASCADE, indexes on foreign keys and on (analysis_id, final_score DESC).",
        "CHECK constraints reject scores outside 0–100 and negative experience at database level; "
        "UNIQUE(analysis_id, candidate_id) prevents duplicates within an analysis.",
        "NULL means <i>unknown</i>, never zero. Row Level Security is enabled so Supabase's public REST API cannot read the tables.",
    ])

    # 9 API -----------------------------------------------------------------------------------------------------------------------
    s.h1("9. API Design")
    s.p("28 REST operations on 23 routes, documented automatically with Swagger UI at <font name='Mono'>/docs</font>. "
        "All endpoints except health and login require a <font name='Mono'>Bearer</font> token.")
    s.table([
        ["Group", "Endpoints"],
        ["Authentication", "GET /api/auth/setup-status · POST /api/auth/setup · POST /api/auth/login · GET /api/auth/me · POST /api/auth/change-password"],
        ["Accounts (admin)", "GET/POST /api/users/ · PATCH /api/users/{id} · POST /api/users/{id}/reset-password"],
        ["Jobs", "POST /api/jobs/analyze · POST /api/jobs/analyze-file · GET/POST /api/jobs/ · GET/PUT/DELETE /api/jobs/{id}"],
        ["Resumes", "POST /api/resumes/upload (multipart, per-file results)"],
        ["Analysis", "POST /api/analyze/{job_id} · GET /api/results/{job_id} · GET /api/results/{job_id}/export · GET /api/analyses/"],
        ["Candidates", "GET /api/candidates/ · GET/DELETE /api/candidates/{id} · GET /api/candidates/{id}/analysis/{job_id}"],
        ["Dashboard & system", "GET /api/dashboard/stats · GET /api/settings/ · GET /api/health"],
    ], [0.2, 0.8], first_col_bold=True, font_size=8.3)

    # 10 UI -------------------------------------------------------------------------------------------------------------------------
    s.h1("10. User Interface")
    s.p("The interface is designed for recruiters rather than engineers: a guided wizard, plain-language help, score colours "
        "that always carry a text label (Strong / Good / Partial / Limited), and an explicit reminder that scores support human judgement.")
    s.image("dashboard.png", "Figure 3 - Dashboard: totals, latest shortlist (click a bar to open a candidate), score distribution and activity.", max_height=11 * cm)
    s.image("new_analysis.png", "Figure 4 - New Analysis wizard: extracted requirements are reviewed and edited before saving.", width_ratio=0.82, max_height=12.5 * cm)
    s.image("rankings.png", "Figure 5 - Candidate ranking: top-match card, filters, score bars, matched and missing skills, CSV export.", max_height=11 * cm)
    s.image("candidate.png", "Figure 6 - Candidate details: score ring, explanation, points breakdown and interview checklist.", width_ratio=0.86, max_height=13 * cm)
    s.image("team_accounts.png", "Figure 7 - Team accounts (admin only). Other real accounts are blurred for privacy.", width_ratio=0.9)

    # 11 Security -------------------------------------------------------------------------------------------------------------------
    s.h1("11. Security, Privacy and Responsible AI")
    s.table([
        ["Concern", "Measure"],
        ["Passwords", "Never stored; scrypt hash with a random per-user salt; constant-time comparison"],
        ["Login", "Same message and timing for unknown email and wrong password (no account discovery); 8-hour signed JWT"],
        ["Session revocation", "token_version: password change/reset or disabling an account invalidates all existing tokens immediately"],
        ["Data isolation", "Every query filtered by the logged-in HR; another HR's record returns 404 (existence not revealed)"],
        ["Uploads", "Content-based type check, size limit enforced while reading, zip-bomb check, sanitised file names, files not stored"],
        ["Injection", "SQL via SQLAlchemy parameters; LIKE wildcards escaped; CSV export neutralises spreadsheet formulas (=, +, -, @)"],
        ["Secrets & logs", "Credentials only in backend/.env; logs contain counts, never names or e-mails; RLS enabled on all tables"],
        ["Fairness", "Age, gender, religion, ethnicity and other sensitive attributes are never used; candidates are never auto-rejected"],
        ["Privacy rights", "A candidate's data can be permanently deleted on request; analysis totals are recalculated"],
    ], [0.22, 0.78], first_col_bold=True)

    # 12 Testing --------------------------------------------------------------------------------------------------------------------
    s.h1("12. Testing and Validation")
    s.table([
        ["Test suite", "Tests", "Covers"],
        ["Resume parsing & sample resumes", "76", "Contact details, names, sections, dates, overlaps, internships, education, 12 synthetic resumes end to end"],
        ["Documents & validation", "29", "PDF/DOCX extraction, empty/scanned/corrupted/password-protected files, upload validation, zip bombs"],
        ["Skills & JD analysis", "73", "False-match prevention, synonyms, alternatives, required vs preferred, experience phrases, sample JDs"],
        ["Matching engine", "52", "Embeddings, cosine formula, chunking, calibration, weights, missing data, determinism, sample rankings"],
        ["Database, jobs & ranking", "48", "Constraints, cascades, transactions, rollback on failure, SQL ranking, ties, filters, pagination"],
        ["API & authentication", "44", "All endpoints, error codes, CSV export, login, admin management, data isolation between HRs"],
        ["<b>Backend total (pytest)</b>", "<b>322</b>", "Run against the real Supabase database inside rolled-back transactions"],
        ["Browser end-to-end (Playwright)", "13", "Full recruiter workflow, login and accounts, error handling, phone-width layout"],
    ], [0.33, 0.09, 0.58])
    s.h2("Results on the synthetic dataset")
    s.p("Python Developer JD (requires Python, FastAPI, SQL, REST APIs, Machine Learning, Docker; 3+ years) against the 12 sample resumes:")
    s.append(score_chart(RESULTS))
    s.p("Figure 8 - Final scores for the Python Developer JD (measured).", "caption")
    s.bullets([
        "The two Python backend developers rank first and second; Java, front-end and embedded profiles rank last.",
        "For the Java Developer JD the Java developer ranks first by a margin of more than 30 points; for the Data Scientist JD the data scientist ranks first.",
        "The fresher (rank 5) has a very high semantic score (96) but an experience score of 0 - showing why semantic similarity alone is not enough.",
    ])
    s.h2("Defects found by the tests (and fixed)")
    s.bullets([
        "Relevant experience too lenient (one shared generic skill counted a Flask job as Java experience) and too strict (Django work not counted as Python).",
        "Pages wider than a phone screen, caused by a hidden screen-reader label escaping a table's scroll container.",
        "A disabled user was signed out but the explanation message was cleared; a race in session handling.",
        "React StrictMode would have uploaded every batch twice if the upload were started in an effect; moved to the click handler.",
    ])

    # 13 Performance -----------------------------------------------------------------------------------------------------------------
    s.h1("13. Performance")
    s.table([
        ["Operation", "Measured time", "Notes"],
        ["Model loading (startup)", "≈ 14 s", "Once per server start; first run also downloads ≈ 90 MB"],
        ["Upload + parse 12 resumes", "≈ 4.5 s", "Includes saving to Supabase"],
        ["Analyse 12 resumes", "≈ 3.4 s", "Embedding, scoring, explanation and transactional save"],
        ["Scoring computation only", "≈ 0.3 s", "Batched embeddings on a laptop CPU"],
        ["Database round trip", "≈ 0.4 s", "Development database hosted in Sydney; a nearer region would be faster"],
    ], [0.32, 0.2, 0.48])

    # 14 Limitations -----------------------------------------------------------------------------------------------------------------
    s.h1("14. Limitations and Future Work")
    s.h2("Current limitations")
    s.bullets([
        "Semantic similarity measures topical similarity, not competence; it is deliberately only 40% of the score.",
        "Skill detection depends on the curated dictionary (editable JSON); unknown skills are matched by exact text only.",
        "Multi-column PDFs can interleave lines; scanned PDFs need the optional OCR extension; English only.",
        "No login rate limiting or e-mail-based password reset yet (admins reset passwords).",
        "Cloud deployment is prepared (environment variables, model caching, CORS) but not yet performed.",
    ])
    s.h2("Future enhancements")
    s.table([
        ["Enhancement", "Benefit"],
        ["pgvector embeddings in PostgreSQL", "Semantic search across all candidates; no re-embedding on re-analysis"],
        ["OCR (Tesseract) for scanned resumes", "Handle image-only PDFs"],
        ["Login rate limiting, e-mail invites and resets", "Production-grade account security"],
        ["Bias and fairness audits on real (consented) data", "Measure and reduce disparate impact"],
        ["ATS integration and shared team pipelines", "Fit into existing recruiting workflows"],
        ["Domain fine-tuned embedding model", "Better semantic accuracy for technical roles"],
    ], [0.45, 0.55])

    # 15 Deployment ----------------------------------------------------------------------------------------------------------------------
    s.h1("15. Deployment and Running the Project")
    s.table([
        ["Component", "Platform", "Configuration"],
        ["Frontend", "Vercel", "Build: npm run build · env: VITE_API_BASE_URL · SPA rewrite to index.html"],
        ["Backend", "Render (Python web service)", "pip install -r requirements.txt · uvicorn app.main:app · env: DATABASE_URL, JWT_SECRET_KEY, CORS_ORIGINS · persistent model cache"],
        ["Database", "Supabase", "PostgreSQL via the Session pooler (IPv4); tables created automatically on startup"],
    ], [0.15, 0.25, 0.6], first_col_bold=True)
    s.h2("Local execution")
    s.formula(["# backend",
               "cd backend && .venv\\Scripts\\activate",
               "uvicorn app.main:app --reload --port 8000      # API + Swagger at /docs",
               "python -m pytest                                # 322 tests",
               "# frontend",
               "cd frontend && npm run dev                      # http://localhost:5173",
               "npm run test:e2e                                # 13 browser tests"])
    s.h2("Project structure")
    s.formula(["backend/app/   main, config, database, models, schemas, errors, manage",
               "  auth/        security (scrypt, JWT), dependencies",
               "  parser/      pdf, docx, sections, experience, resume_parser",
               "  nlp/         skill_extractor (+ skills.json), jd_analyzer,",
               "               semantic_matcher, education, spacy_model",
               "  matching/    scoring, explanation, ranking",
               "  services/    job, candidate, resume, analysis, dashboard,",
               "               export, user",
               "  routes/      auth, users, jobs, resumes, analysis, candidates,",
               "               dashboard, settings",
               "frontend/src/ pages, components, layouts, auth, hooks,",
               "               services/api.js, utils",
               "sample_resumes/ (12)   sample_jds/ (7)   docs/"])
    s.callout("Conclusion", "TalentMatch AI meets the assignment's objectives with a working, tested system whose every score can be "
              "explained. Its design favours transparency over black-box accuracy: recruiters see exactly why a candidate ranks "
              "where they do, what to verify in interview, and remain in control of every decision.", "good")

    doc = Report(str(DOCS / "TalentMatch_AI_Project_Report.pdf"), "Project Report",
                 "Intelligent Resume Matching and Candidate Ranking System\nTechnical design, implementation and validation",
                 "Technical project report", [("40 / 35 / 25", "semantic / skills / experience"), ("335", "automated tests"),
                                              ("126", "skills in the dictionary"), ("0", "paid APIs required")])
    doc.multiBuild(s)


# =====================================================================================================================
# 2. STUDY GUIDE (plain language, for the developer)
# =====================================================================================================================
QA = [
    ("Why did you choose React?",
     "React lets me build the screen from small reusable pieces (a score bar, a skill chip, a table) that update automatically "
     "when data changes. It is the most widely used UI library, works well with Vite for fast development, and has good "
     "charting (Recharts) and routing (React Router) libraries."),
    ("Why FastAPI?",
     "All the AI libraries I needed (Sentence Transformers, spaCy, scikit-learn) are Python, so a Python backend avoids a "
     "second language. FastAPI checks every request with Pydantic models, gives clear error messages, and creates the Swagger "
     "documentation at /docs automatically. It is also fast and simple to explain."),
    ("Why Supabase PostgreSQL instead of Firebase?",
     "My data is relational: a job has analyses, an analysis has results, each result links a job and a candidate. PostgreSQL "
     "handles that with foreign keys, joins, transactions and constraints (a score can never be above 100). I also rank "
     "candidates with an SQL window function (RANK() OVER). Firebase is a document store and would make these joins and "
     "rankings much harder. Supabase gives me managed PostgreSQL for free."),
    ("How do PDF and DOCX parsing work?",
     "For PDFs I use PyMuPDF, which reads the text layer page by page in reading order. For Word files I use python-docx and "
     "read paragraphs, tables, the page header and text boxes, because many resume templates hide content there. If a PDF has "
     "no text (a scanned image), I report it clearly instead of returning nothing. Before parsing, I check the file is really a "
     "PDF/DOCX by its content, not just its name."),
    ("How is candidate information extracted?",
     "Email and phone use regular expressions. Skills come from my skill dictionary (126 skills with synonyms). The name is "
     "usually one of the first lines with 2–4 capitalised words; if that fails, spaCy's named-entity recognition looks for a "
     "PERSON. Experience comes from date ranges like \"Jan 2020 – Present\" in the Experience section. If something is not "
     "found, I store it as empty and show \"Not found\" - I never guess."),
    ("How are job requirements extracted?",
     "I split the JD into sections and sentences. A sentence in \"Nice to have\" or containing \"is a plus\" or \"preferred\" "
     "makes its skills preferred; otherwise they are required. Skills in \"About us\" are ignored. Experience phrases like "
     "\"3+ years\" or \"at least 3 years\" give the minimum. The recruiter can then edit everything before saving."),
    ("What are Sentence Transformers?",
     "They are AI models that turn a whole sentence or paragraph into a list of numbers (a vector) that represents its "
     "meaning. Two texts that mean similar things get similar vectors, even if they use different words."),
    ("What does all-MiniLM-L6-v2 do?",
     "It is a small, free Sentence Transformer model (about 90 MB). It converts text into 384 numbers. It runs on a normal CPU, "
     "so I don't need a GPU or a paid API, and candidate data never leaves my server."),
    ("What are embeddings?",
     "An embedding is the list of numbers a model produces for a text - like GPS coordinates for meaning. Texts about similar "
     "things are close to each other in this \"meaning space\"."),
    ("What does cosine similarity mean?",
     "It measures the angle between two embedding vectors: cos = (A · B) / (|A| × |B|). If they point the same way the value "
     "is close to 1 (very similar); if they are unrelated it is near 0. I convert it to 0–100: 0.15 or less is 0, 0.75 or more "
     "is 100, straight line in between - I chose these limits by measuring 84 real JD/resume pairs."),
    ("How does skill matching work?",
     "Required skills are worth 2 points, preferred skills 1 point. Skills score = points the candidate has ÷ total points × 100. "
     "\"FastAPI or Django\" counts as one requirement that either skill satisfies. The candidate only gets credit for skills "
     "actually written in their resume."),
    ("How does experience matching work?",
     "Experience score = relevant years ÷ required years, capped at 100. Relevant means jobs related to this role (similar "
     "title, the main skill of the job, or at least two required skills). Overlapping jobs are counted once, and internships "
     "are shown separately. If experience cannot be found, I mark it unknown instead of using 0."),
    ("How is the final score calculated?",
     "Final = 40% semantic + 35% skills + 25% experience. Example: Priya scored semantic 85.81, skills 66.67, experience 100, so "
     "0.40 × 85.81 + 0.35 × 66.67 + 0.25 × 100 = 82.657, shown as 82.66. If one part is missing, the other weights are scaled "
     "up and the result is marked \"Verify\"."),
    ("How does candidate ranking work?",
     "PostgreSQL ranks with RANK() OVER (ORDER BY final_score DESC). Equal scores share a rank (1, 2, 2, 4) and are always "
     "listed in the same order using tie-breakers. Ranks are computed before filtering, so a candidate keeps their rank when "
     "you search. \"Top 5\" means rank ≤ 5, so ties at the cut-off are included."),
    ("How does FastAPI communicate with React?",
     "React calls the API over HTTP using Axios (all calls are in services/api.js). Data is sent and received as JSON. After "
     "login, every request carries the token in the header \"Authorization: Bearer …\". CORS settings allow only my frontend's "
     "address to call the API."),
    ("How does Supabase store analysis results?",
     "Each analysis creates one row in analysis_history and one row per candidate in match_results (all scores, matched and "
     "missing skills, explanation, and a JSON breakdown). Everything is saved in one transaction, so a failure never leaves a "
     "half-saved analysis. Old analyses are kept, so you can look at history."),
    ("What challenges did you face?",
     "(1) Windows Smart App Control blocked some new Python packages, so I found versions that load. (2) The AI model only "
     "reads ~180 words, so I split long resumes into chunks and averaged them. (3) Deciding which experience is \"relevant\" "
     "needed several iterations. (4) Avoiding false skill matches like Java inside JavaScript. (5) The database is far away "
     "(Sydney), so I reduced the number of queries. (6) Automated browser tests found a mobile layout bug and a login message bug."),
    ("What improvements can be made?",
     "Store embeddings in PostgreSQL with pgvector for semantic search, add OCR for scanned resumes, add login rate limiting and "
     "e-mail password reset, run fairness audits on real data, support more languages, and deploy to the cloud."),
]

EXTRA_QA = [
    ("Why not just use ChatGPT or another LLM?",
     "The brief asked for no paid APIs, and resumes contain personal data that should not be sent to third parties. My approach "
     "is also deterministic and explainable: the same resume always gets the same score, and I can show exactly why."),
    ("How do you stop \"C\" matching inside \"C++\", or \"Java\" inside \"JavaScript\"?",
     "Each skill is matched with custom word boundaries: it cannot be followed by + or # or a letter, and overlapping matches "
     "are resolved by keeping the longest one. Ambiguous words like \"React\" or \"REST\" must match exact capital letters."),
    ("Is the system biased?",
     "It never uses age, gender, religion or similar attributes, and only scores skills, relevant experience and content. But "
     "any scoring can reflect how people write resumes, so it is decision support only - candidates are never rejected "
     "automatically, and every screen reminds the recruiter to review."),
    ("How do HR logins and data isolation work?",
     "Passwords are stored only as scrypt hashes. After login the server gives a signed token (JWT) that expires in 8 hours. "
     "Each job and candidate has an owner_id, and every query filters by the logged-in HR, so one HR cannot see another's "
     "data - they get \"not found\". Disabling an account or changing a password cancels all old tokens immediately."),
    ("How do you know it works?",
     "335 automated tests: 322 backend tests (parsing, NLP, scoring, database, API, security) run against the real database "
     "inside transactions that are rolled back, and 13 browser tests that click through the real app in Microsoft Edge."),
]


def build_guide():
    s = Story()
    s.space(1)
    toc_page(s, "This guide explains TalentMatch AI in simple words, so you can understand every part and talk about it "
                "confidently. Read Part 1 first, practise the demo in Part 6, and revise the questions in Part 5 before the interview.")

    s.h1("Part 1 - The Project in One Minute")
    s.callout("Your elevator pitch (say this first)", [
        "\"TalentMatch AI helps recruiters shortlist candidates faster and more fairly. A recruiter pastes a job description "
        "and uploads a batch of resumes. The system reads each resume, finds the candidate's skills and experience, and gives "
        "every candidate a score from 0 to 100.",
        "The score has three parts: how close the resume's meaning is to the job, measured with an AI language model; which "
        "required skills the candidate has; and how much relevant experience they have. Candidates are ranked, and for each one "
        "the recruiter sees exactly why they got their score and what to check in the interview.",
        "It's built with React, FastAPI and Supabase PostgreSQL, uses free open-source AI models that run locally, supports "
        "separate logins for each HR, and has over 300 automated tests.\""], "idea")
    s.h2("The three parts of the system")
    s.table([
        ["Part", "What it is", "Simple analogy"],
        ["Frontend", "The website the recruiter uses (React)", "The shop counter where customers are served"],
        ["Backend", "The Python program that does the work (FastAPI + AI)", "The kitchen where food is prepared"],
        ["Database", "Where everything is saved (Supabase PostgreSQL)", "The store room with labelled shelves"],
    ], [0.15, 0.45, 0.4], first_col_bold=True)

    s.h1("Part 2 - The Journey of One Resume")
    s.p("Follow one resume - Priya's - from upload to ranking. Each step is a file in the project.")
    s.numbered([
        "<b>Upload.</b> The recruiter drops Priya's PDF on the page. The browser sends it to the backend "
        "(<font name='Mono'>resumes/upload</font>).",
        "<b>Safety check.</b> The backend checks it is really a PDF (by its first bytes), not too big, and not a disguised file "
        "(<font name='Mono'>utils/file_validator.py</font>).",
        "<b>Read the text.</b> PyMuPDF pulls the words out of the PDF (<font name='Mono'>parser/pdf_parser.py</font>).",
        "<b>Tidy up.</b> Bullets and strange characters are cleaned, but \"C++\" and \"Node.js\" are kept exactly "
        "(<font name='Mono'>utils/text_cleaner.py</font>).",
        "<b>Find the sections.</b> Headings like \"Skills\" and \"Work Experience\" split the text (<font name='Mono'>parser/sections.py</font>).",
        "<b>Pick out the details.</b> Email, phone, name, skills, education and job dates are extracted. Two jobs that overlap are "
        "counted once (<font name='Mono'>parser/resume_parser.py</font>, <font name='Mono'>experience.py</font>).",
        "<b>Save.</b> Priya becomes a row in the <font name='Mono'>candidates</font> table, owned by the HR who uploaded her.",
        "<b>Score.</b> When the recruiter clicks Analyse, Priya's resume is compared with the job: meaning, skills, experience "
        "(<font name='Mono'>matching/scoring.py</font>).",
        "<b>Explain.</b> A sentence-by-sentence explanation is written from the numbers (<font name='Mono'>matching/explanation.py</font>).",
        "<b>Rank and show.</b> PostgreSQL ranks everyone; the website shows Priya at #1 with 82.66 and why.",
    ])

    s.h1("Part 3 - Each Building Block in Simple Words")
    s.h2("3.1 The skill dictionary")
    s.p("A JSON file listing 126 technical skills and their other spellings (235 aliases). \"ML\" means Machine Learning, "
        "\"Postgres\" means PostgreSQL. Matching is careful: \"Java\" inside \"JavaScript\" does not count, \"C\" inside \"C++\" does "
        "not count. If two skills overlap (\"React Native\" contains \"React\"), the longer one wins. Anyone can add a skill by "
        "editing the file - no code change needed.")
    s.h2("3.2 Understanding the job description")
    s.p("The JD is read sentence by sentence. Words like \"nice to have\" or \"is a plus\" mark a skill as <i>preferred</i>; "
        "everything else is <i>required</i>. \"3+ years\" or \"at least 3 years\" gives the minimum experience. The recruiter always "
        "checks and edits the result - the computer suggests, the human decides.")
    s.h2("3.3 Embeddings and cosine similarity (the \"AI\" part)")
    s.callout("Analogy: arrows pointing at meanings", [
        "Imagine every piece of text as an arrow in a huge space. The AI model (all-MiniLM-L6-v2) decides where the arrow points, "
        "based on meaning. \"Built REST services in Flask\" and \"backend API development in Python\" point in almost the same "
        "direction, even though the words are different. A pastry chef's resume points somewhere else entirely.",
        "Cosine similarity measures the angle between two arrows: same direction ≈ 1, unrelated ≈ 0. I turn that into 0–100."], "info")
    s.p("The model can only read about 180 words at once, so long resumes are cut into overlapping pieces and the arrows are "
        "averaged. The model is loaded once when the server starts, which takes about 14 seconds, then scores 12 resumes in a fraction of a second.")
    s.h2("3.4 The three scores and the final score")
    s.table([
        ["Score", "Question it answers", "How"],
        ["Semantic (40%)", "Is this resume about the same kind of work?", "Cosine similarity of AI embeddings, scaled to 0–100"],
        ["Skills (35%)", "Does the candidate have the skills asked for?", "Required skill = 2 points, preferred = 1; points found ÷ total"],
        ["Experience (25%)", "Enough experience in this kind of role?", "Relevant years ÷ required years (max 100)"],
    ], [0.18, 0.4, 0.42], first_col_bold=True)
    s.formula(["Priya:  0.40 × 85.81  +  0.35 × 66.67  +  0.25 × 100",
               "      =   34.324     +    23.333      +    25.000     =  82.657  →  82.66"])
    s.p("Tip: the computer adds the exact values and rounds only at the end. If you add the rounded points shown on screen "
        "(34.32 + 23.33 + 25.00) you get 82.65 - the 0.01 difference is just rounding.", "small")
    s.p("Why three parts? The AI alone can be fooled by matching words: Rohan, a fresher, gets 96 for meaning but 0 for experience, "
        "so he ranks 5th, not 1st. Combining all three gives a fair, explainable result.")
    s.h2("3.5 Missing information")
    s.p("If a resume has no dates, the system says \"experience unknown\" and leaves that part out (the other two parts share its "
        "weight) and shows a \"Verify\" badge. It never pretends the candidate has 0 years.")
    s.h2("3.6 Ranking")
    s.p("The database sorts by score. Equal scores get the same rank (1, 2, 2, 4) and are always listed in the same order. Ranks are "
        "fixed, so searching for someone doesn't change their number.")
    s.h2("3.7 The database tables")
    s.table([
        ["Table", "Holds", "Example"],
        ["users", "HR accounts (password stored only as a hash)", "Admin, two recruiters"],
        ["jobs", "Job descriptions and requirements", "\"Python Developer, 3+ years\""],
        ["candidates", "What was read from each resume", "Priya Nair, skills, 4.3 years"],
        ["analysis_history", "Each time you click Analyse", "12 resumes, average 48.49"],
        ["match_results", "Each candidate's score in one analysis", "Priya: 82.66, missing Docker"],
    ], [0.2, 0.45, 0.35], first_col_bold=True)
    s.h2("3.8 Login and keeping data separate")
    s.bullets([
        "The first person to open the app creates the <b>admin</b> account; the admin adds the other HRs (no public sign-up).",
        "Passwords are turned into a scrambled code (a <b>hash</b>) with scrypt; the real password is never saved anywhere.",
        "After login, the browser gets a signed <b>token</b> (like a wristband at an event) valid for 8 hours.",
        "Every job and candidate has an owner, so each HR only sees their own. If someone tries another HR's record, they get \"not found\".",
        "Disabling an HR or changing a password makes old tokens stop working immediately.",
    ])
    s.h2("3.9 Testing")
    s.p("335 automatic tests check the project: 322 test the backend (reading resumes, skills, scoring, database, API, login) on the "
        "real database but undo every change afterwards; 13 open Microsoft Edge and click through the app like a recruiter. They "
        "found real bugs: a page too wide for phones and a login message that disappeared.")

    s.h1("Part 4 - Glossary")
    s.table([
        ["Term", "Meaning in simple words"],
        ["API", "The list of \"doors\" the frontend can knock on to ask the backend for something (e.g. POST /api/analyze)"],
        ["Endpoint", "One of those doors: an address plus an action (GET = read, POST = create, PUT = edit, DELETE = remove)"],
        ["JSON", "The text format used to send data, e.g. {\"name\": \"Priya\", \"score\": 82.66}"],
        ["NLP", "Natural Language Processing - teaching computers to work with human language"],
        ["spaCy", "An NLP library; here it splits sentences, tags verbs and finds person names"],
        ["Embedding", "A list of numbers representing the meaning of a text (384 numbers here)"],
        ["Cosine similarity", "How closely two embeddings point in the same direction (1 = same, 0 = unrelated)"],
        ["Regex", "A pattern for finding text, e.g. an email address"],
        ["JSONB", "A PostgreSQL column that stores lists or objects, e.g. a list of skills"],
        ["Transaction", "A group of database changes saved all together or not at all"],
        ["Foreign key", "A link from one table to another (a result points to its job and candidate)"],
        ["JWT", "JSON Web Token - the signed login wristband sent with every request"],
        ["Hash", "A one-way scramble of a password; you can check a password against it but never reverse it"],
        ["CORS", "A browser rule that decides which websites may call the API"],
        ["Swagger", "The automatic, clickable API documentation at /docs"],
        ["Deterministic", "Same input → same output, every time (no randomness)"],
    ], [0.22, 0.78], first_col_bold=True)

    s.h1("Part 5 - Interview Questions and Answers")
    s.p("Answers are written the way you could say them. Each one is true for the code you built.")
    s.h2("The 18 questions from the brief")
    for i, (q, a) in enumerate(QA, 1):
        s.append(KeepTogether([Paragraph(f"{i}. {q}", STYLES["q"]), Paragraph(a, STYLES["body"])]))
    s.h2("Likely follow-up questions")
    for q, a in EXTRA_QA:
        s.append(KeepTogether([Paragraph(q, STYLES["q"]), Paragraph(a, STYLES["body"])]))

    s.h1("Part 6 - Five-Minute Demo Script")
    s.table([
        ["Time", "Do this", "Say this"],
        ["0:00", "Show the login page; sign in as admin", "\"Each recruiter has their own account and sees only their own data.\""],
        ["0:30", "New Analysis → paste sample_jds/02_senior_backend_engineer.txt → Extract requirements",
         "\"The JD is analysed: required vs preferred skills, 5 years minimum. I can correct anything before saving.\""],
        ["1:15", "Save → drop all 12 files from sample_resumes/ → Analyse",
         "\"Each file is checked and read; the AI compares every resume with the job.\""],
        ["2:00", "View candidate ranking", "\"Ranked by score. Green bars are strong matches; I can filter Top 5 or search.\""],
        ["2:45", "Open the top candidate", "\"Here's why: points from each part, skills found and missing, experience, and what to ask in interview.\""],
        ["3:45", "Back → Export CSV; open Dashboard", "\"Results can be exported, and the dashboard summarises my activity.\""],
        ["4:15", "Settings → Team accounts", "\"The admin adds HRs, can disable accounts and reset passwords; passwords are stored only as hashes.\""],
        ["4:45", "Close", "\"It's decision support: the recruiter always makes the final decision.\""],
    ], [0.09, 0.42, 0.49])
    s.callout("Before the demo", ["Start the backend about a minute early (the AI model takes ~14 s to load). Use the sample files "
              "(they are fictional). Have Swagger (/docs) open in a second tab in case the panel asks about the API.",
              "<b>Demo account</b> (shown on the login page; \"Use demo account\" fills it in): demo@gmail.com / Demo@1234. "
              "It is a regular HR recruiter, so panel members who try it see only its own data. Use your admin account for "
              "the Team accounts step."], "note")

    s.h1("Part 7 - Challenges and How They Were Solved")
    s.table([
        ["Challenge", "What was done"],
        ["Windows Smart App Control blocked some new Python packages", "Tested versions until finding ones that load; pinned them in requirements.txt; ran tools via python -m"],
        ["The AI model reads only ~180 words", "Split long resumes into overlapping 150-word chunks and averaged their embeddings"],
        ["Raw cosine scores were bunched together", "Measured 84 pairs and stretched 0.15–0.75 to 0–100"],
        ["False skill matches (Java in JavaScript)", "Custom word boundaries, longest-match-first, case-sensitive short words"],
        ["Deciding which experience is \"relevant\"", "Title words, the job's main skill (incl. frameworks) or two shared required skills"],
        ["Remote database (Sydney) is slow", "Fewer round trips: batched saves, one-query rankings, not downloading resume text for lists"],
        ["Bugs only visible in a real browser", "Playwright tests found a phone-width overflow and a disappearing login message"],
    ], [0.4, 0.6])

    s.h1("Part 8 - Honest Limitations")
    s.bullets([
        "The AI measures topic similarity, not skill level - that's why it's only 40% of the score.",
        "Skills must be in the dictionary (or typed exactly by the recruiter) to be recognised.",
        "Two-column PDFs can mix lines; scanned PDFs need OCR (not installed by default); English only.",
        "No limit on wrong-password attempts yet, and no \"forgot password\" e-mail (the admin resets passwords).",
        "Not yet deployed to the cloud - it runs locally; deployment settings are prepared.",
    ])
    s.callout("If asked \"what would you do next?\"", "Deploy it, add pgvector for semantic search across all candidates, add OCR, "
              "add login rate limiting, and test fairness on real, consented data.", "idea")

    s.h1("Part 9 - Numbers to Remember")
    s.table([
        ["Fact", "Value"],
        ["Score weights", "40% semantic · 35% skills · 25% experience"],
        ["Skill weights", "required 2 · preferred 1"],
        ["Semantic calibration", "cosine 0.15 → 0, 0.75 → 100"],
        ["Embedding size / model", "384 numbers · all-MiniLM-L6-v2 (~90 MB)"],
        ["Skill dictionary", "126 skills · 235 aliases · 12 categories"],
        ["Sample data", "12 resumes (6 PDF, 6 DOCX) · 7 job descriptions"],
        ["Tests", "322 backend + 13 browser = 335"],
        ["Speed", "12 resumes: ≈ 4.5 s upload + parse, ≈ 3.4 s analysis"],
        ["Login", "scrypt hash · JWT valid 8 hours · admin creates accounts"],
        ["Example", "Priya: 85.81 / 66.67 / 100 → 82.66 (rank 1)"],
    ], [0.35, 0.65], first_col_bold=True)

    s.h1("Part 10 - Command Cheat Sheet")
    s.formula(["# Start the backend (from the backend folder)",
               "cd /d C:\\Users\\chand\\TalentMatch-AI\\backend",
               ".venv\\Scripts\\activate",
               "uvicorn app.main:app --reload --port 8000",
               "",
               "# Start the frontend (second terminal)",
               "cd /d C:\\Users\\chand\\TalentMatch-AI\\frontend",
               "npm run dev                         # open http://localhost:5173",
               "",
               "# Tests",
               "python -m pytest -q                 # backend (322)",
               "npm run test:e2e                    # browser (13)",
               "",
               "# Accounts (from the backend folder)",
               "python -m app.manage list-users",
               "python -m app.manage reset-password --email you@company.com --password NewPass123"])

    doc = Report(str(DOCS / "TalentMatch_AI_Study_Guide.pdf"), "Study Guide",
                 "The project explained in simple words\nplus interview questions, demo script and cheat sheet",
                 "Personal study guide", [("1 min", "elevator pitch"), ("23", "interview Q&As"),
                                          ("5 min", "demo script"), ("10", "parts")])
    doc.multiBuild(s)


if __name__ == "__main__":
    build_report()
    build_guide()
    print("Built:", DOCS / "TalentMatch_AI_Project_Report.pdf")
    print("Built:", DOCS / "TalentMatch_AI_Study_Guide.pdf")
