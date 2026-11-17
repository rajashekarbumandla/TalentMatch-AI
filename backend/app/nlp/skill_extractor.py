"""
Technical skill extraction using a configurable dictionary (nlp/data/skills.json).

How a skill is detected
-----------------------
Every alias becomes a regular expression with custom "word boundaries":
- it must not be preceded by a letter, digit, "_" or "." and
- it must not be followed by a letter, digit, "_", "+" or "#".

That is what prevents false matches:
    "C"     does not match inside "C++" or "C#"   (followed by + or #)
    "Java"  does not match inside "JavaScript"    (followed by a letter)
    "SQL"   does not match inside "PostgreSQL"    (preceded by a letter)
    "JS"    does not match inside "Node.js"       (preceded by ".")

Overlapping matches are resolved "longest first": in "Java Script" the
JavaScript alias (11 chars) wins over "Java" (4 chars), and in "React Native"
the React Native skill wins over React.

Every alias maps to one canonical name, so "ML", "Postgres" and "RESTful API"
are reported as "Machine Learning", "PostgreSQL" and "REST APIs".
"""
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SKILLS_FILE = Path(__file__).resolve().parent / "data" / "skills.json"

_BEFORE = r"(?<![A-Za-z0-9_.])"
_AFTER = r"(?![A-Za-z0-9_+#])"


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    category: str
    aliases: tuple[str, ...]
    pattern: re.Pattern
    implies: tuple[str, ...] = ()  # e.g. Django -> ("Python",); used only for experience relevance


def _alias_key(text: str) -> str:
    """Lookup key used when normalising typed skills: lowercase, spaces/hyphens collapsed."""
    return re.sub(r"[\s\-]+", " ", text.strip().lower())


def _alias_to_regex(alias: str) -> str:
    """Escape an alias and let spaces/hyphens inside it match any run of spaces or hyphens."""
    parts = re.split(r"[\s\-]+", alias.strip())
    return r"[\s\-]+".join(re.escape(part) for part in parts)


def _build_pattern(aliases: list[str], case_sensitive: set[str]) -> re.Pattern:
    alternatives = []
    for alias in aliases:
        body = _alias_to_regex(alias)
        if len(alias) == 1:
            # Single letters (the "C" language) need stricter rules: not "Objective-C",
            # not "C-level", and not a name initial such as "John C. Smith".
            body = rf"(?<![\-/']){body}(?!-|\.\s*[A-Z]|\.[A-Za-z])"
        # (?-i:...) switches case-insensitivity off for this one alias only.
        alternatives.append(f"(?-i:{body})" if alias in case_sensitive else body)
    # Longer aliases first so the regex prefers "REST APIs" over "REST".
    alternatives.sort(key=len, reverse=True)
    return re.compile(f"{_BEFORE}(?:{'|'.join(alternatives)}){_AFTER}", re.IGNORECASE)


@lru_cache(maxsize=1)
def load_skill_dictionary(path: str = str(SKILLS_FILE)) -> tuple[SkillDefinition, ...]:
    """Load and compile the dictionary once (cached for the lifetime of the process)."""
    with open(path, encoding="utf-8") as file:
        raw = json.load(file)
    definitions = []
    for category, skills in raw.items():
        if category.startswith("_"):
            continue  # comments
        for name, spec in skills.items():
            aliases = spec.get("aliases") or [name]
            pattern = _build_pattern(aliases, set(spec.get("case_sensitive", [])))
            definitions.append(
                SkillDefinition(
                    name=name, category=category, aliases=tuple(aliases), pattern=pattern,
                    implies=tuple(spec.get("implies", [])),
                )
            )
    return tuple(definitions)


@lru_cache(maxsize=1)
def _skill_index() -> dict[str, SkillDefinition]:
    """Canonical name or any alias (case-insensitive) -> skill definition."""
    index: dict[str, SkillDefinition] = {}
    for definition in load_skill_dictionary():
        for key in (definition.name, *definition.aliases):
            index.setdefault(_alias_key(key), definition)
    return index


