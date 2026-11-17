"""Tests for Job Description analysis (no database needed)."""
from pathlib import Path

import pytest

from app.nlp.jd_analyzer import JDAnalysisError, analyze_job_description, analyze_job_description_file, experience_bounds
from app.nlp.skill_extractor import extract_skill_requirements, normalize_skill, split_alternatives
from app.utils.file_validator import FileValidationError

JD_DIR = Path(__file__).resolve().parents[2] / "sample_jds"
SPEC_EXAMPLE = (
    "We are looking for a Python Developer with at least 3 years of experience in Python, FastAPI, SQL, "
    "REST APIs, Machine Learning, and Docker. Candidates should have a Bachelor's degree in Computer Science "
    "or an equivalent qualification."
)


def load(name: str) -> str:
    return (JD_DIR / name).read_text(encoding="utf-8")


# --- The assignment's own example ---------------------------------------------------------------------
def test_assignment_example_jd():
    result = analyze_job_description(SPEC_EXAMPLE)
    assert result.job_title == "Python Developer"
    assert result.required_skills == ["Python", "FastAPI", "SQL", "REST APIs", "Machine Learning", "Docker"]
    assert result.preferred_skills == []
    assert result.minimum_experience == 3.0
    assert result.education_requirements == "Bachelor's degree in Computer Science or an equivalent qualification"
    assert result.education_level == "bachelor"
    assert result.skill_evidence["Docker"].startswith("We are looking for a Python Developer")


# --- Required vs preferred --------------------------------------------------------------------------------
def test_sectioned_jd_separates_required_and_preferred():
    result = analyze_job_description(load("02_senior_backend_engineer.txt"))
    assert result.job_title == "Senior Backend Engineer"
    assert {"Python", "FastAPI", "PostgreSQL", "Docker", "Git", "REST APIs"} <= set(result.required_skills)
    assert result.preferred_skills == ["Kubernetes", "Redis", "Microservices", "AWS"]
    assert not set(result.required_skills) & set(result.preferred_skills)
    assert result.minimum_experience == 5.0  # not the "at least 2 years with Python" in the same sentence
    assert set(result.sections_found) == {"company", "responsibilities", "requirements", "preferred"}


@pytest.mark.parametrize(
    "jd, required, preferred",
    [
        ("Requirements: Python and SQL. Knowledge of Docker is a plus.", ["Python", "SQL"], ["Docker"]),
        ("Must know Java; experience with Kubernetes would be an advantage.", ["Java"], ["Kubernetes"]),
        ("Strong React skills required. Good to have: Redux and Next.js knowledge.", ["React"], ["Redux", "Next.js"]),
        # Python appears in a required AND a preferred sentence -> required only; Flask -> preferred.
        ("Python developer needed. Python experience preferred too, plus Flask.", ["Python"], ["Flask"]),
    ],
)
def test_preferred_cue_words(jd, required, preferred):
    result = analyze_job_description(jd)
    assert result.required_skills == required
    assert result.preferred_skills == preferred


def test_skill_mentioned_as_both_is_only_required():
    result = analyze_job_description("Required: Python, Docker.\nNice to have\n- Docker, Kubernetes")
    assert result.required_skills == ["Python", "Docker"] and result.preferred_skills == ["Kubernetes"]


def test_company_section_skills_are_not_requirements():
    jd = "Backend Developer\nAbout Us\nWe run on AWS and Kubernetes.\nRequirements\n- 3+ years of Python experience"
    result = analyze_job_description(jd)
    assert result.required_skills == ["Python"] and result.preferred_skills == []
    assert "AWS" in result.keywords  # still recorded as context keywords


# --- Alternatives ("A or B") -----------------------------------------------------------------------------
def test_alternatives_are_one_requirement():
    assert extract_skill_requirements("Experience with FastAPI or Django, and Docker") == ["FastAPI or Django", "Docker"]
    assert extract_skill_requirements("HTML/CSS and Git") == ["HTML", "CSS", "Git"]  # "/" means both
    assert split_alternatives("TensorFlow or PyTorch") == ["TensorFlow", "PyTorch"]
    assert normalize_skill("pytorch or tensorflow") == "PyTorch or TensorFlow"


def test_redundant_alternative_group_dropped():
    result = analyze_job_description("Build APIs using FastAPI.\nRequirements\n- Strong FastAPI or Django experience")
    assert result.required_skills == ["FastAPI"]


def test_sample_jd_alternatives():
    data_scientist = analyze_job_description(load("03_data_scientist.txt"))
    assert "TensorFlow or PyTorch" in data_scientist.required_skills
    assert "Tableau or Power BI" in data_scientist.preferred_skills


