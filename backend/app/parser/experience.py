"""
Work-experience extraction.

1. Find employment date ranges such as "Jan 2020 - Present", "03/2018 - 06/2020",
   "2019 to 2021" inside the Experience / Internships sections only (education
   years like "2016 - 2020" must never be counted as work).
2. Group the lines around each date range into an entry: heading (title/company),
   dates, description, and the skills mentioned in that entry.
3. Compute total experience by MERGING overlapping periods, so two parallel jobs
   in 2021 count as one year, not two. Internships are totalled separately and
   are not included in total (professional) experience.

If no dated entries exist, fall back to a statement such as "5+ years of
experience". If nothing reliable is found, experience is reported as UNKNOWN
(None), never silently as 0, unless the resume clearly describes a fresher.
"""
import re
from dataclasses import asdict, dataclass, field
from datetime import date

from app.nlp.skill_extractor import extract_skills

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH = r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
# One date: "Jan 2020", "January, 2020", "03/2020", "2020-03" or just "2020".
_DATE = rf"(?<!\d)(?:(?:{_MONTH})\.?,?\s*'?\d{{4}}|\d{{1,2}}[/.-]\d{{4}}|\d{{4}}(?:[/.-]\d{{1,2}}(?!\d))?)(?!\d)"
_PRESENT = r"present|current(?:ly)?|now|ongoing|till\s+date|to\s+date|today|date"
DATE_RANGE = re.compile(
    rf"(?P<start>{_DATE})\s*(?:-|to|till|until)\s*(?P<end>{_DATE}|{_PRESENT})", re.IGNORECASE
)
_DURATION = re.compile(r"\(?\b(\d{1,2})\s*(months?|mos?|years?|yrs?)\b\)?", re.IGNORECASE)
_STATED = [
    re.compile(r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)(?:\s+(?:of|in))?\s+(?:[\w/&.+#-]+\s+){0,4}?experience", re.I),
    re.compile(r"experience\s+(?:of\s+)?(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)", re.I),
]
_FRESHER = re.compile(r"\b(?:fresher|fresh graduate|recent graduate|entry[- ]level|final[- ]year student)\b", re.I)
_INTERN = re.compile(r"\bintern(?:ship)?s?\b", re.I)
_TITLE_WORDS = re.compile(
    r"\b(?:engineer|developer|analyst|scientist|intern|manager|consultant|lead|architect|designer|administrator|"
    r"specialist|associate|assistant|trainee|programmer|researcher|officer|executive|technician|tester|director|"
    r"freelancer?)\b",
    re.I,
)


@dataclass
class ExperienceEntry:
    heading: str
    title: str | None = None
    company: str | None = None
    start: str | None = None  # "YYYY-MM" (or "YYYY" when only the year is given)
    end: str | None = None  # same format, or "present"
    months: int | None = None
    is_internship: bool = False
    description: str = ""
    skills: list[str] = field(default_factory=list)
    # Month indices (year*12 + month-1) used for overlap merging; [start, end)
    interval: tuple[int, int] | None = None


@dataclass
class ExperienceSummary:
    entries: list[ExperienceEntry]
    total_years: float | None  # professional experience; None = unknown
    internship_years: float | None
    stated_years: float | None  # e.g. "5+ years of experience" found in the text
    method: str  # date_ranges | stated_in_resume | fresher | unknown
    is_fresher: bool
    warnings: list[str]

    def entries_as_dicts(self) -> list[dict]:
        result = []
        for entry in self.entries:
            data = asdict(entry)
            data.pop("interval")
            result.append(data)
        return result


# --- Dates ------------------------------------------------------------------------------
def parse_date(text: str, today: date) -> tuple[int, int | None] | None:
    """Return (year, month) with month None when only the year is given; None if invalid."""
    text = text.strip().lower().rstrip(".")
    if re.fullmatch(_PRESENT, text, re.I):
        return today.year, today.month
    month_name = re.match(rf"({_MONTH})\.?,?\s*'?(\d{{4}})", text, re.I)
    if month_name:
        year, month = int(month_name.group(2)), MONTHS[month_name.group(1)[:3].lower()]
    elif m := re.fullmatch(r"(\d{1,2})[/.-](\d{4})", text):
        month, year = int(m.group(1)), int(m.group(2))
    elif m := re.fullmatch(r"(\d{4})[/.-](\d{1,2})", text):
        year, month = int(m.group(1)), int(m.group(2))
    elif m := re.fullmatch(r"\d{4}", text):
        year, month = int(m.group(0)), None
    else:
        return None
    if not 1950 <= year <= today.year + 1 or (month is not None and not 1 <= month <= 12):
        return None
    return year, month


def _format_date(value: tuple[int, int | None]) -> str:
    year, month = value
    return f"{year}-{month:02d}" if month else str(year)


def date_range_to_interval(start_text: str, end_text: str, today: date):
    """
    Convert a date range to (start_index, end_index_exclusive, label_start, label_end).

    Month-precise ranges are inclusive ("Jan 2020 - Dec 2020" = 12 months).
    Year-only ranges count whole years ("2019 - 2021" = 24 months).
    """
    start, end = parse_date(start_text, today), parse_date(end_text, today)
    if not start or not end:
        return None
    is_present = bool(re.fullmatch(_PRESENT, end_text.strip(), re.I))
    start_index = start[0] * 12 + (start[1] or 1) - 1
    end_index = end[0] * 12 + (end[1] or 1) - 1
    if start[1] and end[1]:
        end_index += 1  # inclusive of the final month
    today_index = today.year * 12 + today.month
    end_index = min(end_index, today_index)  # never count future months
    if end_index <= start_index:
        return None
    return start_index, end_index, _format_date(start), "present" if is_present else _format_date(end)


def entry_interval(entry: dict, today: date) -> tuple[int, int] | None:
    """
    Rebuild the [start, end) month interval of a stored experience entry from its
    "start"/"end" strings ("2021-06", "2019", "present"), so entries loaded from the
    database can be merged exactly like freshly parsed ones.
    """
    start, end = entry.get("start"), entry.get("end")
    if not start or not end:
        return None
    interval = date_range_to_interval(start, end, today)
    return (interval[0], interval[1]) if interval else None


def merge_intervals(intervals: list[tuple[int, int]]) -> int:
    """Total months covered by possibly-overlapping [start, end) intervals."""
    total, current_start, current_end = 0, None, None
    for start, end in sorted(intervals):
        if current_end is None or start > current_end:
            if current_end is not None:
                total += current_end - current_start
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    if current_end is not None:
        total += current_end - current_start
    return total


# --- Entries ----------------------------------------------------------------------------
def _is_bullet(line: str) -> bool:
    return line.startswith("- ")


def _tidy_heading(text: str) -> str:
    text = text.strip(" ,|-")
    return re.sub(r"\(\s*\)|\s*\($", "", text).strip(" ,|-")  # drop empty "()" or a dangling "("


def _split_title_company(heading: str) -> tuple[str | None, str | None]:
    # Prefer strong separators; " - " is only used when there is nothing else,
    # because it also appears inside titles ("Software Engineer - Java").
    separator = r"\s+(?:at|@)\s+|\s*[|,]\s*" if re.search(r"\s(?:at|@)\s|[|,]", heading) else r"\s+-\s+"
    parts = [p.strip(" -") for p in re.split(separator, heading) if p.strip(" -")]
    title = next((p for p in parts if _TITLE_WORDS.search(p)), None)
    company = next((p for p in parts if p != title), None)
    return title, company


def extract_entries(section_text: str, today: date, internship_section: bool = False) -> list[ExperienceEntry]:
    lines = [line.strip() for line in section_text.split("\n") if line.strip()]
    date_lines = [i for i, line in enumerate(lines) if DATE_RANGE.search(line)]

    # Pass 1: find where each entry's heading starts.
    raw_entries = []
    floor = 0
    for i in date_lines:
        match = DATE_RANGE.search(lines[i])
        remainder = _tidy_heading(lines[i][: match.start()] + " " + lines[i][match.end():])
        heading_parts, start_idx, desc_start = [], i, i + 1
        previous = lines[i - 1] if i - 1 >= floor else None
        if previous and not _is_bullet(previous) and (i - 1) not in date_lines and len(previous.split()) <= 12:
            heading_parts.append(previous)
            start_idx = i - 1
        if remainder:
            heading_parts.append(remainder)
        if not heading_parts and i + 1 < len(lines) and not _is_bullet(lines[i + 1]) and (i + 1) not in date_lines:
            heading_parts.append(lines[i + 1])
            desc_start = i + 2
        raw_entries.append((start_idx, desc_start, " | ".join(heading_parts), match))
        floor = i + 1

    # Pass 2: description = lines up to the next entry's heading.
    entries = []
    for n, (start_idx, desc_start, heading, match) in enumerate(raw_entries):
        next_start = raw_entries[n + 1][0] if n + 1 < len(raw_entries) else len(lines)
        description = "\n".join(lines[desc_start:next_start])
        title, company = _split_title_company(heading)
        entry = ExperienceEntry(
            heading=heading,
            title=title,
            company=company,
            is_internship=internship_section or bool(_INTERN.search(heading)),
            description=description,
            skills=extract_skills(f"{heading}\n{description}"),
        )
        interval = date_range_to_interval(match.group("start"), match.group("end"), today)
        if interval:
            entry.interval = (interval[0], interval[1])
            entry.start, entry.end = interval[2], interval[3]
            entry.months = interval[1] - interval[0]
        entries.append(entry)

    # Undated entries in an internship section, e.g. "ML Intern, ABC Labs (6 months)".
    if not entries and internship_section:
        for line in lines:
            duration = _DURATION.search(line)
            if not _is_bullet(line) and duration:
                months = int(duration.group(1)) * (12 if duration.group(2).lower().startswith("y") else 1)
                heading = _tidy_heading(_DURATION.sub("", line))
                title, company = _split_title_company(heading)
                entries.append(ExperienceEntry(heading=heading, title=title, company=company, months=months,
                                               is_internship=True, skills=extract_skills(line)))
    return entries


def find_stated_experience(text: str) -> float | None:
    """Largest 'N years of experience' statement in the text (ignores internship statements)."""
    values = []
    for pattern in _STATED:
        for match in pattern.finditer(text):
            if "intern" in match.group(0).lower():
                continue
            value = float(match.group(1))
            if 0 < value <= 50:
                values.append(value)
    return max(values) if values else None


def summarize_experience(
    sections: dict[str, str], full_text: str, today: date | None = None
) -> ExperienceSummary:
    today = today or date.today()
    warnings: list[str] = []
    entries = extract_entries(sections.get("experience", ""), today)
    entries += extract_entries(sections.get("internships", ""), today, internship_section=True)

    professional = [e for e in entries if not e.is_internship]
    internships = [e for e in entries if e.is_internship]

    def total_months(group: list[ExperienceEntry]) -> int:
        dated = merge_intervals([e.interval for e in group if e.interval])
        undated = sum(e.months for e in group if not e.interval and e.months)
        return dated + undated

    professional_months = total_months(professional)
    internship_months = total_months(internships)
    stated = find_stated_experience(full_text)
    is_fresher = bool(_FRESHER.search(full_text))

    if professional_months > 0:
        total, method = round(professional_months / 12, 1), "date_ranges"
        if any(e.months is None for e in professional):
            warnings.append("Some work-experience entries have no dates; total experience may be underestimated.")
    elif stated is not None:
        total, method = stated, "stated_in_resume"
    elif professional or sections.get("experience", "").strip():
        total, method = None, "unknown"
        warnings.append("Work experience is listed without dates; total experience could not be calculated.")
    elif internships or is_fresher:
        total, method, is_fresher = 0.0, "fresher", True
    else:
        total, method = None, "unknown"
        warnings.append("No work-experience dates or statements were found; experience is unknown.")

    return ExperienceSummary(
        entries=entries,
        total_years=total,
        internship_years=round(internship_months / 12, 1) if internships else None,
        stated_years=stated,
        method=method,
        is_fresher=is_fresher and not professional_months,
        warnings=warnings,
    )
