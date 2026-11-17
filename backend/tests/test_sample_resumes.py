"""
End-to-end parsing of the 12 synthetic resumes in <repo>/sample_resumes/.

Expected values were worked out by hand from the resume content, with
"Present" = November 2026 (TODAY), so the results are reproducible.
Regenerate the files with:  python scripts/generate_sample_resumes.py
"""
from datetime import date
from pathlib import Path

import pytest

from app.parser.resume_parser import parse_resume
from app.utils.file_validator import validate_resume_file

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "sample_resumes"
TODAY = date(2026, 11, 1)

# file -> (name, email, phone, total_years, method, skills that MUST be found, skills that must NOT be found)
EXPECTED = {
    "01_arjun_mehta_python_backend.pdf": ("Arjun Mehta", "arjun.mehta@example.com", "+91 98450 12345", 8.5, "date_ranges",
        {"Python", "FastAPI", "Django", "PostgreSQL", "Docker", "AWS", "REST APIs", "Redis"}, {"MySQL", "Java"}),
    "02_priya_nair_python_fastapi.docx": ("Priya Nair", "priya.nair@example.com", "+91-99000-22334", 4.3, "date_ranges",
        {"Python", "FastAPI", "SQL", "PostgreSQL", "SQLAlchemy", "Pytest", "REST APIs"}, {"Docker", "Flask"}),
    "03_karthik_iyer_java.pdf": ("Karthik Iyer", "karthik.iyer@example.com", "+91 91234 56789", 5.9, "date_ranges",
        {"Java", "Spring Boot", "Hibernate", "MySQL", "JUnit", "JavaScript"}, {"Python", "SQL"}),
    "04_sneha_kulkarni_data_scientist.docx": ("Sneha Kulkarni", "sneha.kulkarni@example.com", "+91 98220 44556", 6.4, "date_ranges",
        {"Python", "Machine Learning", "Deep Learning", "NLP", "Scikit-learn", "TensorFlow", "Pandas", "SQL"}, {"Java"}),
    "05_vikram_singh_flask_backend.pdf": ("Vikram Singh", "vikram.singh@example.com", "+91 97111 23456", 5.8, "date_ranges",
        {"Python", "Flask", "MySQL", "REST APIs", "Docker"}, {"FastAPI", "Django", "PostgreSQL"}),
    "06_ananya_reddy_fullstack.docx": ("Ananya Reddy", "ananya.reddy@example.com", "+91 90000 11223", 3.2, "date_ranges",
        {"JavaScript", "TypeScript", "React", "Node.js", "Express.js", "MongoDB", "Tailwind CSS"}, {"Java", "Python"}),
    "07_rohan_gupta_fresher.pdf": ("Rohan Gupta", "rohan.gupta@example.com", "9876501234", 0.0, "fresher",
        {"Python", "Flask", "Pandas", "Scikit-learn", "SQL", "Data Structures"}, {"Artificial Intelligence"}),
    "08_meera_joshi_dotnet_sql.docx": ("Meera Joshi", "meera.joshi@example.com", "+1 (415) 555-0142", 7.8, "date_ranges",
        {"C#", ".NET", "SQL", "Microsoft SQL Server", "REST APIs", "Azure"}, {"PostgreSQL", "MySQL", "C"}),
    "09_aditya_rao_ml_engineer.pdf": ("Aditya Rao", "aditya.rao@example.com", "+91 99860 77889", 6.9, "date_ranges",
        {"Python", "PyTorch", "NLP", "Sentence Transformers", "Docker", "Kubernetes", "FastAPI"}, {"GitHub"}),
    "10_fatima_sheikh_embedded.docx": ("Fatima Sheikh", "fatima.sheikh@example.com", "+91 93222 98765", 6.2, "date_ranges",
        {"Embedded C", "C", "C++", "RTOS", "MATLAB"}, {"Python", "Java", "SQL", "Machine Learning", "Algorithms"}),
    "11_neha_patil_no_contact.pdf": ("Neha Patil", None, None, 4.0, "stated_in_resume",
        {"Python", "SQL", "Django"}, set()),
    "12_sanjay_verma_data_analyst.docx": ("Sanjay Verma", "sanjay.verma@example.com", "+91 98100 65432", 3.9, "date_ranges",
        {"SQL", "Excel", "Power BI", "Tableau", "Python", "Pandas"}, {"Machine Learning"}),
}


def test_sample_set_has_at_least_ten_pdf_and_docx_resumes():
    files = sorted(p.name for p in SAMPLES_DIR.glob("*") if p.suffix in {".pdf", ".docx"})
    assert set(files) == set(EXPECTED)
    assert len(files) >= 10
    assert any(f.endswith(".pdf") for f in files) and any(f.endswith(".docx") for f in files)


@pytest.mark.parametrize("filename", sorted(EXPECTED))
def test_sample_resume_parsed_correctly(filename):
    name, email, phone, total, method, must_have, must_not = EXPECTED[filename]
    content = (SAMPLES_DIR / filename).read_bytes()
    validated = validate_resume_file(filename, content)  # the same validation the upload uses
    result = parse_resume(validated.content, validated.extension, today=TODAY)

    assert result.name == name
    assert result.email == email
    assert result.phone == phone
    assert result.total_experience_years == total
    assert result.experience_method == method
    assert must_have <= set(result.skills), f"missing: {must_have - set(result.skills)}"
    assert not (must_not & set(result.skills)), f"false positives: {must_not & set(result.skills)}"
    assert result.education, "education should be found"
    assert "bachelor" in result.degree_levels


def test_overlapping_freelance_job_is_merged():
    result = parse_resume((SAMPLES_DIR / "05_vikram_singh_flask_backend.pdf").read_bytes(), ".pdf", today=TODAY)
    assert sum(e["months"] for e in result.experience) == 76  # naive sum would be 6.3 years
    assert result.total_experience_years == 5.8  # merged: 69 months


def test_internship_reported_separately():
    ananya = parse_resume((SAMPLES_DIR / "06_ananya_reddy_fullstack.docx").read_bytes(), ".docx", today=TODAY)
    assert ananya.internship_experience_years == 0.5
    rohan = parse_resume((SAMPLES_DIR / "07_rohan_gupta_fresher.pdf").read_bytes(), ".pdf", today=TODAY)
    assert rohan.is_fresher and rohan.internship_experience_years == 0.5
    assert [p["title"] for p in rohan.projects] == ["Resume Screening Tool", "Weather Dashboard"]


def test_certifications_found():
    sneha = parse_resume((SAMPLES_DIR / "04_sneha_kulkarni_data_scientist.docx").read_bytes(), ".docx", today=TODAY)
    assert sneha.certifications == ["TensorFlow Developer Certificate", "Google Data Analytics Professional Certificate"]


def test_name_in_word_page_header_is_found():
    meera = parse_resume((SAMPLES_DIR / "08_meera_joshi_dotnet_sql.docx").read_bytes(), ".docx", today=TODAY)
    assert meera.name == "Meera Joshi"
