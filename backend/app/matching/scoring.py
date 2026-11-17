"""
Hybrid matching engine: one JD vs many resumes -> explainable 0-100 scores.

    Final Score = 0.40 × Semantic + 0.35 × Skills + 0.25 × Experience     (weights configurable)

A. Semantic (0-100)    cosine similarity of all-MiniLM-L6-v2 embeddings (nlp/semantic_matcher.py)
B. Skills (0-100)      Σ weights of matched skills / Σ weights of all JD skills × 100
                       required skill = weight 2, preferred = weight 1 (configurable);
                       "A or B" is one requirement satisfied by either skill
C. Experience (0-100)  min(relevant years / required years, 1) × 100

Missing information is never turned into a silent zero:
- JD states no experience requirement  -> experience score 100 for everyone ("not required")
- candidate's experience is unknown     -> experience score None; the final score uses the
  remaining components with their weights rescaled, and the result is flagged "incomplete"
- JD lists no recognised skills         -> skills score None (same rescaling, flagged)
- semantic model unavailable            -> semantic score None (same rescaling, flagged)

Everything here is deterministic: the same inputs always give the same scores.
"""
import re
from dataclasses import dataclass, field
from datetime import date

from app.config import settings
from app.matching.explanation import build_explanation
from app.nlp.semantic_matcher import cosine_to_score, semantic_matcher
from app.nlp.skill_extractor import expand_implied_skills, extract_skills, is_known_skill, split_alternatives
from app.parser.experience import entry_interval, merge_intervals
from app.parser.sections import split_sections

# Resume sections used for semantic comparison: the professional content only,
# never the name/contact header or personal details.
RESUME_SEMANTIC_SECTIONS = ("summary", "skills", "experience", "internships", "projects", "certifications")
_TITLE_STOPWORDS = {
    "senior", "junior", "lead", "principal", "staff", "associate", "trainee", "intern", "engineer", "developer",
    "i", "ii", "iii", "the", "of", "and", "a", "an", "-", "|", "graduate", "programme", "program",
    "software", "full", "stack", "web", "application", "applications", "specialist", "consultant", "analyst",
}


# --- Inputs -------------------------------------------------------------------------------------------
@dataclass
class JobProfile:
    job_title: str
    description: str
    required_skills: list[str]
    preferred_skills: list[str] = field(default_factory=list)
    minimum_experience: float | None = None  # None = no requirement
    responsibilities: list[str] = field(default_factory=list)

    @classmethod
    def from_model(cls, job) -> "JobProfile":
        return cls(
            job_title=job.job_title,
            description=job.description,
            required_skills=list(job.required_skills or []),
            preferred_skills=list(job.preferred_skills or []),
            minimum_experience=job.minimum_experience,
            responsibilities=list(job.responsibilities or []),
        )

    def skill_parts(self) -> set[str]:
        """Every individual skill named in the JD, lower-cased (alternatives expanded)."""
        return {p.lower() for s in self.required_skills + self.preferred_skills for p in split_alternatives(s)}


@dataclass
class CandidateProfile:
    """The parts of a parsed resume that matching needs (built from a parse result or a DB row)."""

    key: str  # anything that identifies the candidate to the caller (file name, UUID ...)
    name: str | None
    skills: list[str]
    resume_text: str
    experience: list[dict]
    total_experience: float | None
    experience_method: str  # date_ranges | stated_in_resume | fresher | unknown
    internship_experience: float | None = None

    @classmethod
    def from_parsed(cls, key: str, parsed) -> "CandidateProfile":
        return cls(
            key=key,
            name=parsed.name,
            skills=list(parsed.skills),
            resume_text=parsed.text,
            experience=list(parsed.experience),
            total_experience=parsed.total_experience_years,
            experience_method=parsed.experience_method,
            internship_experience=parsed.internship_experience_years,
        )

    @classmethod
    def from_model(cls, candidate) -> "CandidateProfile":
        profile = candidate.profile or {}
        return cls(
            key=str(candidate.id),
            name=candidate.name,
            skills=list(candidate.extracted_skills or []),
            resume_text=candidate.resume_text,
            experience=list(profile.get("experience", [])),
            total_experience=candidate.total_experience,
            experience_method=profile.get("experience_method", "unknown"),
            internship_experience=profile.get("internship_experience_years"),
        )


