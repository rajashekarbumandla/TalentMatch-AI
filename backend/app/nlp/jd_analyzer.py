"""
Job Description (JD) analyzer: free text -> structured, editable job requirements.

Pipeline
    1. clean_text()      same normalisation as resumes (bullets, dashes, spacing)
    2. split_sections()  Responsibilities / Requirements / Nice to have / About us / Benefits ...
    3. sentence units    each bullet line, and each sentence of prose (spaCy sentence splitter);
                         a sentence is split again at ";" so "Python required; Docker is a plus"
                         becomes two units with different meanings
    4. classify units    every unit gets a context:
                           preferred - in a "Nice to have" section, or contains a cue such as
                                       "preferred", "is a plus", "good to have", "bonus"
                           company   - "About us" / "Benefits" (skills there are only keywords)
                           required  - everything else
    5. extract           skills (dictionary), experience (regex on "experience" sentences),
                         education (degree keywords), responsibilities (section or verb-first
                         sentences, using spaCy part-of-speech tags), job title, keywords

The result is a *suggestion*: the recruiter reviews and edits it before saving.
A skill that is both required and preferred is kept only as required (no double counting).
"""
import re
from collections import Counter
from dataclasses import asdict, dataclass, field

from app.nlp.education import detect_degree_levels, lowest_degree_level, mentions_education
from app.nlp.skill_extractor import extract_skill_requirements, find_skill_mentions, split_alternatives
from app.nlp.spacy_model import get_spacy_model
from app.parser.sections import build_heading_lookup, split_sections
from app.utils.text_cleaner import clean_text

MIN_JD_CHARS = 30

JD_SECTION_HEADINGS: dict[str, list[str]] = {
    "description": [
        "job description", "description", "overview", "job overview", "role overview", "about the role",
        "the role", "job summary", "position summary", "summary", "about the job", "about the position",
    ],
    "responsibilities": [
        "responsibilities", "key responsibilities", "roles and responsibilities", "role and responsibilities",
        "job responsibilities", "your responsibilities", "duties", "key duties", "what you will do",
        "what you'll do", "what you will be doing", "your role", "day to day", "in this role you will",
    ],
    "requirements": [
        "requirements", "job requirements", "qualifications", "required qualifications", "minimum qualifications",
        "basic qualifications", "required skills", "skills required", "must have", "must have skills",
        "must-have skills", "what we're looking for", "what we are looking for", "what you'll need",
        "what you will need", "what you bring", "who you are", "technical requirements", "skills and qualifications",
        "requirements and qualifications", "eligibility", "eligibility criteria", "desired candidate profile",
        "skills", "technical skills", "key skills", "education", "experience",
    ],
    "preferred": [
        "nice to have", "nice-to-have", "good to have", "nice to have skills", "good to have skills",
        "preferred qualifications", "preferred skills", "preferred", "bonus", "bonus points", "bonus skills",
        "desirable", "desirable skills", "desired skills", "additional skills", "plus", "pluses",
        "it's a plus", "optional",
    ],
    "company": [
        "about us", "about the company", "who we are", "company overview", "our company", "about",
        "benefits", "perks", "perks and benefits", "what we offer", "why join us", "compensation",
        "salary and benefits", "how to apply", "equal opportunity",
    ],
}
JD_HEADING_LOOKUP = build_heading_lookup(JD_SECTION_HEADINGS)

PREFERRED_CUE = re.compile(
    r"\b(?:nice[- ]to[- ]have|good[- ]to[- ]have|preferred|preferably|plus point|(?:is|are|would be) a (?:big |strong )?plus|"
    r"an? (?:added )?advantage|advantageous|bonus|desirable|desired|ideally|optional|beneficial|would be great)\b",
    re.I,
)
TITLE_NOUNS = (
    r"developer|engineer|scientist|analyst|architect|manager|designer|intern|lead|administrator|specialist|"
    r"consultant|programmer|tester|researcher|associate|trainee"
)
_TITLE_LABEL = re.compile(r"^(?:job\s*title|position|role|designation|title|opening)\s*[:\-]\s*(.{2,80})$", re.I)
_TITLE_AFTER_HIRING = re.compile(
    rf"(?:looking for|hiring|seeking|searching for|in search of|recruiting)\s+(?:an?\s+|the\s+|our\s+(?:next\s+)?)?"
    rf"(?P<title>(?:[\w+#./()-]+\s+){{0,4}}?(?:{TITLE_NOUNS})s?)\b",
    re.I,
)
_TITLE_ADJECTIVES = re.compile(
    r"^(?:(?:an?|the|experienced|talented|skilled|passionate|motivated|driven|enthusiastic|dynamic|highly)\s+)+", re.I
)

