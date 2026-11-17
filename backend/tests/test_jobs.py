"""Tests for recruiter editing (Pydantic schemas) and saving jobs to Supabase (job_service)."""
import pytest
from pydantic import ValidationError

from app.models import Job
from app.nlp.jd_analyzer import analyze_job_description
from app.schemas import JDAnalysisResponse, JobCreate, JobRead, JobUpdate
from app.services import job_service

DESCRIPTION = "We are looking for a Python Developer with at least 3 years of experience in Python, FastAPI and SQL."


def make_create(**overrides) -> JobCreate:
    values = dict(job_title="Python Developer", description=DESCRIPTION, required_skills=["Python", "FastAPI", "SQL"])
    values.update(overrides)
    return JobCreate(**values)


# --- Schema validation and cleaning (no database) -------------------------------------------------------
def test_recruiter_edits_are_normalised():
    job = make_create(
        job_title="  Python   Developer ",
        required_skills=["python", "postgres", "ML", "Python", " ", "pytorch or tensorflow"],
        preferred_skills=["Docker", "PostgreSQL", "k8s"],
        responsibilities=["  Build APIs ", "build apis", ""],
        education_requirements="   ",
    )
    assert job.job_title == "Python Developer"
    assert job.required_skills == ["Python", "PostgreSQL", "Machine Learning", "PyTorch or TensorFlow"]
    assert job.preferred_skills == ["Docker", "Kubernetes"]  # PostgreSQL removed: already required
    assert job.responsibilities == ["Build APIs"]
    assert job.education_requirements is None


def test_unknown_skills_are_kept():
    assert make_create(required_skills=["Underwater Basket Weaving"]).required_skills == ["Underwater Basket Weaving"]


@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"job_title": " "}, "job_title"),
        ({"description": "too short"}, "description"),
        ({"minimum_experience": -1}, "minimum_experience"),
        ({"minimum_experience": 80}, "minimum_experience"),
        ({"required_skills": ["x" * 101]}, "required_skills"),
        ({"required_skills": [f"Skill {i}" for i in range(61)]}, "required_skills"),
    ],
)
def test_invalid_job_data_rejected(overrides, field):
    with pytest.raises(ValidationError) as error:
        make_create(**overrides)
    assert field in str(error.value)


def test_analysis_result_converts_to_editable_job():
    analysis = analyze_job_description(DESCRIPTION)
    response = JDAnalysisResponse(**analysis.to_dict())
    job = JobCreate(description=DESCRIPTION, **response.model_dump(include={
        "job_title", "required_skills", "preferred_skills", "minimum_experience",
        "education_requirements", "responsibilities", "keywords",
    }))
    assert job.required_skills == ["Python", "FastAPI", "SQL"] and job.minimum_experience == 3.0


def test_update_only_contains_sent_fields():
    update = JobUpdate(minimum_experience=4)
    assert update.model_dump(exclude_unset=True) == {"minimum_experience": 4.0}


# --- Saving to Supabase (rolled back after each test) ---------------------------------------------------------
def test_create_and_read_job(db_session, hr_user):
    job = job_service.create_job(db_session, make_create(preferred_skills=["Docker"], minimum_experience=3), owner_id=hr_user.id)
    stored = job_service.get_job(db_session, job.id, owner_id=hr_user.id)
    read = JobRead.model_validate(stored)
    assert read.job_title == "Python Developer"
    assert read.required_skills == ["Python", "FastAPI", "SQL"] and read.preferred_skills == ["Docker"]
    assert read.minimum_experience == 3.0
    assert read.created_at is not None and read.updated_at is not None
    assert job.id in [j.id for j in job_service.list_jobs(db_session, owner_id=hr_user.id)]


def test_recruiter_edit_updates_only_sent_fields(db_session, hr_user):
    job = job_service.create_job(db_session, make_create(preferred_skills=["Docker", "AWS"], minimum_experience=3), owner_id=hr_user.id)
    job_service.update_job(db_session, job, JobUpdate(required_skills=["Python", "Docker"], minimum_experience=4))
    db_session.expire_all()
    stored = db_session.get(Job, job.id)
    assert stored.required_skills == ["Python", "Docker"]
    assert stored.preferred_skills == ["AWS"]  # Docker moved to required, so removed from preferred
    assert stored.minimum_experience == 4.0
    assert stored.job_title == "Python Developer"  # untouched


def test_explicit_null_removes_experience_requirement(db_session, hr_user):
    job = job_service.create_job(db_session, make_create(minimum_experience=3), owner_id=hr_user.id)
    job_service.update_job(db_session, job, JobUpdate.model_validate({"minimum_experience": None}))
    assert db_session.get(Job, job.id).minimum_experience is None


def test_delete_job(db_session, hr_user):
    job = job_service.create_job(db_session, make_create(), owner_id=hr_user.id)
    job_id = job.id
    job_service.delete_job(db_session, job)
    assert job_service.get_job(db_session, job_id, owner_id=hr_user.id) is None