# --- Outputs ------------------------------------------------------------------------------------------
@dataclass
class SkillMatch:
    score: float | None  # None = the JD has no skills to compare
    matched_required: list[str]
    matched_preferred: list[str]
    missing_required: list[str]
    missing_preferred: list[str]
    additional: list[str]
    satisfied_by: dict[str, str]  # requirement -> the candidate skill that satisfied it
    matched_weight: float
    total_weight: float


@dataclass
class ExperienceMatch:
    score: float | None  # None = candidate experience unknown
    status: str  # met | not_met | not_required | unknown
    required_years: float | None
    relevant_years: float | None
    total_years: float | None
    method: str  # relevant_entries | estimated_from_total | fresher | unknown
    relevant_entries: list[str]


@dataclass
class MatchOutcome:
    candidate_key: str
    candidate_name: str | None
    semantic_score: float | None
    skills_score: float | None
    experience_score: float | None
    final_score: float
    status: str  # complete | incomplete
    matched_skills: list[str]
    missing_skills: list[str]
    additional_skills: list[str]
    relevant_experience: float | None
    explanation: str
    details: dict


# --- B. Skills ------------------------------------------------------------------------------------------
def _mentioned_in_text(skill: str, text: str) -> bool:
    """Whole-word search, used for custom skills a recruiter typed that are not in the dictionary."""
    return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(skill)}(?![A-Za-z0-9])", text or "", re.I))


def _satisfying_skill(requirement: str, candidate_skills: set[str], resume_text: str) -> str | None:
    for part in split_alternatives(requirement):
        if part.lower() in candidate_skills:
            return part
        if not is_known_skill(part) and _mentioned_in_text(part, resume_text):
            return part
    return None


def compute_skill_match(
    required: list[str],
    preferred: list[str],
    candidate_skills: list[str],
    resume_text: str = "",
    required_weight: float | None = None,
    preferred_weight: float | None = None,
) -> SkillMatch:
    """
    Skills Score = (sum of weights of matched skills / sum of weights of all JD skills) × 100

    Example (all required, weight 2 each):
        JD: Python, SQL, FastAPI, Docker, REST APIs     candidate: Python, SQL, REST APIs, Flask
        matched = 3 × 2 = 6, total = 5 × 2 = 10  ->  60.0
    """
    required_weight = settings.REQUIRED_SKILL_WEIGHT if required_weight is None else required_weight
    preferred_weight = settings.PREFERRED_SKILL_WEIGHT if preferred_weight is None else preferred_weight
    have = {s.lower() for s in candidate_skills}

    result = SkillMatch(None, [], [], [], [], [], {}, 0.0, 0.0)
    for requirements, weight, matched, missing in (
        (required, required_weight, result.matched_required, result.missing_required),
        (preferred, preferred_weight, result.matched_preferred, result.missing_preferred),
    ):
        for requirement in requirements:
            result.total_weight += weight
            satisfied_by = _satisfying_skill(requirement, have, resume_text)
            if satisfied_by:
                matched.append(requirement)
                result.matched_weight += weight
                result.satisfied_by[requirement] = satisfied_by
            else:
                missing.append(requirement)

    jd_parts = {p.lower() for s in required + preferred for p in split_alternatives(s)}
    result.additional = [s for s in candidate_skills if s.lower() not in jd_parts]
    if result.total_weight > 0:
        result.score = result.matched_weight / result.total_weight * 100
    return result


# --- C. Experience ----------------------------------------------------------------------------------------
def _title_keywords(title: str | None) -> set[str]:
    words = re.findall(r"[a-z+#.]+", (title or "").lower())
    return {w for w in words if w not in _TITLE_STOPWORDS and len(w) > 1}


