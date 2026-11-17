"""
Degree detection shared by the resume parser and the JD analyzer.

Abbreviations (B.Tech, M.Sc, MCA, ...) are matched case-sensitively so that the
verb "be" or "MS Excel" are never mistaken for a degree; full words (Bachelor,
Master, Diploma, ...) are case-insensitive.
"""
import re

DEGREE_ABBREVIATIONS = re.compile(
    r"(?<![A-Za-z])(?:B\.?\s?Tech|B\.E\.?(?=\s|,|$)|B\.Sc|BSc|B\.S\.|BCA|B\.C\.A|B\.Com|M\.?\s?Tech|M\.E\.|M\.Sc|MSc|"
    r"M\.S\.|MCA|M\.C\.A|MBA|Ph\.?\s?D)(?![A-Za-z])"
)
DEGREE_WORDS = re.compile(
    r"\b(?:bachelor(?:'s|s)?|master(?:'s|s)?|doctor(?:ate)?|diploma|associate degree|higher secondary|"
    r"senior secondary|secondary school|intermediate|hsc|ssc|class xii|class x|12th|10th)\b",
    re.I,
)
# A generic mention such as "a degree in Computer Science" or "any graduate".
# A bare "graduate" is NOT enough ("Graduate Programme", "recent graduates" are not degree requirements).
GENERIC_DEGREE = re.compile(r"\b(?:degree|graduation|any graduate|graduate degree|post[- ]?graduat\w*)\b", re.I)

# Lowest to highest.
DEGREE_LEVEL_ORDER = ["school", "diploma", "bachelor", "master", "doctorate"]
_LEVEL_PATTERNS = [
    ("doctorate", re.compile(r"ph\.?\s?d|doctor", re.I)),
    ("master", re.compile(r"master|m\.?\s?tech|m\.e\.|m\.sc|msc|m\.s\.|mca|m\.c\.a|mba|post[- ]?graduate", re.I)),
    ("bachelor", re.compile(r"bachelor|b\.?\s?tech|b\.e\.?(?=\s|,|$)|b\.sc|bsc|b\.s\.|bca|b\.c\.a|b\.com|any graduate|graduation", re.I)),
    ("diploma", re.compile(r"diploma", re.I)),
    ("school", re.compile(r"higher secondary|senior secondary|secondary school|intermediate|hsc|ssc|class x|12th|10th", re.I)),
]


def has_degree(text: str) -> bool:
    """True if the text names a specific degree (B.Tech, Bachelor's, M.Sc, Diploma, ...)."""
    return bool(DEGREE_ABBREVIATIONS.search(text) or DEGREE_WORDS.search(text))


def mentions_education(text: str) -> bool:
    """Broader check that also accepts generic wording like 'a degree in Computer Science'."""
    return has_degree(text) or bool(GENERIC_DEGREE.search(text))


def detect_degree_levels(text: str) -> list[str]:
    """Degree levels mentioned, highest first, e.g. ['master', 'bachelor']."""
    found = []
    for level, pattern in _LEVEL_PATTERNS:
        # "post-graduate" is a master's-level phrase, so don't also count it as "graduate" (bachelor).
        searchable = re.sub(r"post[- ]?graduate", "", text, flags=re.I) if level == "bachelor" else text
        if pattern.search(searchable):
            found.append(level)
    return found


def lowest_degree_level(levels: list[str]) -> str | None:
    known = [level for level in levels if level in DEGREE_LEVEL_ORDER]
    return min(known, key=DEGREE_LEVEL_ORDER.index) if known else None
