"""
Split resume text into sections (summary, skills, experience, education, ...).

A line is treated as a section heading when, after removing bullets, punctuation
and a trailing colon, it exactly matches one of the known headings below
(case-insensitive). Inline headings such as "Skills: Python, SQL" are split into
the heading and its first content line.

Text before the first heading (usually the name and contact details) is stored
under the key "header".
"""
import re

SECTION_HEADINGS: dict[str, list[str]] = {
    "summary": [
        "summary", "professional summary", "career summary", "profile", "professional profile",
        "objective", "career objective", "about me", "overview",
    ],
    "skills": [
        "skills", "technical skills", "key skills", "core skills", "core competencies", "skill set",
        "skills summary", "tech stack", "technologies", "technical expertise", "tools and technologies",
        "technical proficiency", "skills and tools",
    ],
    "experience": [
        "experience", "work experience", "professional experience", "employment history", "work history",
        "employment", "career history", "relevant experience", "industry experience",
    ],
    "internships": [
        "internships", "internship", "internship experience", "internships and training", "training and internships",
    ],
    "education": [
        "education", "academic background", "academic qualifications", "educational qualifications",
        "education and training", "academics", "academic details", "qualifications",
    ],
    "projects": [
        "projects", "academic projects", "personal projects", "key projects", "project experience",
        "major projects", "side projects", "project work", "notable projects",
    ],
    "certifications": [
        "certifications", "certification", "certificates", "licenses and certifications",
        "courses and certifications", "certifications and courses", "professional certifications", "courses",
    ],
    "achievements": ["achievements", "awards", "awards and achievements", "honors and awards", "accomplishments"],
    "languages": ["languages", "languages known"],
    "interests": ["interests", "hobbies", "hobbies and interests", "extracurricular activities"],
    "personal": ["personal details", "personal information", "declaration", "references"],
}

_INLINE_HEADING = re.compile(r"^\s*(?:-\s*)?([A-Za-z &/]{3,40}?)\s*:\s*(.+)$")
_NO_INLINE_SWITCH = {"languages"}
_NO_INLINE_SWITCH_INSIDE = {"experience", "internships", "projects"}


def _normalize_heading(line: str) -> str:
    line = line.lower().replace("&", " and ").replace("'", "").replace("’", "")
    line = re.sub(r"[^a-z ]", " ", line)
    return re.sub(r"\s+", " ", line).strip()


def build_heading_lookup(headings: dict[str, list[str]]) -> dict[str, str]:
    """{normalised heading text: section key}, e.g. {"what youll do": "responsibilities"}."""
    return {_normalize_heading(h): key for key, variants in headings.items() for h in variants}


RESUME_HEADING_LOOKUP = build_heading_lookup(SECTION_HEADINGS)


def match_heading(line: str, lookup: dict[str, str] = RESUME_HEADING_LOOKUP) -> str | None:
    """Return the section key if the whole line is a heading, else None."""
    if not line or len(line) > 45:
        return None
    return lookup.get(_normalize_heading(line))


def split_sections(text: str, lookup: dict[str, str] = RESUME_HEADING_LOOKUP) -> dict[str, str]:
    """
    Return {section_key: section_text}. Repeated sections (e.g. two project lists)
    are concatenated. `lookup` selects the heading vocabulary (resume by default,
    the JD analyzer passes its own).
    """
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in text.split("\n"):
        key = match_heading(line, lookup)
        if key:
            current = key
            sections.setdefault(current, [])
            continue
        inline = _INLINE_HEADING.match(line)
        inline_key = match_heading(inline.group(1), lookup) if inline else None
        # "Languages: Python, SQL" inside Skills, or "Technologies: Flask" inside a job entry,
        # are sub-labels, not new sections.
        if inline_key and inline_key not in _NO_INLINE_SWITCH and current not in _NO_INLINE_SWITCH_INSIDE:
            current = inline_key
            sections.setdefault(current, []).append(inline.group(2).strip())
            continue
        sections[current].append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}