def compute_relevant_experience(
    candidate: CandidateProfile, job: JobProfile, today: date
) -> tuple[float | None, str, list[str]]:
    """
    Relevant experience = merged duration of the jobs that are related to the JD.
    A job entry is relevant when ANY of these holds:
      1. its title shares a meaningful word with the JD title ("Data Analyst" ~ "Data Scientist");
      2. it uses the JD's title skill ("Python Developer" -> Python), counting skills implied
         by frameworks (a Django job is Python work);
      3. it shares at least 2 required skills with the JD (or all of them, if the JD lists fewer).
    Internships are not counted (consistent with total experience).
    Returns (years or None, method, headings of the relevant entries).
    """
    if candidate.experience_method == "date_ranges":
        jd_title_words = _title_keywords(job.job_title)
        title_skills = {s.lower() for s in extract_skills(job.job_title or "")}
        required_parts = {p.lower() for s in job.required_skills for p in split_alternatives(s)}
        min_overlap = min(2, len(required_parts)) or 1
        intervals, undated_months, relevant = [], 0, []
        for entry in candidate.experience:
            if entry.get("is_internship"):
                continue
            entry_skills = {s.lower() for s in expand_implied_skills(entry.get("skills", []))}
            title_words = _title_keywords(entry.get("title") or entry.get("heading"))
            is_relevant = (
                bool(title_words & jd_title_words)
                or bool(entry_skills & title_skills)
                or len(entry_skills & required_parts) >= min_overlap
            )
            if not is_relevant:
                continue
            relevant.append(entry.get("heading") or entry.get("title") or "work experience")
            interval = entry_interval(entry, today)
            if interval:
                intervals.append(interval)
            elif entry.get("months"):
                undated_months += entry["months"]
        return round((merge_intervals(intervals) + undated_months) / 12, 1), "relevant_entries", relevant

    if candidate.experience_method == "stated_in_resume" and candidate.total_experience is not None:
        # No dated jobs to inspect: count the stated total only if the resume shows JD skills at all.
        has_jd_skill = bool({s.lower() for s in candidate.skills} & job.skill_parts())
        return (candidate.total_experience if has_jd_skill else 0.0), "estimated_from_total", []

    if candidate.experience_method == "fresher":
        return 0.0, "fresher", []
    return None, "unknown", []


def compute_experience_score(required_years: float | None, relevant_years: float | None) -> tuple[float | None, str]:
    """
    Experience Score = min(relevant / required, 1) × 100
    Example: required 3 -> relevant 4 = 100, relevant 2 = 66.67, relevant 0 = 0.
    """
    if required_years is None:
        return 100.0, "not_required"
    if relevant_years is None:
        return None, "unknown"
    if required_years <= 0:
        return 100.0, "met"
    score = min(relevant_years / required_years, 1.0) * 100
    return score, "met" if relevant_years >= required_years else "not_met"


def compute_experience_match(candidate: CandidateProfile, job: JobProfile, today: date) -> ExperienceMatch:
    relevant, method, entries = compute_relevant_experience(candidate, job, today)
    score, status = compute_experience_score(job.minimum_experience, relevant)
    return ExperienceMatch(score, status, job.minimum_experience, relevant, candidate.total_experience, method, entries)


# --- Final score ------------------------------------------------------------------------------------------
def scoring_weights() -> dict[str, float]:
    """Configured weights, rescaled to sum to 1 if the configuration doesn't."""
    weights = {
        "semantic": settings.WEIGHT_SEMANTIC,
        "skills": settings.WEIGHT_SKILLS,
        "experience": settings.WEIGHT_EXPERIENCE,
    }
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()} if total > 0 else {"semantic": 0.4, "skills": 0.35, "experience": 0.25}


def combine_scores(components: dict[str, float | None], weights: dict[str, float] | None = None) -> tuple[float, dict[str, float]]:
    """
    Weighted average of the AVAILABLE components (each 0-100), rounded to 2 decimals.
    With all three present this is exactly 0.40·S + 0.35·K + 0.25·E. If one is None,
    the others' weights are rescaled so they still sum to 1 (and the result is flagged).
    Returns (final_score, weights_actually_used).
    """
    weights = weights or scoring_weights()
    available = {k: v for k, v in components.items() if v is not None and weights.get(k, 0) > 0}
    total_weight = sum(weights[k] for k in available)
    if total_weight == 0:
        return 0.0, {}
    used = {k: weights[k] / total_weight for k in available}
    final = sum(available[k] * used[k] for k in available)
    return round(min(max(final, 0.0), 100.0), 2), used