# --- Experience ----------------------------------------------------------------------------------
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15,
}
_YEARS = r"(?:years?|yrs?)"
_NUM = r"(\d{1,2}(?:\.\d)?)"
_EXP_RANGE = re.compile(rf"{_NUM}\s*(?:-|to)\s*{_NUM}\s*\+?\s*{_YEARS}", re.I)
_EXP_MIN = re.compile(
    rf"(?:at\s+least|minimum(?:\s+of)?|min\.?|over|more\s+than|no\s+less\s+than)\s+{_NUM}\s*\+?\s*{_YEARS}", re.I
)
_EXP_PLUS = re.compile(rf"{_NUM}\s*\+\s*{_YEARS}", re.I)
_EXP_PLAIN = re.compile(rf"{_NUM}\s*{_YEARS}(?:'s?)?\s+(?:of\s+)?(?:[\w/+#.,-]+\s+){{0,5}}?(?:experience|exp\b)", re.I)
_EXP_MONTHS = re.compile(r"(\d{1,2})\s*months?\s+(?:of\s+)?(?:[\w/+#.-]+\s+){0,3}?experience", re.I)
_EXP_CONTEXT = re.compile(r"experience|\bexp\b|experienced", re.I)
_FRESHER = re.compile(
    r"\bfreshers?\b|\bentry[- ]level\b|\bno (?:prior |previous )?experience (?:is )?(?:required|needed)\b|"
    r"\brecent graduates?\b",
    re.I,
)

# --- Responsibilities -----------------------------------------------------------------------------
RESPONSIBILITY_VERBS = {
    "design", "develop", "build", "implement", "create", "write", "maintain", "own", "lead", "manage", "collaborate",
    "work", "deploy", "optimize", "optimise", "improve", "test", "debug", "troubleshoot", "document", "review",
    "mentor", "participate", "support", "analyze", "analyse", "integrate", "deliver", "ensure", "monitor",
    "architect", "automate", "drive", "coordinate", "conduct", "contribute", "define", "translate", "research",
    "evaluate", "communicate", "partner", "scale", "ship", "help", "prepare", "perform", "provide", "identify",
}
_RESPONSIBILITY_PHRASE = re.compile(r"\b(?:you will|you'll|responsible for|your role|you would|you are expected to)\b", re.I)
_REQUIREMENT_HINT = re.compile(
    r"\b(?:years?|degree|bachelor|master|must have|should have|proficien|knowledge of|experience (?:in|with)|"
    r"familiar|understanding of|required|qualification)\b",
    re.I,
)

# Generic JD words that are never useful as keywords.
_GENERIC_WORDS = {
    "experience", "candidate", "candidates", "team", "teams", "skills", "skill", "years", "year", "ability",
    "abilities", "work", "role", "company", "job", "knowledge", "understanding", "degree", "qualification",
    "qualifications", "requirements", "responsibilities", "opportunity", "environment", "plus", "bonus",
    "communication", "level", "proficiency", "field", "position", "applicants", "people", "time", "part",
    "way", "use", "equivalent", "computer", "science", "bachelor", "master", "developer", "engineer", "members",
    "member", "stakeholders", "salary", "benefits", "office", "location", "days", "day", "things", "lot",
    "senior", "junior", "key", "overview", "title", "description", "fictional", "programme", "program",
    "graduate", "graduates", "fresher", "freshers", "business", "related", "strong", "hands", "exposure",
    "familiarity", "fundamentals", "convert", "train", "package", "requirement",
}


