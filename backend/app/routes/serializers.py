"""Convert database rows into API response schemas (keeps the route functions short)."""
from app.matching.ranking import RankedCandidate
from app.models import AnalysisHistory, Candidate, MatchResult
from app.schemas import (
    AnalysisSummary,
    CandidateDetail,
    CandidateMatchSummary,
    MatchDetail,
    RankedCandidateOut,
    round2,
)


def analysis_summary(analysis: AnalysisHistory) -> AnalysisSummary:
    return AnalysisSummary(
        id=analysis.id,
        job_id=analysis.job_id,
        job_title=analysis.job.job_title,
        total_resumes=analysis.total_resumes,
        average_score=round2(analysis.average_score),
        created_at=analysis.created_at,
    )


def ranked_candidate(item: RankedCandidate) -> RankedCandidateOut:
    match, candidate = item.match, item.candidate
    return RankedCandidateOut(
        rank=item.rank,
        candidate_id=candidate.id,
        match_id=match.id,
        name=candidate.name,
        email=candidate.email,
        phone=candidate.phone,
        total_experience=candidate.total_experience,
        relevant_experience=match.relevant_experience,
        final_score=round2(match.final_score),
        semantic_score=round2(match.semantic_score),
        skills_score=round2(match.skills_score),
        experience_score=round2(match.experience_score),
        matched_skills=match.matched_skills,
        missing_skills=match.missing_skills,
        additional_skills=match.additional_skills,
        status=(match.details or {}).get("status", "complete"),
        resume_filename=candidate.resume_filename,
    )


def candidate_detail(candidate: Candidate, history: list[tuple[MatchResult, str]] | None = None) -> CandidateDetail:
    profile = candidate.profile or {}
    return CandidateDetail(
        id=candidate.id,
        name=candidate.name,
        email=candidate.email,
        phone=candidate.phone,
        education=profile.get("education_entries") or ([candidate.education] if candidate.education else []),
        degree_levels=profile.get("degree_levels", []),
        total_experience=candidate.total_experience,
        internship_experience=profile.get("internship_experience_years"),
        experience_method=profile.get("experience_method", "unknown"),
        is_fresher=bool(profile.get("is_fresher")),
        skills=candidate.extracted_skills,
        skills_by_category=profile.get("skills_by_category", {}),
        certifications=candidate.certifications,
        projects=profile.get("projects", []),
        experience=profile.get("experience", []),
        links=profile.get("links", []),
        summary=profile.get("summary"),
        resume_filename=candidate.resume_filename,
        parse_warnings=profile.get("parse_warnings", []),
        created_at=candidate.created_at,
        matches=[
            CandidateMatchSummary(
                analysis_id=m.analysis_id, job_id=m.job_id, job_title=title,
                final_score=round2(m.final_score), created_at=m.created_at,
            )
            for m, title in (history or [])
        ],
    )


def match_detail(item: RankedCandidate, total_candidates: int) -> MatchDetail:
    match = item.match
    details = match.details or {}
    skills = details.get("skills", {})
    experience = details.get("experience", {})
    return MatchDetail(
        match_id=match.id,
        rank=item.rank,
        total_candidates=total_candidates,
        final_score=round2(match.final_score),
        semantic_score=round2(match.semantic_score),
        skills_score=round2(match.skills_score),
        experience_score=round2(match.experience_score),
        status=details.get("status", "complete"),
        cosine_similarity=details.get("semantic", {}).get("cosine_similarity"),
        weights_used=details.get("weights_used", {}),
        missing_components=details.get("missing_components", []),
        matched_required_skills=skills.get("matched_required", []),
        matched_preferred_skills=skills.get("matched_preferred", []),
        missing_required_skills=skills.get("missing_required", []),
        missing_preferred_skills=skills.get("missing_preferred", []),
        additional_skills=match.additional_skills,
        satisfied_by=skills.get("satisfied_by", {}),
        required_experience=experience.get("required_years"),
        relevant_experience=match.relevant_experience,
        experience_status=experience.get("status", "unknown"),
        experience_method=experience.get("method", "unknown"),
        relevant_experience_entries=experience.get("relevant_entries", []),
        explanation=match.explanation,
    )