# --- Text sent to the semantic model ---------------------------------------------------------------------
def build_resume_semantic_text(resume_text: str) -> str:
    sections = split_sections(resume_text)
    text = "\n".join(sections[key] for key in RESUME_SEMANTIC_SECTIONS if sections.get(key))
    if len(text.split()) < 30:  # no usable headings: fall back to everything except the header
        text = "\n".join(v for k, v in sections.items() if k not in {"header", "personal", "interests", "languages"})
    if len(text.split()) < 30:
        text = resume_text
    # Contact details carry no meaning for matching.
    return re.sub(r"\S+@\S+|https?://\S+|\+?\d[\d\s().-]{8,}\d", " ", text)


def build_job_semantic_text(job: JobProfile) -> str:
    from app.nlp.jd_analyzer import JD_HEADING_LOOKUP

    sections = split_sections(job.description, JD_HEADING_LOOKUP)
    body = "\n".join(v for k, v in sections.items() if k != "company" and v)  # skip About us / Benefits
    parts = [job.job_title, body]
    # Include the recruiter's edited requirements, so edits affect semantic matching too.
    if job.required_skills:
        parts.append("Required skills: " + ", ".join(job.required_skills))
    if job.preferred_skills:
        parts.append("Preferred skills: " + ", ".join(job.preferred_skills))
    return "\n".join(p for p in parts if p)


# --- Orchestration ----------------------------------------------------------------------------------------
def score_candidates(job: JobProfile, candidates: list[CandidateProfile], today: date | None = None) -> list[MatchOutcome]:
    """Score every candidate against one job. Semantic embeddings are computed in one batch."""
    today = today or date.today()
    weights = scoring_weights()
    notes: list[str] = []

    try:
        cosines = semantic_matcher.similarities(
            build_job_semantic_text(job), [build_resume_semantic_text(c.resume_text) for c in candidates]
        )
    except RuntimeError as exc:
        cosines = [None] * len(candidates)
        notes.append(f"Semantic similarity unavailable: {exc}")

    outcomes = []
    for candidate, cosine in zip(candidates, cosines):
        semantic = cosine_to_score(cosine) if cosine is not None else None
        skills = compute_skill_match(job.required_skills, job.preferred_skills, candidate.skills, candidate.resume_text)
        experience = compute_experience_match(candidate, job, today)
        final, used_weights = combine_scores(
            {"semantic": semantic, "skills": skills.score, "experience": experience.score}, weights
        )
        missing_components = [k for k, v in (("semantic", semantic), ("skills", skills.score),
                                             ("experience", experience.score)) if v is None]
        status = "incomplete" if missing_components else "complete"

        explanation = build_explanation(
            job_title=job.job_title,
            final_score=final,
            semantic_score=semantic,
            skills=skills,
            experience=experience,
            internship_years=candidate.internship_experience,
            missing_components=missing_components,
        )
        outcomes.append(
            MatchOutcome(
                candidate_key=candidate.key,
                candidate_name=candidate.name,
                semantic_score=semantic,
                skills_score=skills.score,
                experience_score=experience.score,
                final_score=final,
                status=status,
                matched_skills=skills.matched_required + skills.matched_preferred,
                missing_skills=skills.missing_required + skills.missing_preferred,
                additional_skills=skills.additional,
                relevant_experience=experience.relevant_years,
                explanation=explanation,
                details={
                    "weights_configured": weights,
                    "weights_used": used_weights,
                    "missing_components": missing_components,
                    "semantic": {
                        "model": semantic_matcher.model_name,
                        "cosine_similarity": cosine,
                        "calibration": {"floor": settings.SEMANTIC_COSINE_FLOOR, "ceil": settings.SEMANTIC_COSINE_CEIL},
                    },
                    "skills": {
                        "matched_required": skills.matched_required,
                        "matched_preferred": skills.matched_preferred,
                        "missing_required": skills.missing_required,
                        "missing_preferred": skills.missing_preferred,
                        "satisfied_by": skills.satisfied_by,
                        "matched_weight": skills.matched_weight,
                        "total_weight": skills.total_weight,
                        "required_weight": settings.REQUIRED_SKILL_WEIGHT,
                        "preferred_weight": settings.PREFERRED_SKILL_WEIGHT,
                    },
                    "experience": {
                        "status": experience.status,
                        "required_years": experience.required_years,
                        "relevant_years": experience.relevant_years,
                        "total_years": experience.total_years,
                        "internship_years": candidate.internship_experience,
                        "method": experience.method,
                        "relevant_entries": experience.relevant_entries,
                    },
                    "notes": notes,
                },
            )
        )
    return outcomes