class JDAnalysisError(ValueError):
    """Raised for unusable input (empty / too short JD), with a user-friendly message."""


@dataclass
class JDAnalysis:
    job_title: str | None
    required_skills: list[str]
    preferred_skills: list[str]
    minimum_experience: float | None  # None = the JD states no experience requirement
    maximum_experience: float | None
    experience_evidence: str | None
    education_requirements: str | None
    education_level: str | None  # lowest required degree level, e.g. "bachelor"
    responsibilities: list[str]
    keywords: list[str]
    skill_evidence: dict[str, str] = field(default_factory=dict)  # skill -> sentence it came from
    sections_found: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    description: str = ""  # the cleaned JD text (needed when the JD came from an uploaded file)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class _Unit:
    text: str
    section: str
    context: str  # required | preferred | company


# --- Step 3/4: units ----------------------------------------------------------------------------------
def _split_sentences(text: str) -> list[str]:
    nlp = get_spacy_model()
    if nlp is not None:
        return [s.text.strip() for s in nlp(text).sents if s.text.strip()]
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text) if s.strip()]


def _section_context(section: str) -> str:
    return {"preferred": "preferred", "company": "company"}.get(section, "required")


def build_units(sections: dict[str, str]) -> list[_Unit]:
    units: list[_Unit] = []
    for section, content in sections.items():
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            line = line[2:].strip() if line.startswith("- ") else line
            sentences = _split_sentences(line) if len(line) > 120 or re.search(r"[.!?]\s+[A-Z]", line) else [line]
            for sentence in sentences:
                for clause in (c.strip() for c in sentence.split(";")):
                    if not clause:
                        continue
                    context = _section_context(section)
                    if context == "required" and PREFERRED_CUE.search(clause):
                        context = "preferred"
                    units.append(_Unit(clause, section, context))
    return units


# --- Step 5: extractors -------------------------------------------------------------------------------
def extract_job_title(text: str, units: list[_Unit]) -> str | None:
    """Explicit 'Job Title:' label > a short first line naming a role > 'looking for a <title>' phrase."""
    for line in text.split("\n")[:15]:
        labelled = _TITLE_LABEL.match(line.strip("- ").strip())
        if labelled:
            return labelled.group(1).strip(" .")
    first_line = text.strip().split("\n")[0].strip()
    if len(first_line.split()) <= 8 and not first_line.endswith(".") and re.search(rf"\b(?:{TITLE_NOUNS})\b", first_line, re.I):
        return first_line
    for unit in units[:10]:
        hiring = _TITLE_AFTER_HIRING.search(unit.text)
        if hiring:
            title = _TITLE_ADJECTIVES.sub("", hiring.group("title")).strip()
            return title if any(ch.isupper() for ch in title) else title.title()
    return None


def _normalize_number_words(text: str) -> str:
    # "three (3) years" -> "3 years"; "five years" -> "5 years"
    text = re.sub(
        r"\b(" + "|".join(_NUMBER_WORDS) + r")\b(?=\s*(?:\(\s*\d+\s*\)\s*)?\+?\s*(?:years?|yrs?))",
        lambda m: str(_NUMBER_WORDS[m.group(1).lower()]),
        text,
        flags=re.I,
    )
    return re.sub(r"(\d+)\s*\(\s*\d+\s*\)", r"\1", text)


def experience_bounds(sentence: str) -> tuple[float, float | None] | None:
    """(minimum, maximum) years stated in one sentence, or None if it states no requirement."""
    sentence = _normalize_number_words(sentence)
    if not _EXP_CONTEXT.search(sentence):
        return None
    if match := _EXP_RANGE.search(sentence):
        low, high = float(match.group(1)), float(match.group(2))
        return (low, high) if low <= high else (high, low)
    # A sentence can contain several numbers, e.g. "5+ years of development experience,
    # including at least 2 years with Python": the overall requirement is the largest (5).
    lower_bounds = [float(m.group(1)) for p in (_EXP_MIN, _EXP_PLUS, _EXP_PLAIN) for m in p.finditer(sentence)]
    if lower_bounds:
        return max(lower_bounds), None
    if match := _EXP_MONTHS.search(sentence):
        return round(int(match.group(1)) / 12, 2), None
    return None


