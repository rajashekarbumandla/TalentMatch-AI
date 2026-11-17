"""
Resume parser: file bytes -> structured candidate information.

Pipeline
    1. extract_text()          PDF (PyMuPDF) or DOCX (python-docx) -> raw text
    2. clean_text()            normalise bullets, dashes, spacing (technical terms preserved)
    3. split_sections()        summary / skills / experience / education / projects / ...
    4. field extractors        name, email, phone, links, skills, education,
                               certifications, projects, work experience

Rule: never invent information. Anything not found is returned as None (or an
empty list) and listed in `warnings`, so the UI can show "Not found".
"""
import re
from dataclasses import asdict, dataclass, field
from datetime import date

from app.nlp.education import detect_degree_levels, has_degree
from app.nlp.skill_extractor import extract_skills, group_skills_by_category
from app.nlp.spacy_model import get_spacy_model
from app.parser import extract_text
from app.parser.experience import summarize_experience
from app.parser.sections import SECTION_HEADINGS, split_sections
from app.utils.text_cleaner import clean_text

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# A run of digits with common phone separators; validated afterwards by digit count.
PHONE_RE = re.compile(r"(?<![\w/])\(?\+?\(?\d[\d\s().-]{7,20}\d(?![\w/])")
LINK_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin\.com/in/|github\.com/)[\w\-./]+", re.I)
# Case-sensitive on purpose: real domains are lowercase, so "ASP.NET/C#" is not mistaken for a URL.
URL_OR_EMAIL_RE = re.compile(
    r"(?:https?://|www\.)\S+|\b[a-z0-9.-]+\.(?:com|in|io|org|net|dev|ai)/\S*|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)

_CERTIFICATION_HINT = re.compile(r"\bcertifi(?:ed|cation|cate)\b", re.I)
# Title and description separated by ":" (not "://" of a URL) or " - ".
_PROJECT_TITLE_SPLIT = re.compile(r"^(.{2,120}?)(?::(?!//)|\s-\s)\s*(.*)$")

# Words that mean a top line is NOT a person's name.
_NOT_NAME_WORDS = {
    "resume", "curriculum", "vitae", "cv", "profile", "contact", "email", "phone", "mobile", "address",
    "linkedin", "github", "portfolio", "objective", "summary", "developer", "engineer", "analyst",
    "scientist", "manager", "intern", "designer", "consultant", "architect", "student", "fresher",
    "software", "data", "senior", "junior", "lead", "full", "stack", "backend", "frontend", "machine",
    "learning", "python", "java", "india", "street", "road", "nagar",
}
_NAME_TOKEN = re.compile(r"^[A-Z][A-Za-z'\-]*\.?$|^[A-Z]\.$")
_ALL_HEADINGS = {h for headings in SECTION_HEADINGS.values() for h in headings}


@dataclass
class ParsedResume:
    name: str | None
    email: str | None
    phone: str | None
    links: list[str]
    summary: str | None
    skills: list[str]
    skills_by_category: dict[str, list[str]]
    education: list[str]
    degree_levels: list[str]
    certifications: list[str]
    projects: list[dict]
    experience: list[dict]
    total_experience_years: float | None  # None = unknown
    internship_experience_years: float | None
    stated_experience_years: float | None
    experience_method: str
    is_fresher: bool
    sections_found: list[str]
    warnings: list[str] = field(default_factory=list)
    text: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def education_text(self) -> str | None:
        return "\n".join(self.education) if self.education else None

    def to_dict(self) -> dict:
        return asdict(self)


# --- Contact details -----------------------------------------------------------------------
def extract_email(text: str) -> str | None:
    match = EMAIL_RE.search(text)
    return match.group(0).lower().rstrip(".") if match else None


def extract_phone(text: str) -> str | None:
    """First number with 10-15 digits that does not look like a date range."""
    for match in PHONE_RE.finditer(text):
        candidate = match.group(0).strip()
        digits = re.sub(r"\D", "", candidate)
        if not 10 <= len(digits) <= 15:
            continue
        if re.search(r"(?:19|20)\d{2}\s*[-/]\s*(?:19|20)\d{2}", candidate):  # "2019 - 2021 ..."
            continue
        return re.sub(r"\s+", " ", candidate)
    return None


def extract_links(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(0).rstrip(".,") for m in LINK_RE.finditer(text)))


# --- Name ------------------------------------------------------------------------------------
def _looks_like_name(candidate: str) -> bool:
    tokens = candidate.split()
    if not 2 <= len(tokens) <= 4:
        return False
    if any(token.lower().strip(".") in _NOT_NAME_WORDS for token in tokens):
        return False
    if candidate.lower() in _ALL_HEADINGS or extract_skills(candidate):
        return False
    return all(_NAME_TOKEN.match(token) for token in tokens)


def _tidy_name(candidate: str) -> str:
    candidate = re.sub(r"\s+", " ", candidate).strip()
    return candidate.title() if candidate.isupper() else candidate


def extract_name(text: str, header_text: str) -> tuple[str | None, str]:
    """
    Returns (name, method). Heuristic first: the name is usually one of the first
    lines, 2-4 capitalised words, with no digits, email or job-title words.
    Fallback: spaCy PERSON entity in the top of the resume.
    """
    top_lines = [line for line in (header_text or text).split("\n") if line.strip()][:8]
    for line in top_lines:
        if EMAIL_RE.search(line) or re.search(r"\d{3}", line) or "http" in line.lower():
            continue
        first_part = re.split(r"\s*[|,]\s*|\s+-\s+", line.strip("- "))[0].strip()
        candidate = _tidy_name(first_part)
        if _looks_like_name(candidate):
            return candidate, "layout_heuristic"

    nlp = get_spacy_model()
    if nlp is not None:
        top_text = "\n".join(text.split("\n")[:12])
        for entity in nlp(top_text).ents:
            candidate = _tidy_name(entity.text.strip())
            if entity.label_ == "PERSON" and "\n" not in entity.text and _looks_like_name(candidate):
                return candidate, "spacy_ner"
    return None, "not_found"


