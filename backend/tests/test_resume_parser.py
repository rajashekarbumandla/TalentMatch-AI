"""Unit tests for candidate-information extraction from resume text."""
from datetime import date

import pytest

from app.parser import experience
from app.parser.experience import date_range_to_interval, merge_intervals, parse_date
from app.parser.resume_parser import (
    extract_candidate_info,
    extract_email,
    extract_name,
    extract_phone,
    extract_projects,
)
from app.parser.sections import split_sections

TODAY = date(2026, 11, 1)


# --- Contact details -----------------------------------------------------------------------------
def test_email_extraction():
    assert extract_email("Contact: Jane.Doe+jobs@Example.co.in | 98765") == "jane.doe+jobs@example.co.in"
    assert extract_email("no email here") is None


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Phone: +91 98450 12345", "+91 98450 12345"),
        ("Mobile (+1) 415-555-0142 Remote", "(+1) 415-555-0142"),
        ("+1 (415) 555-0142", "+1 (415) 555-0142"),
        ("Call 9876501234 anytime", "9876501234"),
        ("+91-99000-22334", "+91-99000-22334"),
    ],
)
def test_phone_extraction(text, expected):
    assert extract_phone(text) == expected


@pytest.mark.parametrize("text", ["2019 - 2021 2022", "Pin 560001", "CGPA 8.4/10", "Jan 2020 - Present", "no phone"])
def test_phone_not_confused_with_numbers(text):
    assert extract_phone(text) is None


# --- Name ------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "header, expected",
    [
        ("Arjun Mehta\nSenior Python Developer\narjun@example.com", "Arjun Mehta"),
        ("ARJUN MEHTA\nData Analyst", "Arjun Mehta"),
        ("RESUME\nPriya S. Nair | Python Developer", "Priya S. Nair"),
        ("Curriculum Vitae\nKarthik Iyer, Chennai", "Karthik Iyer"),
    ],
)
def test_name_heuristic(header, expected):
    assert extract_name(header, header)[0] == expected


def test_name_not_guessed_from_job_title_or_skills():
    header = "Senior Software Engineer\nPython Django Docker\njane@example.com"
    name, method = extract_name(header, header)
    assert name is None or name not in {"Senior Software Engineer", "Python Django Docker"}


def test_name_falls_back_to_spacy_ner(monkeypatch):
    class Entity:
        def __init__(self, text, label):
            self.text, self.label_ = text, label

    class FakeDoc:
        ents = [Entity("Chennai", "GPE"), Entity("Divya Raman", "PERSON")]

    import app.parser.resume_parser as resume_parser

    monkeypatch.setattr(resume_parser, "get_spacy_model", lambda: (lambda text: FakeDoc()))
    header = "Contact: Divya Raman, Chennai"  # heuristic fails because of "Contact:"
    assert extract_name(header, header) == ("Divya Raman", "spacy_ner")


def test_real_spacy_model_loads():
    from app.nlp.spacy_model import get_spacy_model

    nlp = get_spacy_model()
    assert nlp is not None and "ner" in nlp.pipe_names


# --- Sections ----------------------------------------------------------------------------------------
def test_sections_detected_with_varied_headings():
    text = "Jane Doe\nPROFESSIONAL SUMMARY\nPython dev\nTechnical Skills:\nPython\nWork Experience\nDev at X\nEDUCATION\nB.Tech\nLicenses & Certifications\nAWS"
    sections = split_sections(text)
    assert list(sections) == ["header", "summary", "skills", "experience", "education", "certifications"]
    assert sections["header"] == "Jane Doe" and sections["certifications"] == "AWS"


def test_inline_heading_and_sub_labels():
    text = "Skills: Python, SQL\nLanguages: Java, C\nExperience\nDev | X | 2020 - 2021\nTechnologies: Flask"
    sections = split_sections(text)
    assert sections["skills"] == "Python, SQL\nLanguages: Java, C"  # sub-label stays in Skills
    assert "Technologies: Flask" in sections["experience"]  # sub-label inside a job stays in Experience


# --- Dates and experience ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text, expected",
    [("Jan 2020", (2020, 1)), ("September, 2019", (2019, 9)), ("Sept 2019", (2019, 9)), ("03/2018", (2018, 3)),
     ("2018-03", (2018, 3)), ("2017", (2017, None)), ("Present", (2026, 11)), ("13/2018", None), ("1800", None)],
)
def test_parse_date_formats(text, expected):
    assert parse_date(text, TODAY) == expected


def test_month_ranges_are_inclusive_and_year_ranges_whole_years():
    assert date_range_to_interval("Jan 2020", "Dec 2020", TODAY)[1] - date_range_to_interval("Jan 2020", "Dec 2020", TODAY)[0] == 12
    start, end, *_ = date_range_to_interval("2019", "2021", TODAY)
    assert end - start == 24


def test_future_end_dates_are_capped_at_today():
    start, end, *_ = date_range_to_interval("Jan 2026", "Dec 2027", TODAY)
    assert end - start == 11  # Jan..Nov 2026


def test_merge_intervals_handles_overlap():
    assert merge_intervals([(0, 12), (6, 18)]) == 18  # overlapping -> counted once
    assert merge_intervals([(0, 12), (24, 36)]) == 24  # gap -> both counted
    assert merge_intervals([(0, 36), (6, 12)]) == 36  # contained
    assert merge_intervals([]) == 0


