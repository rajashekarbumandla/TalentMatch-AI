"""
Phase 6: saving analyses to Supabase and ranking candidates with SQL.

Every test runs inside a rolled-back transaction (see conftest.py), so nothing is
left in the database. Candidate data is the synthetic sample set.
"""
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.matching import scoring
from app.matching.ranking import RankingFilters, SortField, get_ranked_candidate, rank_candidates
from app.matching.scoring import CandidateProfile, JobProfile, score_candidates
from app.models import AnalysisHistory, Candidate, MatchResult
from app.parser.resume_parser import parse_resume
from app.schemas import JobCreate
from app.services import analysis_service, candidate_service, job_service
from app.services.analysis_service import AnalysisError, run_analysis
from app.utils.file_validator import validate_resume_file

TODAY = date(2026, 11, 1)
ROOT = Path(__file__).resolve().parents[2]
PYTHON_JD = (ROOT / "sample_jds" / "01_python_developer.txt").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parsed_samples():
    """Parse the 12 sample resumes once for the whole module."""
    samples = []
    for path in sorted(p for p in (ROOT / "sample_resumes").glob("*") if p.suffix in {".pdf", ".docx"}):
        validated = validate_resume_file(path.name, path.read_bytes())
        samples.append((validated, parse_resume(validated.content, validated.extension, today=TODAY)))
    return samples


@pytest.fixture
def python_job(db_session, hr_user):
    return job_service.create_job(db_session, JobCreate(
        job_title="Python Developer", description=PYTHON_JD,
        required_skills=["Python", "FastAPI", "SQL", "REST APIs", "Machine Learning", "Docker"],
        minimum_experience=3,
    ), owner_id=hr_user.id)


@pytest.fixture
def stored_candidates(db_session, parsed_samples, hr_user):
    candidates = [candidate_service.build_candidate(parsed, v.filename, v.sha256, owner_id=hr_user.id) for v, parsed in parsed_samples]
    db_session.add_all(candidates)
    db_session.commit()
    return candidates


@pytest.fixture
def analysis(db_session, python_job, stored_candidates):
    return run_analysis(db_session, python_job.id, [c.id for c in stored_candidates], today=TODAY, owner_id=python_job.owner_id)


# --- Persistence -----------------------------------------------------------------------------------------------
def test_analysis_and_all_results_are_saved(db_session, analysis, stored_candidates):
    db_session.expire_all()
    saved = db_session.get(AnalysisHistory, analysis.analysis.id)
    assert saved.total_resumes == 12 and len(saved.match_results) == 12
    finals = [m.final_score for m in saved.match_results]
    assert saved.average_score == pytest.approx(round(sum(finals) / 12, 2))
    for result in saved.match_results:
        assert 0 <= result.final_score <= 100
        assert result.explanation and result.details["weights_used"]
        assert result.details["status"] in {"complete", "incomplete"}


def test_component_scores_stored_unrounded(db_session, analysis):
    db_session.expire_all()
    semantic_scores = [m.semantic_score for m in db_session.get(AnalysisHistory, analysis.analysis.id).match_results]
    assert any(round(s, 2) != s for s in semantic_scores)  # raw floats, not display values


def test_scores_from_database_equal_scores_from_fresh_parse(db_session, analysis, parsed_samples):
    """Re-scoring from stored candidate rows must give exactly the same result as scoring the parsed files."""
    job = JobProfile.from_model(analysis.analysis.job)
    fresh = score_candidates(job, [CandidateProfile.from_parsed(v.sha256, p) for v, p in parsed_samples], today=TODAY)
    fresh_by_hash = {o.candidate_key: o.final_score for o in fresh}
    for result in analysis.results:
        candidate = db_session.get(Candidate, result.candidate_id)
        assert result.final_score == fresh_by_hash[candidate.file_hash], candidate.resume_filename


def test_rerunning_creates_a_separate_analysis(db_session, python_job, stored_candidates, analysis):
    second = run_analysis(db_session, python_job.id, [c.id for c in stored_candidates[:3]], today=TODAY, owner_id=python_job.owner_id)
    assert second.analysis.id != analysis.analysis.id
    history = analysis_service.list_analyses(db_session, owner_id=python_job.owner_id, job_id=python_job.id)
    assert {a.id for a in history} == {analysis.analysis.id, second.analysis.id}
    assert analysis_service.latest_analysis_for_job(db_session, python_job.id).total_resumes in {3, 12}
    # The first analysis is untouched.
    assert len(db_session.get(AnalysisHistory, analysis.analysis.id).match_results) == 12