def extract_experience(units: list[_Unit]) -> tuple[float | None, float | None, str | None]:
    """
    Overall minimum = the LARGEST lower bound among required statements, e.g.
    "5+ years in software development; 2+ years with FastAPI" -> 5.
    Statements in preferred context ("7 years preferred") do not raise the minimum.
    """
    best: tuple[float, float | None, str] | None = None
    fresher_evidence = None
    for unit in units:
        if unit.context != "required":
            continue
        bounds = experience_bounds(unit.text)
        if bounds and 0 <= bounds[0] <= 40 and (best is None or bounds[0] > best[0]):
            best = (bounds[0], bounds[1], unit.text)
        elif _FRESHER.search(unit.text) and fresher_evidence is None:
            fresher_evidence = unit.text
    if best:
        return best
    if fresher_evidence:
        return 0.0, None, fresher_evidence
    return None, None, None


def extract_education(units: list[_Unit]) -> tuple[str | None, str | None]:
    """Education requirement text (from the degree keyword to the end of the sentence) and lowest level."""
    phrases, required_levels = [], []
    for unit in units:
        if unit.context == "company" or not mentions_education(unit.text):
            continue
        start = re.search(
            r"\b(?:any graduate|bachelor|master|b\.?\s?tech|b\.e|m\.?\s?tech|m\.sc|b\.sc|mca|bca|mba|ph\.?\s?d|diploma|"
            r"degree|graduation|post[- ]?graduat\w*)",
            unit.text,
            re.I,
        )
        phrase = unit.text[start.start():] if start else unit.text
        phrase = phrase.strip().rstrip(".")
        phrase = phrase[0].upper() + phrase[1:]
        if phrase not in phrases:
            phrases.append(phrase)
        if unit.context == "required":
            required_levels.extend(detect_degree_levels(unit.text))
    return ("; ".join(phrases) if phrases else None), lowest_degree_level(required_levels)


def _first_word_is_verb(sentence: str) -> bool:
    first = re.match(r"[A-Za-z]+", sentence)
    if not first:
        return False
    if first.group(0).lower() in RESPONSIBILITY_VERBS:
        return True
    nlp = get_spacy_model()
    if nlp is None:
        return False
    tokens = nlp(sentence[:120])
    return len(tokens) > 0 and tokens[0].tag_ == "VB"  # base-form verb = imperative ("Deploy models ...")


def extract_responsibilities(units: list[_Unit]) -> list[str]:
    from_section = [u.text for u in units if u.section == "responsibilities"]
    if from_section:
        candidates = from_section
    else:
        candidates = [
            u.text for u in units
            if u.context != "company"
            and (_RESPONSIBILITY_PHRASE.search(u.text) or _first_word_is_verb(u.text))
            and not _REQUIREMENT_HINT.search(u.text)
        ]
    cleaned = [c.rstrip(".").strip() for c in candidates if len(c.split()) >= 3]
    return list(dict.fromkeys(cleaned))[:20]


def extract_keywords(units: list[_Unit], skills: list[str], limit: int = 8) -> list[str]:
    """
    Technical keywords = every recognised skill, plus up to `limit` domain nouns that
    appear at least twice (e.g. "payments", "models"), found with spaCy part-of-speech tags.
    Proper nouns (usually company names), headings and verbs are skipped.
    """
    keywords = list(skills)
    nlp = get_spacy_model()
    if nlp is None:
        return keywords
    known = {part.lower() for s in skills for part in split_alternatives(s)}
    counts: Counter = Counter()
    first_seen: dict[str, int] = {}
    for unit in units:
        # Blank out skill mentions, so "Machine Learning" doesn't also yield "machine" and "learning".
        masked = list(unit.text)
        for start, end, _ in find_skill_mentions(unit.text):
            masked[start:end] = " " * (end - start)
        for token in nlp("".join(masked)):
            word = token.text.lower()
            key = word[:-1] if word.endswith("s") and len(word) > 4 else word  # "payments" ~ "payment"
            if (
                token.tag_ in {"NN", "NNS"}
                and not token.is_stop
                and len(word) > 2
                and word.isalpha()
                and key not in _GENERIC_WORDS
                and word not in _GENERIC_WORDS
                and key not in RESPONSIBILITY_VERBS
                and key not in known
            ):
                counts[key] += 1
                first_seen.setdefault(key, len(first_seen))
    ranked = [w for w in sorted(counts, key=lambda w: (-counts[w], first_seen[w])) if counts[w] >= 2]
    keywords.extend(ranked[:limit])
    return keywords


