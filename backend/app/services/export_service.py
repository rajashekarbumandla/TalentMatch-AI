"""
CSV export of an analysis' ranked candidates.

Security: spreadsheet programs treat a cell that starts with = + - @ (or tab/CR)
as a formula. Resume text is untrusted, so such values are prefixed with an
apostrophe ("CSV injection" protection) and are shown as plain text.
The file starts with a UTF-8 BOM so Excel displays non-English names correctly.
"""
import csv
import io

from app.matching.ranking import RankedCandidate

CSV_COLUMNS = [
    "Rank", "Candidate Name", "Email", "Phone", "Total Experience (years)", "Relevant Experience (years)",
    "Final Score", "Semantic Score", "Skills Score", "Experience Score", "Matched Skills", "Missing Skills",
    "Additional Skills", "Status", "Resume File", "Explanation",
]
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    text = str(value)
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


def ranked_candidates_to_csv(items: list[RankedCandidate]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for item in items:
        match, candidate = item.match, item.candidate
        writer.writerow([safe_cell(v) for v in (
            item.rank,
            candidate.name or "Not found",
            candidate.email or "Not found",
            candidate.phone or "Not found",
            candidate.total_experience,
            match.relevant_experience,
            match.final_score,
            match.semantic_score,
            match.skills_score,
            match.experience_score,
            "; ".join(match.matched_skills),
            "; ".join(match.missing_skills),
            "; ".join(match.additional_skills),
            (match.details or {}).get("status", "complete"),
            candidate.resume_filename,
            match.explanation,
        )])
    return "﻿" + buffer.getvalue()