# --- Education, certifications, projects -----------------------------------------------------
def extract_education(education_section: str, full_text: str) -> list[str]:
    """
    Group education lines into entries. A line that names a degree starts a new
    entry; following lines (institution, year, grade) are appended to it.
    """
    lines = [line.strip("- ").strip() for line in education_section.split("\n") if line.strip("- ").strip()]
    if not lines:  # no Education heading: fall back to any line that names a degree
        return list(dict.fromkeys(line.strip("- ").strip() for line in full_text.split("\n") if has_degree(line)))[:6]
    entries: list[str] = []
    for line in lines:
        if has_degree(line) or not entries:
            entries.append(line)
        elif line[0].isdigit() or line[0].islower():  # a wrapped line, e.g. "... CGPA" / "8.4/10"
            entries[-1] = f"{entries[-1]} {line}"
        else:
            entries[-1] = f"{entries[-1]}, {line}"
    return entries


def extract_certifications(cert_section: str, sections: dict[str, str]) -> list[str]:
    lines = [line.strip("- ").strip() for line in cert_section.split("\n") if line.strip("- ").strip()]
    if not lines:  # no heading: look for lines that mention a certification outside education
        searchable = "\n".join(v for k, v in sections.items() if k != "education")
        lines = [line.strip("- ").strip() for line in searchable.split("\n") if _CERTIFICATION_HINT.search(line)]
    return list(dict.fromkeys(line for line in lines if len(line) <= 200))[:15]


def extract_projects(projects_section: str) -> list[dict]:
    """
    A non-bullet line starts a new project (its title); bullet lines describe it.
    If every line is a bullet, each bullet is its own project ("Title: description").
    """
    projects: list[dict] = []
    current: dict | None = None
    for line in (l.strip() for l in projects_section.split("\n")):
        if not line:
            continue
        if line.startswith("- ") and current is not None and current["has_title_line"]:
            current["description"] += ("\n" if current["description"] else "") + line[2:]
            continue
        text = line[2:] if line.startswith("- ") else line
        # "Resume Matcher: Built a ..." / "Resume Matcher - Built a ..." -> title + description
        split = _PROJECT_TITLE_SPLIT.match(text)
        title, rest = (split.group(1), split.group(2)) if split else (text, "")
        current = {"title": title.strip()[:150], "description": rest.strip(), "has_title_line": not line.startswith("- ")}
        projects.append(current)
    for project in projects:
        project.pop("has_title_line")
        project["skills"] = extract_skills(f"{project['title']}\n{project['description']}")
    return projects


# --- Orchestration ---------------------------------------------------------------------------
def extract_candidate_info(raw_text: str, meta: dict | None = None, today: date | None = None) -> ParsedResume:
    """Extract every field from already-extracted resume text."""
    text = clean_text(raw_text)
    sections = split_sections(text)
    warnings: list[str] = []

    name, name_method = extract_name(text, sections.get("header", ""))
    email = extract_email(sections.get("header", "")) or extract_email(text)
    phone = extract_phone(sections.get("header", "")) or extract_phone(text)
    # URLs and e-mails are removed first so "github.com/x" or "python.dev@..." don't count as skills.
    skills = extract_skills(URL_OR_EMAIL_RE.sub(" ", text))
    education = extract_education(sections.get("education", ""), text)
    experience = summarize_experience(sections, text, today=today)

    for label, value in (("name", name), ("email address", email), ("phone number", phone)):
        if not value:
            warnings.append(f"Candidate {label} not found in the resume.")
    if not skills:
        warnings.append("No technical skills from the skills dictionary were found.")
    if not education:
        warnings.append("No education details were found.")
    if len(sections) == 1:
        warnings.append("No standard section headings were detected; extraction may be less accurate.")
    warnings.extend(experience.warnings)
    if (meta or {}).get("ocr_used"):
        warnings.append("Text was read with OCR from a scanned PDF; please verify the extracted details.")

    summary = sections.get("summary") or None
    return ParsedResume(
        name=name,
        email=email,
        phone=phone,
        links=extract_links(text),
        summary=summary[:1000] if summary else None,
        skills=skills,
        skills_by_category=group_skills_by_category(skills),
        education=education,
        degree_levels=detect_degree_levels("\n".join(education)),
        certifications=extract_certifications(sections.get("certifications", ""), sections),
        projects=extract_projects(sections.get("projects", "")),
        experience=experience.entries_as_dicts(),
        total_experience_years=experience.total_years,
        internship_experience_years=experience.internship_years,
        stated_experience_years=experience.stated_years,
        experience_method=experience.method,
        is_fresher=experience.is_fresher,
        sections_found=[key for key in sections if key != "header"],
        warnings=warnings,
        text=text,
        meta={**(meta or {}), "name_method": name_method},
    )


def parse_resume(content: bytes, extension: str, today: date | None = None) -> ParsedResume:
    """Full pipeline for one uploaded file (bytes + '.pdf'/'.docx'). Raises DocumentParseError subclasses."""
    raw_text, meta = extract_text(content, extension)
    return extract_candidate_info(raw_text, meta=meta, today=today)
