"""Tests for skill, experience and final scoring, explanations and end-to-end matching."""
from datetime import date
from pathlib import Path

import pytest

from app.matching import scoring
from app.matching.scoring import (
    CandidateProfile,
    JobProfile,
    combine_scores,
    compute_experience_match,
    compute_experience_score,
    compute_skill_match,
    score_candidates,
)
from app.nlp.jd_analyzer import analyze_job_description
from app.nlp.skill_extractor import expand_implied_skills
from app.parser.resume_parser import parse_resume

TODAY = date(2026, 11, 1)
ROOT = Path(__file__).resolve().parents[2]


def candidate(skills=(), experience=(), total=None, method="date_ranges", text="", internship=None, key="c1"):
    return CandidateProfile(key=key, name="Test Person", skills=list(skills), resume_text=text,
                            experience=list(experience), total_experience=total, experience_method=method,
                            internship_experience=internship)


def job(required=(), preferred=(), minimum=None, title="Python Developer", description="Python developer role."):
    return JobProfile(job_title=title, description=description, required_skills=list(required),
                      preferred_skills=list(preferred), minimum_experience=minimum)


# --- B. Skills -------------------------------------------------------------------------------------------------
def test_assignment_skill_example():
    result = compute_skill_match(
        ["Python", "SQL", "FastAPI", "Docker", "REST APIs"], [], ["Python", "SQL", "REST APIs", "Flask"]
    )
    assert result.matched_required == ["Python", "SQL", "REST APIs"]
    assert result.missing_required == ["FastAPI", "Docker"]
    assert result.additional == ["Flask"]
    assert result.score == pytest.approx(60.0)  # 3×2 / 5×2


def test_required_skills_weigh_double_preferred():
    # required: Python (2), Docker (2); preferred: AWS (1), Redis (1) -> total 6
    result = compute_skill_match(["Python", "Docker"], ["AWS", "Redis"], ["Python", "AWS"])
    assert result.matched_weight == 3 and result.total_weight == 6
    assert result.score == pytest.approx(50.0)
    assert result.matched_preferred == ["AWS"] and result.missing_preferred == ["Redis"]


def test_weights_are_configurable():
    result = compute_skill_match(["Python"], ["AWS"], ["AWS"], required_weight=3, preferred_weight=1)
    assert result.score == pytest.approx(25.0)


def test_alternative_group_satisfied_by_either_skill():
    result = compute_skill_match(["FastAPI or Django", "SQL"], [], ["Django", "SQL"])
    assert result.score == 100.0
    assert result.satisfied_by["FastAPI or Django"] == "Django"


def test_custom_skill_found_in_resume_text():
    result = compute_skill_match(["Kafka Streams"], [], [], resume_text="Built pipelines with Kafka Streams.")
    assert result.score == 100.0


def test_no_jd_skills_gives_none_not_zero():
    assert compute_skill_match([], [], ["Python"]).score is None


def test_candidate_with_no_matching_skills_scores_zero():
    assert compute_skill_match(["Java", "Spring Boot"], [], ["Python", "Flask"]).score == 0.0


def test_skill_matching_does_not_use_implications():
    # A Django resume does NOT get credit for "Python" unless Python is written in it.
    assert compute_skill_match(["Python"], [], ["Django"]).score == 0.0
    assert "Python" in expand_implied_skills(["Django"])  # implications exist, but only for relevance


# --- C. Experience ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "required, relevant, score, status",
    [
        (3, 4, 100.0, "met"),
        (3, 3, 100.0, "met"),
        (3, 2, 66.67, "not_met"),
        (3, 0, 0.0, "not_met"),
        (0, 0, 100.0, "met"),
        (None, 0, 100.0, "not_required"),
        (None, None, 100.0, "not_required"),
        (3, None, None, "unknown"),
    ],
)
def test_experience_score_formula(required, relevant, score, status):
    result_score, result_status = compute_experience_score(required, relevant)
    assert result_status == status
    assert result_score == (None if score is None else pytest.approx(score, abs=0.01))


def entry(title, start, end, skills, internship=False):
    return {"heading": title, "title": title, "start": start, "end": end, "skills": skills, "is_internship": internship}


def test_relevant_vs_total_experience():
    person = candidate(total=6.0, experience=[
        entry("Python Developer", "2023-01", "2024-12", ["Python", "FastAPI"]),  # relevant: 24 months
        entry("Sales Executive", "2019-01", "2022-12", ["Excel"]),  # not relevant: 48 months
    ])
    result = compute_experience_match(person, job(["Python", "FastAPI"], minimum=3), TODAY)
    assert result.relevant_years == 2.0 and result.total_years == 6.0
    assert result.score == pytest.approx(66.67, abs=0.01) and result.status == "not_met"


