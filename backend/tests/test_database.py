"""Phase 2 tests: Supabase connection, schema, constraints and relationships.

All rows are created inside a rolled-back transaction (see conftest.py).
The candidate data is fictional.
"""
import uuid

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.database import engine
from app.models import AnalysisHistory, Candidate, Job, MatchResult

EXPECTED_TABLES = {"jobs", "candidates", "analysis_history", "match_results"}


def make_job(**overrides) -> Job:
    values = dict(
        job_title="Python Developer",
        description="Python developer with 3+ years of FastAPI, SQL and Docker.",
        required_skills=["Python", "FastAPI", "SQL"],
        preferred_skills=["Docker"],
        minimum_experience=3.0,
        education_requirements="Bachelor's degree in Computer Science or equivalent",
    )
    values.update(overrides)
    return Job(**values)


def make_candidate(**overrides) -> Candidate:
    values = dict(
        name="Asha Verma",
        email="asha.verma@example.com",
        extracted_skills=["Python", "SQL", "Flask"],
        resume_filename="asha_verma.pdf",
        file_hash=uuid.uuid4().hex * 2,
        resume_text="Asha Verma - Python developer with 4 years of experience.",
    )
    values.update(overrides)
    return Candidate(**values)


def make_analysis_with_match(session, final_score: float = 72.5):
    job, candidate = make_job(), make_candidate()
    analysis = AnalysisHistory(job=job, total_resumes=1, average_score=final_score)
    match = MatchResult(
        analysis=analysis,
        job=job,
        candidate=candidate,
        semantic_score=70.0,
        skills_score=66.67,
        experience_score=100.0,
        final_score=final_score,
        relevant_experience=4.0,
        matched_skills=["Python", "SQL"],
        missing_skills=["FastAPI", "Docker"],
        explanation="Test explanation.",
        details={"weights": {"semantic": 0.4, "skills": 0.35, "experience": 0.25}},
    )
    session.add(match)
    session.flush()
    return job, candidate, analysis, match


# --- Connection and schema ---------------------------------------------------------
def test_database_connection(database_available):
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar() == 1


def test_all_tables_exist(database_available):
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())


def test_row_level_security_enabled_on_all_tables(database_available):
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT relname, relrowsecurity FROM pg_class WHERE relname = ANY(:names)"),
            {"names": list(EXPECTED_TABLES)},
        ).all()
    assert dict(rows) == {name: True for name in EXPECTED_TABLES}


def test_ids_are_uuids_and_skills_are_jsonb(database_available):
    columns = {c["name"]: str(c["type"]).upper() for c in inspect(engine).get_columns("candidates")}
    assert columns["id"] == "UUID"
    assert columns["extracted_skills"] == "JSONB"


# --- Inserting and reading ---------------------------------------------------------
def test_insert_and_read_back_full_analysis(db_session):
    job, candidate, analysis, match = make_analysis_with_match(db_session)
    db_session.commit()
    db_session.expire_all()  # force a real re-read from PostgreSQL

    stored = db_session.get(MatchResult, match.id)
    assert isinstance(stored.id, uuid.UUID)
    assert stored.final_score == 72.5
    assert stored.matched_skills == ["Python", "SQL"]
    assert stored.details["weights"]["skills"] == 0.35
    assert stored.candidate.name == "Asha Verma"
    assert stored.job.required_skills == ["Python", "FastAPI", "SQL"]
    assert stored.analysis.total_resumes == 1
    assert stored.created_at.tzinfo is not None  # timestamps are timezone-aware


def test_missing_values_are_stored_as_null_not_zero(db_session):
    candidate = make_candidate(name=None, email=None, phone=None, total_experience=None)
    job = make_job(minimum_experience=None)
    db_session.add_all([candidate, job])
    db_session.flush()
    db_session.expire_all()
    assert db_session.get(Candidate, candidate.id).total_experience is None
    assert db_session.get(Candidate, candidate.id).name is None
    assert db_session.get(Job, job.id).minimum_experience is None


def test_json_lists_default_to_empty(db_session):
    job = Job(job_title="Analyst", description="Data analysis role.")
    db_session.add(job)
    db_session.flush()
    db_session.expire_all()
    stored = db_session.get(Job, job.id)
    assert stored.required_skills == [] and stored.keywords == []


def test_ranking_query_orders_by_final_score(db_session):
    job = make_job()
    analysis = AnalysisHistory(job=job, total_resumes=3)
    for name, score in [("Low", 40.0), ("High", 91.5), ("Mid", 76.8)]:
        db_session.add(
            MatchResult(
                analysis=analysis, job=job, candidate=make_candidate(name=name),
                final_score=score, explanation="-",
            )
        )
    db_session.flush()
    ranked = db_session.scalars(
        select(MatchResult).where(MatchResult.analysis_id == analysis.id).order_by(MatchResult.final_score.desc())
    ).all()
    assert [m.candidate.name for m in ranked] == ["High", "Mid", "Low"]


# --- Constraints ---------------------------------------------------------------------
def test_duplicate_candidate_in_same_analysis_is_rejected(db_session):
    job, candidate, analysis, _ = make_analysis_with_match(db_session)
    db_session.add(MatchResult(analysis=analysis, job=job, candidate=candidate, final_score=50.0, explanation="dup"))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_same_candidate_allowed_in_different_analyses(db_session):
    job, candidate, _, _ = make_analysis_with_match(db_session)
    second_analysis = AnalysisHistory(job=job, total_resumes=1)
    db_session.add(MatchResult(analysis=second_analysis, job=job, candidate=candidate, final_score=60.0, explanation="-"))
    db_session.flush()  # no error


@pytest.mark.parametrize("bad_score", [-1.0, 100.01, 250.0])
def test_scores_outside_0_to_100_are_rejected(db_session, bad_score):
    job, candidate = make_job(), make_candidate()
    analysis = AnalysisHistory(job=job, total_resumes=1)
    db_session.add(MatchResult(analysis=analysis, job=job, candidate=candidate, final_score=bad_score, explanation="-"))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_negative_experience_is_rejected(db_session):
    db_session.add(make_job(minimum_experience=-2))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_match_result_requires_existing_job(db_session):
    _, candidate, analysis, _ = make_analysis_with_match(db_session)
    db_session.add(
        MatchResult(analysis_id=analysis.id, job_id=uuid.uuid4(), candidate_id=candidate.id, final_score=10, explanation="-")
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


# --- Cascading deletes ---------------------------------------------------------------
def test_deleting_job_removes_its_analyses_and_results_but_keeps_candidates(db_session):
    job, candidate, analysis, match = make_analysis_with_match(db_session)
    ids = (job.id, candidate.id, analysis.id, match.id)
    db_session.delete(job)
    db_session.flush()
    db_session.expire_all()

    assert db_session.get(Job, ids[0]) is None
    assert db_session.get(AnalysisHistory, ids[2]) is None
    assert db_session.get(MatchResult, ids[3]) is None
    assert db_session.get(Candidate, ids[1]) is not None


def test_deleting_candidate_removes_its_match_results(db_session):
    _, candidate, analysis, match = make_analysis_with_match(db_session)
    match_id, analysis_id = match.id, analysis.id
    db_session.delete(candidate)
    db_session.flush()
    db_session.expire_all()
    assert db_session.get(MatchResult, match_id) is None
    assert db_session.get(AnalysisHistory, analysis_id) is not None