# --- Experience ------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "sentence, expected",
    [
        ("at least 3 years of experience in Python", (3.0, None)),
        ("3+ years of experience", (3.0, None)),
        ("Minimum of 4 years experience in Java", (4.0, None)),
        ("2-4 years of experience in data science", (2.0, 4.0)),
        ("3 to 5 years of relevant experience", (3.0, 5.0)),
        ("Minimum of four (4) years of experience", (4.0, None)),
        ("five years of software experience", (5.0, None)),
        ("over 6 years of hands-on experience", (6.0, None)),
        ("6 months of experience with React", (0.5, None)),
        ("5+ years experience, including at least 2 years with Python", (5.0, None)),
        ("We have been in business for 20 years", None),  # not about candidate experience
        ("Experience with Python", None),
    ],
)
def test_experience_patterns(sentence, expected):
    assert experience_bounds(sentence) == expected


def test_jd_without_experience_requirement():
    result = analyze_job_description(load("04_frontend_developer_no_experience.txt"))
    assert result.minimum_experience is None
    assert any("No minimum experience" in w for w in result.warnings)


def test_fresher_jd_has_zero_minimum():
    result = analyze_job_description(load("07_ml_engineer_fresher.txt"))
    assert result.minimum_experience == 0.0


def test_preferred_experience_does_not_raise_minimum():
    result = analyze_job_description("Requirements\n- 2+ years of Python experience\nNice to have\n- 6+ years of experience")
    assert result.minimum_experience == 2.0


def test_company_age_is_not_experience():
    result = analyze_job_description("About Us\nWe have 25 years of experience serving clients.\nRequirements\n- Python")
    assert result.minimum_experience is None


# --- Education, title, responsibilities -----------------------------------------------------------------------
def test_education_lowest_required_level():
    result = analyze_job_description(load("03_data_scientist.txt"))
    assert result.education_level == "bachelor"  # Master's is only preferred
    assert "Master's degree is preferred" in result.education_requirements


@pytest.mark.parametrize(
    "jd, title",
    [
        ("Job Title: Data Engineer\nWe need Spark experience and solid SQL skills.", "Data Engineer"),
        ("Position: Java Developer\nSpring Boot microservices team.", "Java Developer"),
        ("We are hiring a senior backend engineer to build payment APIs.", "Senior Backend Engineer"),
        ("We are seeking an experienced DevOps Engineer with AWS skills.", "DevOps Engineer"),
        ("Frontend Developer\nBuild React applications for our clients.", "Frontend Developer"),
    ],
)
def test_job_title_detection(jd, title):
    assert analyze_job_description(jd).job_title == title


def test_recruiter_title_overrides_detection():
    assert analyze_job_description(SPEC_EXAMPLE, job_title="  Backend Python Engineer ").job_title == "Backend Python Engineer"


def test_responsibilities_from_section():
    result = analyze_job_description(load("02_senior_backend_engineer.txt"))
    assert len(result.responsibilities) == 5
    assert result.responsibilities[0].startswith("Design, build and maintain high-throughput REST APIs")


def test_responsibilities_from_verb_first_sentences_without_section():
    jd = (
        "We are hiring a Python developer. Design and build scalable REST APIs. Collaborate with product managers "
        "on new features. You will mentor junior developers. Candidates need 3+ years of experience."
    )
    responsibilities = analyze_job_description(jd).responsibilities
    assert responsibilities == [
        "Design and build scalable REST APIs",
        "Collaborate with product managers on new features",
        "You will mentor junior developers",
    ]


def test_keywords_contain_skills_and_no_skill_fragments():
    result = analyze_job_description(load("03_data_scientist.txt"))
    assert result.keywords[: len(result.required_skills)] == result.required_skills
    assert "machine" not in result.keywords and "learning" not in result.keywords


# --- Edge cases -----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("jd", ["", "   ", "Python dev", None])
def test_empty_or_tiny_jd_rejected(jd):
    with pytest.raises(JDAnalysisError, match="empty or too short"):
        analyze_job_description(jd)


def test_jd_with_no_technical_skills_warns():
    result = analyze_job_description(load("05_office_administrator_no_tech_skills.txt"))
    assert result.required_skills == [] and result.preferred_skills == []
    assert any("No technical skills" in w for w in result.warnings)
    assert result.job_title == "Office Administrator"
    assert result.minimum_experience == 2.0 and result.education_requirements == "Any graduate"


# --- File upload -----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("filename", ["06_java_developer.docx", "07_ml_engineer_fresher.pdf"])
def test_jd_file_matches_text_version(filename):
    from_file = analyze_job_description_file((JD_DIR / filename).read_bytes(), filename)
    from_text = analyze_job_description(load(Path(filename).stem + ".txt"))
    assert from_file.job_title == from_text.job_title
    assert from_file.required_skills == from_text.required_skills
    assert from_file.preferred_skills == from_text.preferred_skills
    assert from_file.minimum_experience == from_text.minimum_experience


def test_jd_file_with_wrong_format_rejected():
    with pytest.raises(FileValidationError, match="Unsupported"):
        analyze_job_description_file(b"plain text JD", "jd.txt")