def find_skill_mentions(text: str) -> list[tuple[int, int, SkillDefinition]]:
    """All non-overlapping skill mentions as (start, end, skill), in text order."""
    if not text:
        return []
    candidates = []
    for skill in load_skill_dictionary():
        for match in skill.pattern.finditer(text):
            candidates.append((match.start(), match.end(), skill))

    # Longest-first: keep a mention only if it does not overlap an already-accepted longer one.
    candidates.sort(key=lambda m: (-(m[1] - m[0]), m[0]))
    accepted: list[tuple[int, int, SkillDefinition]] = []
    for start, end, skill in candidates:
        if all(end <= a_start or start >= a_end for a_start, a_end, _ in accepted):
            accepted.append((start, end, skill))
    return sorted(accepted, key=lambda m: m[0])


def extract_skill_requirements(text: str) -> list[str]:
    """
    Like extract_skills(), but skills joined by "or" become ONE requirement:
    "experience with FastAPI or Django, and Docker" -> ["FastAPI or Django", "Docker"].
    Used for job descriptions. ("HTML/CSS" means both, so only the word "or" groups skills.)
    """
    mentions = find_skill_mentions(text)
    groups: list[list[str]] = []
    previous_end = None
    for start, end, skill in mentions:
        between = text[previous_end:start] if previous_end is not None else ""
        if groups and re.fullmatch(r"\s*,?\s*or\s+(?:an?\s+|the\s+)?", between, re.I):
            if skill.name not in groups[-1]:
                groups[-1].append(skill.name)
        else:
            groups.append([skill.name])
        previous_end = end
    return list(dict.fromkeys(ALTERNATIVE_SEPARATOR.join(group) for group in groups))


def extract_skills(text: str) -> list[str]:
    """Canonical skill names found in the text, in order of first appearance, without duplicates."""
    seen: dict[str, None] = {}
    for _, _, skill in find_skill_mentions(text):
        seen.setdefault(skill.name, None)
    return list(seen)


def extract_skills_with_details(text: str) -> list[dict]:
    """Like extract_skills() but also returns category and how many times each skill is mentioned."""
    details: dict[str, dict] = {}
    for _, _, skill in find_skill_mentions(text):
        entry = details.setdefault(skill.name, {"name": skill.name, "category": skill.category, "mentions": 0})
        entry["mentions"] += 1
    return list(details.values())


def group_skills_by_category(skills: list[str]) -> dict[str, list[str]]:
    index = _skill_index()
    grouped: dict[str, list[str]] = {}
    for skill in skills:
        definition = index.get(_alias_key(skill))
        grouped.setdefault(definition.category if definition else "Other", []).append(skill)
    return grouped


ALTERNATIVE_SEPARATOR = " or "


def split_alternatives(requirement: str) -> list[str]:
    """
    A requirement may list interchangeable skills: "FastAPI or Django" is satisfied by
    EITHER skill. Returns ["FastAPI", "Django"]; a plain skill returns [skill].
    """
    return [part.strip() for part in re.split(r"\s+or\s+", requirement or "", flags=re.I) if part.strip()]


def normalize_skill(raw: str) -> str:
    """
    Map any spelling to its canonical name: "postgres" -> "PostgreSQL", "ML" -> "Machine Learning".
    Alternatives are normalised part by part: "pytorch or tensorflow" -> "PyTorch or TensorFlow".
    Unknown skills are returned tidied but unchanged, so recruiters can still use them.
    """
    cleaned = re.sub(r"\s+", " ", (raw or "").strip())
    if not cleaned:
        return ""
    parts = split_alternatives(cleaned)
    if len(parts) > 1:
        return ALTERNATIVE_SEPARATOR.join(dict.fromkeys(normalize_skill(part) for part in parts))
    definition = _skill_index().get(_alias_key(cleaned))
    return definition.name if definition else cleaned


def normalize_skill_list(raw_skills: list[str]) -> list[str]:
    """Normalise and de-duplicate (case-insensitively) while keeping the original order."""
    result: dict[str, str] = {}
    for raw in raw_skills or []:
        name = normalize_skill(raw)
        if name:
            result.setdefault(name.lower(), name)
    return list(result.values())


def expand_implied_skills(skills: list[str]) -> set[str]:
    """
    The skills plus everything they imply (Django -> Python, Spring Boot -> Java).
    Used ONLY to decide whether a past job is relevant to the JD; skill *matching*
    never uses implications, so a candidate is credited only for skills they wrote.
    """
    index = _skill_index()
    result = set(skills)
    for skill in skills:
        definition = index.get(_alias_key(skill))
        if definition:
            result.update(definition.implies)
    return result


def is_known_skill(name: str) -> bool:
    return _alias_key(name or "") in _skill_index()
