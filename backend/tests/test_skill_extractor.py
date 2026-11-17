"""Tests for dictionary-based skill extraction and normalisation."""
import pytest

from app.nlp.skill_extractor import (
    extract_skills,
    extract_skills_with_details,
    group_skills_by_category,
    is_known_skill,
    load_skill_dictionary,
    normalize_skill,
    normalize_skill_list,
)


def test_dictionary_loads_with_required_categories():
    categories = {skill.category for skill in load_skill_dictionary()}
    assert {"Programming Languages", "Backend", "Frontend", "Databases", "AI / Machine Learning"} <= categories
    names = {skill.name for skill in load_skill_dictionary()}
    for required in ["Python", "Java", "C", "C++", "JavaScript", "TypeScript", "FastAPI", "Flask", "Django",
                     "Node.js", "Express.js", "React", "Angular", "HTML", "CSS", "Tailwind CSS", "SQL", "MySQL",
                     "PostgreSQL", "MongoDB", "Firebase", "Supabase", "Machine Learning", "Deep Learning", "NLP",
                     "Scikit-learn", "TensorFlow", "PyTorch", "Sentence Transformers", "REST APIs", "Docker",
                     "Git", "GitHub", "AWS", "Azure", "Linux", "Data Structures", "Data Analysis"]:
        assert required in names, required


@pytest.mark.parametrize(
    "text, expected, forbidden",
    [
        ("Languages: C++ and C#", ["C++", "C#"], ["C"]),
        ("Strong in C and C++", ["C", "C++"], []),
        ("Built UIs in JavaScript", ["JavaScript"], ["Java"]),
        ("Java and JavaScript", ["Java", "JavaScript"], []),
        ("Wrote Java Script widgets", ["JavaScript"], ["Java"]),
        ("Database: PostgreSQL", ["PostgreSQL"], ["SQL"]),
        ("Database: MySQL", ["MySQL"], ["SQL"]),
        ("Backend in Node.js", ["Node.js"], ["JavaScript"]),
        ("Mobile apps in React Native", ["React Native"], ["React"]),
        ("Objective-C, C-level stakeholders, John C. Smith", [], ["C"]),
        ("I react quickly and rest well", [], ["React", "REST APIs"]),
    ],
)
def test_no_false_matches(text, expected, forbidden):
    found = extract_skills(text)
    for skill in expected:
        assert skill in found, f"{skill} missing from {found}"
    for skill in forbidden:
        assert skill not in found, f"{skill} wrongly found in {found}"


@pytest.mark.parametrize(
    "text, canonical",
    [
        ("ML", "Machine Learning"),
        ("Natural Language Processing", "NLP"),
        ("JS", "JavaScript"),
        ("Postgres", "PostgreSQL"),
        ("RESTful API", "REST APIs"),
        ("REST APIs", "REST APIs"),
        ("sklearn", "Scikit-learn"),
        ("K8s", "Kubernetes"),
        ("Fast API", "FastAPI"),
        ("sentence-transformers", "Sentence Transformers"),
    ],
)
def test_synonyms_map_to_canonical_name(text, canonical):
    assert extract_skills(f"Experience with {text}.") == [canonical]


def test_extraction_order_and_deduplication():
    assert extract_skills("Python, Docker, python, PYTHON, Docker") == ["Python", "Docker"]


def test_details_include_category_and_mentions():
    details = {d["name"]: d for d in extract_skills_with_details("Python and SQL. More Python.")}
    assert details["Python"] == {"name": "Python", "category": "Programming Languages", "mentions": 2}
    assert details["SQL"]["category"] == "Databases"


def test_normalize_skill_for_recruiter_input():
    assert normalize_skill("postgres") == "PostgreSQL"
    assert normalize_skill("  js ") == "JavaScript"
    assert normalize_skill("rest-api") == "REST APIs"
    assert normalize_skill("golang") == "Go"
    assert normalize_skill("Underwater Basket Weaving") == "Underwater Basket Weaving"  # unknown kept
    assert normalize_skill("   ") == ""


def test_normalize_skill_list_deduplicates():
    assert normalize_skill_list(["ML", "machine learning", "Python", "python3", ""]) == ["Machine Learning", "Python"]


def test_grouping_and_known_skill():
    grouped = group_skills_by_category(["Python", "Docker", "Basket Weaving"])
    assert grouped == {"Programming Languages": ["Python"], "Cloud & DevOps": ["Docker"], "Other": ["Basket Weaving"]}
    assert is_known_skill("postgres") and not is_known_skill("Basket Weaving")


def test_empty_text():
    assert extract_skills("") == [] and extract_skills(None) == []