# --- Public API ------------------------------------------------------------------------------------------
def analyze_job_description(description: str, job_title: str | None = None) -> JDAnalysis:
    """Analyze JD text. `job_title`, if the recruiter typed one, overrides the detected title."""
    text = clean_text(description)
    if len(text) < MIN_JD_CHARS:
        raise JDAnalysisError(
            f"The job description is empty or too short (minimum {MIN_JD_CHARS} characters). "
            "Paste the full JD or upload it as a PDF/DOCX."
        )

    sections = split_sections(text, JD_HEADING_LOOKUP)
    units = build_units(sections)
    warnings: list[str] = []

    required: dict[str, None] = {}
    preferred: dict[str, None] = {}
    company_skills: dict[str, None] = {}
    evidence: dict[str, str] = {}
    for unit in units:
        for skill in extract_skill_requirements(unit.text):
            target = {"required": required, "preferred": preferred, "company": company_skills}[unit.context]
            target.setdefault(skill, None)
            if unit.context != "company":
                evidence.setdefault(skill, unit.text)
    # An "A or B" group is redundant when A (or B) is already required on its own:
    # "FastAPI" + "FastAPI or Django" -> just "FastAPI".
    required_singles = {s for s in required if len(split_alternatives(s)) == 1}
    required_skills = [
        s for s in required
        if len(split_alternatives(s)) == 1 or not set(split_alternatives(s)) & required_singles
    ]
    # Required wins: a skill already required (alone or as an alternative) is not also preferred.
    required_parts = {part for s in required_skills for part in split_alternatives(s)}
    preferred_skills = [s for s in preferred if not set(split_alternatives(s)) <= required_parts]

    title = (job_title or "").strip() or extract_job_title(text, units)
    minimum, maximum, experience_evidence = extract_experience(units)
    education, education_level = extract_education(units)
    responsibilities = extract_responsibilities(units)
    all_parts = {part for s in required_skills + preferred_skills for part in split_alternatives(s)}
    context_skills = [s for s in company_skills if not set(split_alternatives(s)) <= all_parts]
    keywords = extract_keywords(units, required_skills + preferred_skills + context_skills)

    if not title:
        warnings.append("Job title could not be detected; please enter it.")
    if not required_skills and not preferred_skills:
        warnings.append(
            "No technical skills from the skills dictionary were recognised. Add the required skills "
            "manually, otherwise skill matching cannot be scored."
        )
    elif not required_skills:
        warnings.append("Only preferred skills were found; consider marking the essential ones as required.")
    if minimum is None:
        warnings.append("No minimum experience requirement was found; experience will not limit candidate scores.")
    if not responsibilities:
        warnings.append("No responsibilities were identified.")

    return JDAnalysis(
        job_title=title or None,
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        minimum_experience=minimum,
        maximum_experience=maximum,
        experience_evidence=experience_evidence,
        education_requirements=education,
        education_level=education_level,
        responsibilities=responsibilities,
        keywords=keywords,
        skill_evidence=evidence,
        sections_found=[key for key in sections if key != "header"],
        warnings=warnings,
        description=text,
    )


def analyze_job_description_file(content: bytes, filename: str, job_title: str | None = None) -> JDAnalysis:
    """Validate an uploaded PDF/DOCX JD, extract its text, then analyze it."""
    from app.parser import extract_text
    from app.utils.file_validator import validate_document_file

    validated = validate_document_file(filename, content)
    text, _ = extract_text(validated.content, validated.extension)
    return analyze_job_description(text, job_title=job_title)