def test_overlapping_relevant_jobs_are_merged():
    person = candidate(experience=[
        entry("Backend Developer", "2020-01", "2021-12", ["Python", "SQL"]),
        entry("Freelance Developer", "2021-01", "2022-12", ["Python", "SQL"]),
    ])
    assert compute_experience_match(person, job(["Python", "SQL"]), TODAY).relevant_years == 3.0


def test_framework_implies_title_skill_for_relevance():
    person = candidate(experience=[entry("Backend Developer", "2020-01", "2021-12", ["Django"])])
    result = compute_experience_match(person, job(["Python", "SQL"], minimum=2, title="Python Developer"), TODAY)
    assert result.relevant_years == 2.0


def test_one_generic_shared_skill_is_not_enough():
    person = candidate(experience=[entry("Backend Developer", "2020-01", "2023-12", ["Flask", "MySQL"])])
    java = job(["Java", "Spring Boot", "MySQL"], minimum=3, title="Java Developer")
    assert compute_experience_match(person, java, TODAY).relevant_years == 0.0


def test_internships_not_counted_as_relevant_experience():
    person = candidate(experience=[entry("ML Intern", "2024-01", "2024-06", ["Python"], internship=True)],
                       method="fresher", total=0.0, internship=0.5)
    result = compute_experience_match(person, job(["Python"], minimum=1), TODAY)
    assert result.relevant_years == 0.0 and result.score == 0.0


def test_unknown_experience_is_flagged_not_zero():
    result = compute_experience_match(candidate(method="unknown"), job(["Python"], minimum=3), TODAY)
    assert result.score is None and result.status == "unknown"


def test_stated_experience_estimate():
    person = candidate(skills=["Python"], total=4.0, method="stated_in_resume")
    result = compute_experience_match(person, job(["Python"], minimum=3), TODAY)
    assert result.relevant_years == 4.0 and result.method == "estimated_from_total"
    unrelated = candidate(skills=["AutoCAD"], total=4.0, method="stated_in_resume")
    assert compute_experience_match(unrelated, job(["Python"], minimum=3), TODAY).relevant_years == 0.0


# --- Final score ---------------------------------------------------------------------------------------------------
def test_final_formula():
    final, used = combine_scores({"semantic": 85, "skills": 90, "experience": 100})
    assert final == pytest.approx(0.40 * 85 + 0.35 * 90 + 0.25 * 100)  # 90.5
    assert used == pytest.approx({"semantic": 0.40, "skills": 0.35, "experience": 0.25})


def test_missing_component_rescales_remaining_weights():
    final, used = combine_scores({"semantic": 80, "skills": 60, "experience": None})
    assert used == pytest.approx({"semantic": 0.40 / 0.75, "skills": 0.35 / 0.75})
    assert final == pytest.approx(round((0.40 * 80 + 0.35 * 60) / 0.75, 2))


def test_final_score_rounded_and_bounded():
    # 0.40×33.333 + 0.35×66.666 + 0.25×12.345 = 13.3332 + 23.3331 + 3.08625 = 39.75255 -> 39.75
    assert combine_scores({"semantic": 33.333, "skills": 66.666, "experience": 12.345})[0] == 39.75
    assert combine_scores({"semantic": None, "skills": None, "experience": None})[0] == 0.0
    assert combine_scores({"semantic": 100, "skills": 100, "experience": 100})[0] == 100.0


def test_weights_from_settings_are_normalised(monkeypatch):
    monkeypatch.setattr(scoring.settings, "WEIGHT_SEMANTIC", 2)
    monkeypatch.setattr(scoring.settings, "WEIGHT_SKILLS", 1)
    monkeypatch.setattr(scoring.settings, "WEIGHT_EXPERIENCE", 1)
    assert scoring.scoring_weights() == {"semantic": 0.5, "skills": 0.25, "experience": 0.25}


# --- Orchestration with a fake semantic model (fast, deterministic) ---------------------------------------------------
@pytest.fixture
def fake_semantic(monkeypatch):
    monkeypatch.setattr(scoring.semantic_matcher, "similarities", lambda jd, texts: [0.60] * len(texts))


def test_score_candidates_full_breakdown(fake_semantic):
    person = candidate(skills=["Python", "SQL", "Flask"], text="Python SQL Flask developer",
                       experience=[entry("Python Developer", "2021-01", "2024-12", ["Python", "SQL"])])
    [outcome] = score_candidates(job(["Python", "SQL", "Docker"], ["AWS"], minimum=3), [person], today=TODAY)
    assert outcome.semantic_score == pytest.approx(75.0)  # cosine 0.60 -> (0.60-0.15)/0.60
    assert outcome.skills_score == pytest.approx(4 / 7 * 100)
    assert outcome.experience_score == 100.0
    assert outcome.final_score == round(0.40 * 75 + 0.35 * (400 / 7) + 0.25 * 100, 2)
    assert outcome.matched_skills == ["Python", "SQL"] and outcome.missing_skills == ["Docker", "AWS"]
    assert outcome.additional_skills == ["Flask"] and outcome.status == "complete"
    assert outcome.details["semantic"]["cosine_similarity"] == 0.60
    assert outcome.details["experience"]["relevant_years"] == 4.0