def test_duplicate_ids_and_duplicate_files_analysed_once(db_session, python_job, stored_candidates, parsed_samples):
    validated, parsed = parsed_samples[0]
    same_file_again = candidate_service.create_candidate(db_session, parsed, "copy_of_" + validated.filename, validated.sha256, owner_id=python_job.owner_id)
    first = stored_candidates[0]
    run = run_analysis(db_session, python_job.id, [first.id, first.id, same_file_again.id], today=TODAY, owner_id=python_job.owner_id)
    assert run.analysis.total_resumes == 1
    assert run.skipped_duplicates == ["copy_of_" + validated.filename]


def test_invalid_analysis_requests(db_session, python_job, stored_candidates):
    with pytest.raises(AnalysisError, match="Job not found"):
        run_analysis(db_session, uuid.uuid4(), [stored_candidates[0].id], owner_id=python_job.owner_id)
    with pytest.raises(AnalysisError, match="at least one resume"):
        run_analysis(db_session, python_job.id, [], owner_id=python_job.owner_id)
    with pytest.raises(AnalysisError, match="None of the selected resumes"):
        run_analysis(db_session, python_job.id, [uuid.uuid4()], owner_id=python_job.owner_id)
    partly = run_analysis(db_session, python_job.id, [stored_candidates[0].id, (missing := uuid.uuid4())], today=TODAY, owner_id=python_job.owner_id)
    assert partly.missing_candidate_ids == [missing]


def test_failed_save_leaves_no_partial_analysis(db_session, python_job, stored_candidates, monkeypatch):
    """If any result can't be stored, the whole analysis is rolled back (all or nothing)."""
    real = scoring.score_candidates

    def corrupt_second_result(*args, **kwargs):
        outcomes = real(*args, **kwargs)
        outcomes[1].final_score = 150.0  # violates the 0-100 CHECK constraint
        return outcomes

    monkeypatch.setattr(analysis_service, "score_candidates", corrupt_second_result)
    # Compare with counts taken BEFORE (the database may already contain real data).
    analyses_before = db_session.scalar(select(func.count()).select_from(AnalysisHistory))
    results_before = db_session.scalar(select(func.count()).select_from(MatchResult))
    with pytest.raises(IntegrityError):
        run_analysis(db_session, python_job.id, [c.id for c in stored_candidates[:3]], today=TODAY, owner_id=python_job.owner_id)
    assert db_session.scalar(select(func.count()).select_from(AnalysisHistory)) == analyses_before
    assert db_session.scalar(select(func.count()).select_from(MatchResult)) == results_before


# --- Ranking ------------------------------------------------------------------------------------------------------
def names(page):
    return [item.candidate.name for item in page.items]


def test_default_ranking_highest_score_first(db_session, analysis):
    page = rank_candidates(db_session, analysis.analysis.id)
    scores = [item.match.final_score for item in page.items]
    assert scores == sorted(scores, reverse=True)
    assert [item.rank for item in page.items][:2] == [1, 2] and page.filtered_count == 12
    assert set(names(page)[:2]) == {"Priya Nair", "Arjun Mehta"}
    assert names(page)[-1] == "Fatima Sheikh"


def test_ranking_list_does_not_download_resume_text(db_session, analysis):
    from sqlalchemy import inspect as sa_inspect

    db_session.expunge_all()  # start from an empty identity map so nothing is pre-loaded
    page = rank_candidates(db_session, analysis.analysis.id, RankingFilters(top=3))
    assert "resume_text" in sa_inspect(page.items[0].candidate).unloaded
    detail = get_ranked_candidate(db_session, analysis.analysis.id, page.items[0].candidate.id)
    assert detail.candidate.resume_text  # still available when needed (loads on access)


def test_top_n(db_session, analysis):
    top5 = rank_candidates(db_session, analysis.analysis.id, RankingFilters(top=5))
    assert len(top5.items) == 5 and top5.filtered_count == 5
    assert max(item.rank for item in top5.items) == 5
    assert len(rank_candidates(db_session, analysis.analysis.id, RankingFilters(top=10)).items) == 10


