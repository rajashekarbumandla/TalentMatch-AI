"""
Readable, fact-only explanations of a match.

Every sentence is generated from a computed value (a score, a skill list, a number
of years). Nothing is inferred beyond those facts, so the explanation can never
claim something the resume doesn't support. When information is missing, the
explanation says so and asks the recruiter to verify.
"""


def _list(items: list[str], limit: int = 8) -> str:
    items = list(items)
    if len(items) > limit:
        items = items[:limit] + [f"{len(items) - limit} more"]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _years(value: float) -> str:
    value = round(value, 1)
    text = f"{value:g}"
    return f"{text} year" if value == 1 else f"{text} years"


def overall_band(score: float) -> str:
    if score >= 80:
        return "strong"
    if score >= 60:
        return "good"
    if score >= 40:
        return "partial"
    return "limited"


def semantic_band(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "moderate"
    return "low"


def build_explanation(
    job_title: str,
    final_score: float,
    semantic_score: float | None,
    skills,
    experience,
    internship_years: float | None,
    missing_components: list[str],
) -> str:
    sentences = [
        f"The candidate shows {overall_band(final_score)} alignment with the {job_title} role "
        f"(overall score {final_score:.2f}/100)."
    ]

    # Skills
    required_total = len(skills.matched_required) + len(skills.missing_required)
    if skills.score is None:
        sentences.append("The job description lists no recognised skills, so skills were not scored.")
    else:
        if required_total:
            if skills.matched_required:
                sentences.append(
                    f"{len(skills.matched_required)} of {required_total} required skills were identified in the resume: "
                    f"{_list(skills.matched_required)}."
                )
            else:
                sentences.append(f"None of the {required_total} required skills were identified in the resume.")
            if skills.missing_required and skills.matched_required:
                sentences.append(f"Required skills not identified: {_list(skills.missing_required)}.")
        if skills.matched_preferred:
            sentences.append(f"Preferred skills present: {_list(skills.matched_preferred)}.")
        if skills.missing_preferred:
            sentences.append(f"Preferred skills not identified: {_list(skills.missing_preferred)}.")

    # Experience
    if experience.status == "not_required":
        sentences.append("The job description states no minimum experience requirement.")
    elif experience.status == "unknown":
        sentences.append(
            f"The role requires at least {_years(experience.required_years)} of experience, but the candidate's "
            "experience could not be determined from the resume; please verify it manually."
        )
    else:
        how = "estimated from the total experience stated in the resume" if experience.method == "estimated_from_total" else "relevant experience"
        if experience.method == "fresher":
            have = "no professional work experience listed (fresher)"
        elif experience.method == "estimated_from_total":
            have = f"about {_years(experience.relevant_years)} of experience ({how})"
        elif not experience.relevant_years:
            have = "no relevant work experience identified"
            if experience.total_years:
                have += f" ({_years(experience.total_years)} of experience in other areas)"
        else:
            have = f"about {_years(experience.relevant_years)} of relevant experience"
            if experience.total_years is not None and experience.total_years != experience.relevant_years:
                have += f" ({_years(experience.total_years)} in total)"
        verdict = "meets" if experience.status == "met" else "does not meet"
        sentences.append(
            f"The role requires at least {_years(experience.required_years)} of experience; the candidate has "
            f"{have}, which {verdict} the requirement."
        )
    if internship_years:
        sentences.append(f"Internship experience of {_years(internship_years)} is listed separately and not counted.")

    # Semantic
    if semantic_score is not None:
        sentences.append(
            f"Overall similarity between the resume and the job description is {semantic_band(semantic_score)} "
            f"({semantic_score:.0f}/100)."
        )

    if missing_components:
        names = {"semantic": "semantic similarity", "skills": "skills matching", "experience": "experience matching"}
        sentences.append(
            "The final score is based only on the available components "
            f"({_list([n for k, n in names.items() if k not in missing_components])}); "
            f"{_list([names[k] for k in missing_components])} could not be calculated."
        )
    return " ".join(sentences)