def test_overlapping_jobs_not_double_counted():
    text = "Experience\nDeveloper | A Corp | Jan 2020 - Dec 2021\n- Built APIs\nFreelancer | Self | Jun 2021 - Dec 2022\n- Side work"
    result = extract_candidate_info(text, today=TODAY)
    assert result.total_experience_years == 3.0  # Jan 2020 - Dec 2022, not 2 + 1.6
    assert result.experience_method == "date_ranges"


def test_internships_are_counted_separately():
    text = "Experience\nEngineer | A | Jan 2024 - Dec 2024\nSoftware Intern | B | Jun 2023 - Nov 2023"
    result = extract_candidate_info(text, today=TODAY)
    assert result.total_experience_years == 1.0
    assert result.internship_experience_years == 0.5


def test_education_years_are_not_work_experience():
    text = "Jane Doe\nEducation\nB.Tech in CSE, 2016 - 2020\nSkills\nPython"
    result = extract_candidate_info(text, today=TODAY)
    assert result.total_experience_years is None and result.experience_method == "unknown"
    assert any("experience is unknown" in w for w in result.warnings)


def test_fresher_without_jobs_has_zero_experience():
    result = extract_candidate_info("Jane Doe\nSummary\nFresher seeking a Python role.\nSkills\nPython", today=TODAY)
    assert result.total_experience_years == 0.0 and result.is_fresher and result.experience_method == "fresher"


def test_stated_experience_used_when_no_dates():
    result = extract_candidate_info("Jane Doe\nSummary\nDeveloper with 5+ years of experience in Python.", today=TODAY)
    assert result.total_experience_years == 5.0 and result.experience_method == "stated_in_resume"


def test_undated_experience_is_unknown_not_zero():
    result = extract_candidate_info("Jane Doe\nExperience\nDeveloper at Example Corp\n- Built things", today=TODAY)
    assert result.total_experience_years is None
    assert any("without dates" in w for w in result.warnings)


def test_entry_title_company_and_skills():
    text = "Work Experience\nSoftware Engineer - Java | Orion | June 2021 - Present\n- Built Spring Boot services on AWS"
    entry = extract_candidate_info(text, today=TODAY).experience[0]
    assert entry["title"] == "Software Engineer - Java" and entry["company"] == "Orion"
    assert entry["start"] == "2021-06" and entry["end"] == "present" and entry["months"] == 66
    assert entry["skills"] == ["Java", "Spring Boot", "AWS"]


def test_stated_experience_ignores_internship_statements():
    assert experience.find_stated_experience("1 year of internship experience") is None


# --- Education, certifications, projects ---------------------------------------------------------------
def test_education_grouping_and_levels():
    text = "Education\nM.Sc in Data Science\nSahyadri University, 2018 - 2020\nB.E. in Electronics\nCGPA\n8.1/10"
    result = extract_candidate_info(text, today=TODAY)
    assert result.education == ["M.Sc in Data Science, Sahyadri University, 2018 - 2020", "B.E. in Electronics, CGPA 8.1/10"]
    assert result.degree_levels == ["master", "bachelor"]


def test_ms_excel_is_not_a_masters_degree():
    result = extract_candidate_info("Jane Doe\nSkills\nMS Excel, Python\nEducation\nBCA, 2020", today=TODAY)
    assert result.degree_levels == ["bachelor"]


def test_certifications_from_section_and_fallback():
    with_section = extract_candidate_info("Jane\nCertifications\n- AWS Certified Developer\n- Scrum Master", today=TODAY)
    assert with_section.certifications == ["AWS Certified Developer", "Scrum Master"]
    without_section = extract_candidate_info("Jane\nSummary\nGoogle Certified Data Engineer with Python.", today=TODAY)
    assert without_section.certifications == ["Google Certified Data Engineer with Python."]


def test_projects_titles_and_bullets():
    projects = extract_projects(
        "Resume Matcher\n- Ranked resumes with Python and scikit-learn\n- Added a Flask UI\nWeather App\n- React UI with REST APIs"
    )
    assert [p["title"] for p in projects] == ["Resume Matcher", "Weather App"]
    assert projects[0]["skills"] == ["Python", "Scikit-learn", "Flask"]
    assert projects[0]["description"] == "Ranked resumes with Python and scikit-learn\nAdded a Flask UI"
    assert projects[1]["skills"] == ["React", "REST APIs"]
    # Bullet-only list: each bullet is its own project with "Title: description".
    bullet_only = extract_projects("- Weather App: React UI with REST APIs\n- Chat Bot - NLP with spaCy")
    assert [p["title"] for p in bullet_only] == ["Weather App", "Chat Bot"]
    assert bullet_only[1]["skills"] == ["NLP", "spaCy"]


# --- Missing information is never invented -------------------------------------------------------------
def test_missing_contact_details_are_none_with_warnings():
    result = extract_candidate_info("SUMMARY\nPython developer\nSKILLS\nPython, SQL", today=TODAY)
    assert result.email is None and result.phone is None and result.name is None
    assert {"Candidate name not found in the resume.", "Candidate email address not found in the resume.",
            "Candidate phone number not found in the resume."} <= set(result.warnings)


def test_skills_not_taken_from_urls_or_emails():
    result = extract_candidate_info("Jane Doe\npython.dev@example.com | github.com/jane/docker-tools\nSkills\nJava", today=TODAY)
    assert result.skills == ["Java"]
    assert result.links == ["github.com/jane/docker-tools"]