def test_search_by_name_or_email_case_insensitive(db_session, analysis):
    assert names(rank_candidates(db_session, analysis.analysis.id, RankingFilters(search="pRiYa"))) == ["Priya Nair"]
    assert names(rank_candidates(db_session, analysis.analysis.id, RankingFilters(search="karthik.iyer@"))) == ["Karthik Iyer"]
    assert rank_candidates(db_session, analysis.analysis.id, RankingFilters(search="%")).items == []  # literal %, not wildcard


def test_filters_keep_original_ranks(db_session, analysis):
    full = {item.candidate.name: item.rank for item in rank_candidates(db_session, analysis.analysis.id).items}
    filtered = rank_candidates(db_session, analysis.analysis.id, RankingFilters(min_score=50, min_experience=4))
    assert filtered.items and all(item.match.final_score >= 50 for item in filtered.items)
    assert all(item.match.relevant_experience >= 4 for item in filtered.items)
    for item in filtered.items:
        assert item.rank == full[item.candidate.name]  # rank is not renumbered after filtering
    searched = rank_candidates(db_session, analysis.analysis.id, RankingFilters(search="Fatima"))
    assert searched.items[0].rank == 12


def test_score_range_filter(db_session, analysis):
    page = rank_candidates(db_session, analysis.analysis.id, RankingFilters(min_score=40, max_score=70))
    assert all(40 <= item.match.final_score <= 70 for item in page.items)


def test_sort_by_name_and_experience(db_session, analysis):
    by_name = names(rank_candidates(db_session, analysis.analysis.id, RankingFilters(sort_by=SortField.name)))
    assert by_name == sorted(by_name)
    by_exp = rank_candidates(db_session, analysis.analysis.id, RankingFilters(sort_by=SortField.total_experience))
    totals = [item.candidate.total_experience for item in by_exp.items]
    assert totals == sorted(totals, reverse=True)
    lowest_first = rank_candidates(db_session, analysis.analysis.id, RankingFilters(sort_by=SortField.final_score, descending=False))
    assert lowest_first.items[0].candidate.name == "Fatima Sheikh"


def test_pagination(db_session, analysis):
    first = rank_candidates(db_session, analysis.analysis.id, RankingFilters(limit=5))
    second = rank_candidates(db_session, analysis.analysis.id, RankingFilters(limit=5, offset=5))
    assert len(first.items) == 5 and first.filtered_count == 12
    assert {i.match.id for i in first.items}.isdisjoint({i.match.id for i in second.items})
    assert second.items[0].rank >= first.items[-1].rank


def test_get_single_ranked_candidate(db_session, analysis):
    page = rank_candidates(db_session, analysis.analysis.id)
    third = page.items[2]
    detail = get_ranked_candidate(db_session, analysis.analysis.id, third.candidate.id)
    assert detail.rank == third.rank and detail.match.id == third.match.id
    assert get_ranked_candidate(db_session, analysis.analysis.id, uuid.uuid4()) is None


def test_equal_scores_share_rank_and_have_stable_order(db_session, python_job, parsed_samples, monkeypatch):
    """Two candidates with identical resumes (different names) get the same score and the same rank."""
    monkeypatch.setattr(scoring.semantic_matcher, "similarities", lambda jd, texts: [0.5] * len(texts))
    _, parsed = parsed_samples[1]
    twins = []
    for name in ("Zara Twin", "Adam Twin"):
        candidate = candidate_service.build_candidate(parsed, f"{name}.pdf", uuid.uuid4().hex, owner_id=python_job.owner_id)
        candidate.name = name
        twins.append(candidate)
    weaker = candidate_service.build_candidate(parsed_samples[9][1], "weaker.pdf", uuid.uuid4().hex, owner_id=python_job.owner_id)
    db_session.add_all([*twins, weaker])
    db_session.commit()

    run = run_analysis(db_session, python_job.id, [weaker.id, twins[0].id, twins[1].id], today=TODAY, owner_id=python_job.owner_id)
    page = rank_candidates(db_session, run.analysis.id)
    assert [item.rank for item in page.items] == [1, 1, 3]  # competition ranking
    assert names(page)[:2] == ["Adam Twin", "Zara Twin"]  # tie broken by name, every time
    assert page.items[0].match.final_score == page.items[1].match.final_score
    top1 = rank_candidates(db_session, run.analysis.id, RankingFilters(top=1))
    assert len(top1.items) == 2  # a tie at the cut-off is included