def test_unknown_experience_marks_result_incomplete(fake_semantic):
    [outcome] = score_candidates(job(["Python"], minimum=3), [candidate(skills=["Python"], method="unknown")], today=TODAY)
    assert outcome.experience_score is None and outcome.status == "incomplete"
    assert outcome.details["missing_components"] == ["experience"]
    assert "could not be determined" in outcome.explanation and "please verify" in outcome.explanation


def test_semantic_model_failure_does_not_break_scoring(monkeypatch):
    def unavailable(jd, texts):
        raise RuntimeError("Could not load model 'x'")

    monkeypatch.setattr(scoring.semantic_matcher, "similarities", unavailable)
    [outcome] = score_candidates(job(["Python"]), [candidate(skills=["Python"])], today=TODAY)
    assert outcome.semantic_score is None and outcome.status == "incomplete"
    assert outcome.final_score == 100.0  # skills 100, experience not required 100
    assert "Semantic similarity unavailable" in outcome.details["notes"][0]


def test_identical_candidates_get_identical_scores(fake_semantic):
    twins = [candidate(skills=["Python"], key="a"), candidate(skills=["Python"], key="b")]
    first, second = score_candidates(job(["Python", "SQL"]), twins, today=TODAY)
    assert first.final_score == second.final_score


def test_explanation_states_only_facts(fake_semantic):
    person = candidate(skills=["Python", "SQL"], experience=[entry("Python Developer", "2025-01", "2025-12", ["Python"])])
    [outcome] = score_candidates(job(["Python", "SQL", "Docker", "FastAPI"], minimum=3), [person], today=TODAY)
    text = outcome.explanation
    assert "2 of 4 required skills were identified in the resume: Python and SQL." in text
    assert "Required skills not identified: Docker and FastAPI." in text
    assert "about 1 year of relevant experience, which does not meet the requirement" in text
    assert "meets the requirement" not in text.replace("does not meet the requirement", "")


# --- End to end with the real model and the sample files ------------------------------------------------------------
@pytest.fixture(scope="module")
def sample_candidates():
    files = sorted(p for p in (ROOT / "sample_resumes").glob("*") if p.suffix in {".pdf", ".docx"})
    return [CandidateProfile.from_parsed(p.stem, parse_resume(p.read_bytes(), p.suffix, today=TODAY)) for p in files]


def score_sample_jd(name: str, sample_candidates):
    text = (ROOT / "sample_jds" / name).read_text(encoding="utf-8")
    analysis = analyze_job_description(text)
    profile = JobProfile(analysis.job_title, text, analysis.required_skills, analysis.preferred_skills,
                         analysis.minimum_experience, analysis.responsibilities)
    outcomes = score_candidates(profile, sample_candidates, today=TODAY)
    return sorted(outcomes, key=lambda o: -o.final_score)


def test_python_jd_ranking_is_sensible(sample_candidates):
    ranked = [o.candidate_key for o in score_sample_jd("01_python_developer.txt", sample_candidates)]
    assert set(ranked[:2]) == {"01_arjun_mehta_python_backend", "02_priya_nair_python_fastapi"}
    assert set(ranked[-3:]) == {"03_karthik_iyer_java", "06_ananya_reddy_fullstack", "10_fatima_sheikh_embedded"}


def test_java_jd_ranks_java_developer_first(sample_candidates):
    ranked = score_sample_jd("06_java_developer.txt", sample_candidates)
    assert ranked[0].candidate_key == "03_karthik_iyer_java"
    assert ranked[0].final_score - ranked[1].final_score > 30  # clear winner


def test_data_science_jd_ranks_data_scientist_first(sample_candidates):
    ranked = score_sample_jd("03_data_scientist.txt", sample_candidates)
    assert ranked[0].candidate_key == "04_sneha_kulkarni_data_scientist"


def test_all_sample_scores_within_bounds(sample_candidates):
    for outcome in score_sample_jd("02_senior_backend_engineer.txt", sample_candidates):
        for value in (outcome.semantic_score, outcome.skills_score, outcome.experience_score, outcome.final_score):
            assert value is None or 0 <= value <= 100
        assert outcome.explanation


def test_scores_are_deterministic(sample_candidates):
    first = [o.final_score for o in score_sample_jd("01_python_developer.txt", sample_candidates)]
    second = [o.final_score for o in score_sample_jd("01_python_developer.txt", sample_candidates)]
    assert first == second
