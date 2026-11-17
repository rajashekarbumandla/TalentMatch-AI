"""
API tests with FastAPI's TestClient, against the real Supabase database.

The `get_db` dependency is overridden with the rolled-back test session, so the
complete workflow (create job -> upload 12 resumes -> analyze -> rank -> export)
runs for real but leaves nothing behind.
"""
import csv
import io
import uuid
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.auth.security import create_access_token
from app.config import settings
from app.database import get_db
from app.main import app
from app.services.export_service import ranked_candidates_to_csv, safe_cell

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_FILES = sorted(p for p in (ROOT / "sample_resumes").glob("*") if p.suffix in {".pdf", ".docx"})
PYTHON_JD = (ROOT / "sample_jds" / "01_python_developer.txt").read_text(encoding="utf-8")
MIME = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


@pytest.fixture
def client(db_session, hr_user):
    """A TestClient logged in as a test HR (token sent on every request)."""
    app.dependency_overrides[get_db] = lambda: db_session
    token, _ = create_access_token(hr_user.id, hr_user.token_version)
    yield TestClient(app, headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()


def as_upload(path: Path):
    return ("files", (path.name, path.read_bytes(), MIME[path.suffix]))


def create_job(client, **overrides) -> dict:
    payload = {"job_title": "Python Developer", "description": PYTHON_JD,
               "required_skills": ["Python", "FastAPI", "SQL", "REST APIs", "Machine Learning", "Docker"],
               "minimum_experience": 3}
    payload.update(overrides)
    response = client.post("/api/jobs/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def analyzed(client):
    """A saved job, the 12 sample resumes uploaded, and one analysis."""
    job = create_job(client)
    upload = client.post("/api/resumes/upload", files=[as_upload(p) for p in SAMPLE_FILES]).json()
    analysis = client.post(f"/api/analyze/{job['id']}", json={"candidate_ids": upload["candidate_ids"]})
    assert analysis.status_code == 200, analysis.text
    return {"job": job, "upload": upload, "analysis": analysis.json()}


# --- Jobs ------------------------------------------------------------------------------------------------------
def test_analyze_jd_text_returns_suggestions(client):
    response = client.post("/api/jobs/analyze", json={"description": PYTHON_JD})
    assert response.status_code == 200
    body = response.json()
    assert body["job_title"] == "Python Developer" and body["minimum_experience"] == 3.0
    assert body["required_skills"] == ["Python", "FastAPI", "SQL", "REST APIs", "Machine Learning", "Docker"]


def test_analyze_jd_file_upload(client):
    path = ROOT / "sample_jds" / "06_java_developer.docx"
    response = client.post("/api/jobs/analyze-file", files={"file": (path.name, path.read_bytes(), MIME[".docx"])})
    assert response.status_code == 200 and response.json()["job_title"] == "Java Developer"
    assert "Spring Boot microservices" in response.json()["description"]  # extracted text, ready to save as a job


def test_jd_without_experience_requirement(client):
    jd = (ROOT / "sample_jds" / "04_frontend_developer_no_experience.txt").read_text(encoding="utf-8")
    body = client.post("/api/jobs/analyze", json={"description": jd}).json()
    assert body["minimum_experience"] is None
    assert any("No minimum experience" in w for w in body["warnings"])


@pytest.mark.parametrize("description", ["", "   ", "too short"])
def test_empty_jd_rejected(client, description):
    response = client.post("/api/jobs/analyze", json={"description": description})
    assert response.status_code == 422
    assert client.post("/api/jobs/", json={"job_title": "X Dev", "description": description}).status_code == 422


def test_jd_file_with_unsupported_format(client):
    response = client.post("/api/jobs/analyze-file", files={"file": ("jd.txt", b"some text", "text/plain")})
    assert response.status_code == 422 and "Unsupported file format" in response.json()["detail"]


def test_job_crud(client):
    job = create_job(client, required_skills=["python", "postgres"], preferred_skills=["Docker", "PostgreSQL"])
    assert job["required_skills"] == ["Python", "PostgreSQL"] and job["preferred_skills"] == ["Docker"]
    assert client.get(f"/api/jobs/{job['id']}").json()["job_title"] == "Python Developer"
    listed = client.get("/api/jobs/").json()
    assert any(j["id"] == job["id"] and j["analysis_count"] == 0 for j in listed)

    updated = client.put(f"/api/jobs/{job['id']}", json={"minimum_experience": 5, "required_skills": ["Python", "Docker"]})
    assert updated.status_code == 200
    assert updated.json()["minimum_experience"] == 5 and updated.json()["preferred_skills"] == []

    assert client.put(f"/api/jobs/{job['id']}", json={"minimum_experience": -1}).status_code == 422
    assert client.delete(f"/api/jobs/{job['id']}").status_code == 204
    assert client.get(f"/api/jobs/{job['id']}").status_code == 404


def test_not_found_and_invalid_ids(client):
    assert client.get(f"/api/jobs/{uuid.uuid4()}").json() == {"detail": "Job not found."}
    assert client.get("/api/jobs/not-a-uuid").status_code == 422
    assert client.get(f"/api/candidates/{uuid.uuid4()}").status_code == 404


# --- Resume upload -----------------------------------------------------------------------------------------------
def test_upload_ten_plus_resumes(client):
    response = client.post("/api/resumes/upload", files=[as_upload(p) for p in SAMPLE_FILES])
    assert response.status_code == 200
    body = response.json()
    assert body["total_files"] == 12 and body["parsed"] == 12 and body["failed"] == 0
    assert len(body["candidate_ids"]) == 12
    neha = next(f for f in body["files"] if f["filename"].startswith("11_"))
    assert neha["email"] is None and neha["phone"] is None  # missing contact info -> null, not invented
    assert any("email" in w for w in neha["warnings"])


def scanned_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), False)
    pixmap.clear_with(180)
    page.insert_image(pymupdf.Rect(50, 50, 150, 150), pixmap=pixmap)
    return doc.tobytes()


def test_upload_with_invalid_files_partially_succeeds(client, monkeypatch):
    from app.parser import ocr_parser

    monkeypatch.setattr(ocr_parser, "is_ocr_available", lambda: False)
    blank = pymupdf.open()
    blank.new_page()
    good = SAMPLE_FILES[0]
    files = [
        as_upload(good),
        ("files", ("notes.txt", b"plain text", "text/plain")),  # unsupported format
        ("files", ("broken.pdf", b"%PDF-1.7 garbage", "application/pdf")),  # corrupted
        ("files", ("empty.pdf", blank.tobytes(), "application/pdf")),  # empty PDF
        ("files", ("scanned.pdf", scanned_pdf(), "application/pdf")),  # image only
        ("files", ("copy.pdf", good.read_bytes(), "application/pdf")),  # same content again
    ]
    body = client.post("/api/resumes/upload", files=files).json()
    by_name = {f["filename"]: f for f in body["files"]}
    assert body["parsed"] == 1 and body["duplicates"] == 1 and body["failed"] == 4
    assert "Unsupported file format" in by_name["notes.txt"]["error"]
    assert "damaged" in by_name["broken.pdf"]["error"]
    assert "empty" in by_name["empty.pdf"]["error"]
    assert "scanned" in by_name["scanned.pdf"]["error"]
    assert by_name["copy.pdf"]["status"] == "duplicate"
    assert by_name["copy.pdf"]["candidate_id"] == by_name[good.name]["candidate_id"]


def test_upload_limits(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_FILES_PER_BATCH", 3)
    response = client.post("/api/resumes/upload", files=[as_upload(p) for p in SAMPLE_FILES[:4]])
    assert response.status_code == 400 and "maximum per batch is 3" in response.json()["detail"]
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_MB", 0.001)  # ~1 KB
    body = client.post("/api/resumes/upload", files=[as_upload(SAMPLE_FILES[0])]).json()
    assert body["failed"] == 1 and "maximum allowed size" in body["files"][0]["error"]


def test_upload_without_files(client):
    assert client.post("/api/resumes/upload").status_code == 422


# --- Analysis and results ----------------------------------------------------------------------------------------
def test_full_analysis_workflow(client, analyzed):
    body = analyzed["analysis"]
    assert body["total_candidates"] == 12 and len(body["items"]) == 12
    scores = [item["final_score"] for item in body["items"]]
    assert scores == sorted(scores, reverse=True)
    assert body["items"][0]["rank"] == 1
    assert {body["items"][0]["name"], body["items"][1]["name"]} == {"Priya Nair", "Arjun Mehta"}
    fatima = next(i for i in body["items"] if i["name"] == "Fatima Sheikh")
    assert fatima["skills_score"] == 0 and fatima["matched_skills"] == []  # no matching skills
    for item in body["items"]:
        assert all(v is None or round(v, 2) == v for v in
                   (item["final_score"], item["semantic_score"], item["skills_score"], item["experience_score"]))


def test_results_with_filters(client, analyzed):
    job_id = analyzed["job"]["id"]
    top5 = client.get(f"/api/results/{job_id}", params={"top": 5}).json()
    assert len(top5["items"]) == 5 and top5["total_candidates"] == 12
    searched = client.get(f"/api/results/{job_id}", params={"search": "arjun"}).json()
    assert [i["name"] for i in searched["items"]] == ["Arjun Mehta"] and searched["items"][0]["rank"] <= 2
    filtered = client.get(f"/api/results/{job_id}", params={"min_score": 60, "min_experience": 4}).json()
    assert all(i["final_score"] >= 60 and i["relevant_experience"] >= 4 for i in filtered["items"])
    by_name = client.get(f"/api/results/{job_id}", params={"sort_by": "name", "order": "asc"}).json()
    names = [i["name"] for i in by_name["items"]]
    assert names == sorted(names)
    assert client.get(f"/api/results/{job_id}", params={"sort_by": "salary"}).status_code == 422
    assert client.get(f"/api/results/{job_id}", params={"min_score": 150}).status_code == 422


def test_results_for_unanalyzed_job(client):
    job = create_job(client)
    response = client.get(f"/api/results/{job['id']}")
    assert response.status_code == 404 and response.json()["detail"] == "This job has not been analyzed yet."


def test_analyze_errors(client):
    job = create_job(client)
    assert client.post(f"/api/analyze/{job['id']}", json={"candidate_ids": []}).status_code == 422
    missing = client.post(f"/api/analyze/{job['id']}", json={"candidate_ids": [str(uuid.uuid4())]})
    assert missing.status_code == 400 and "None of the selected resumes" in missing.json()["detail"]
    assert client.post(f"/api/analyze/{uuid.uuid4()}", json={"candidate_ids": [str(uuid.uuid4())]}).status_code == 404


def test_previous_analyses_retrievable(client, analyzed):
    job_id = analyzed["job"]["id"]
    second = client.post(f"/api/analyze/{job_id}", json={"candidate_ids": analyzed["upload"]["candidate_ids"][:3]}).json()
    history = client.get("/api/analyses/", params={"job_id": job_id}).json()
    assert {h["id"] for h in history} == {analyzed["analysis"]["analysis"]["id"], second["analysis"]["id"]}
    first = client.get(f"/api/results/{job_id}", params={"analysis_id": analyzed["analysis"]["analysis"]["id"]}).json()
    assert first["total_candidates"] == 12
    other_job = create_job(client)
    wrong = client.get(f"/api/results/{other_job['id']}", params={"analysis_id": second["analysis"]["id"]})
    assert wrong.status_code == 404


# --- CSV export ----------------------------------------------------------------------------------------------------
def test_csv_export(client, analyzed):
    response = client.get(f"/api/results/{analyzed['job']['id']}/export")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/csv")
    assert 'filename="talentmatch_python_developer_' in response.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0][:3] == ["Rank", "Candidate Name", "Email"] and len(rows) == 13
    assert rows[1][0] == "1" and rows[1][1] in {"Priya Nair", "Arjun Mehta"}
    neha = next(r for r in rows if r[1] == "Neha Patil")
    assert neha[2] == "Not found" and neha[3] == "Not found"
    filtered = client.get(f"/api/results/{analyzed['job']['id']}/export", params={"top": 3})
    assert len(list(csv.reader(io.StringIO(filtered.content.decode("utf-8-sig"))))) == 4


def test_csv_formula_injection_is_neutralised():
    assert safe_cell("=HYPERLINK(\"http://evil\")") == "'=HYPERLINK(\"http://evil\")"
    assert safe_cell("+91 98450 12345") == "'+91 98450 12345"
    assert safe_cell("Priya Nair") == "Priya Nair" and safe_cell(82.6649) == "82.66" and safe_cell(None) == ""
    assert ranked_candidates_to_csv([]).startswith("﻿Rank,")


# --- Candidates ------------------------------------------------------------------------------------------------------
def test_candidate_endpoints(client, analyzed):
    job_id = analyzed["job"]["id"]
    priya = next(i for i in analyzed["analysis"]["items"] if i["name"] == "Priya Nair")

    detail = client.get(f"/api/candidates/{priya['candidate_id']}").json()
    assert detail["email"] == "priya.nair@example.com" and "FastAPI" in detail["skills"]
    assert detail["education"] and detail["experience"] and detail["matches"][0]["job_id"] == job_id

    analysis = client.get(f"/api/candidates/{priya['candidate_id']}/analysis/{job_id}").json()
    match = analysis["match"]
    assert match["rank"] == priya["rank"] and match["total_candidates"] == 12
    assert match["matched_required_skills"] == ["Python", "FastAPI", "SQL", "REST APIs"]
    assert match["missing_required_skills"] == ["Machine Learning", "Docker"]
    assert match["required_experience"] == 3 and match["experience_status"] == "met"
    assert match["weights_used"] == pytest.approx({"semantic": 0.4, "skills": 0.35, "experience": 0.25})
    assert match["explanation"].startswith("The candidate shows")

    listing = client.get("/api/candidates/", params={"search": "priya"}).json()
    assert listing["total"] >= 1
    row = next(i for i in listing["items"] if i["id"] == priya["candidate_id"])
    assert row["latest_job_title"] == "Python Developer" and row["best_score"] == priya["final_score"]

    other_job = create_job(client)
    assert client.get(f"/api/candidates/{priya['candidate_id']}/analysis/{other_job['id']}").status_code == 404


def test_delete_candidate_recalculates_analysis(client, analyzed):
    job_id = analyzed["job"]["id"]
    fatima = next(i for i in analyzed["analysis"]["items"] if i["name"] == "Fatima Sheikh")
    assert client.delete(f"/api/candidates/{fatima['candidate_id']}").status_code == 204
    assert client.get(f"/api/candidates/{fatima['candidate_id']}").status_code == 404
    results = client.get(f"/api/results/{job_id}").json()
    assert results["total_candidates"] == 11 and len(results["items"]) == 11
    remaining = [i["final_score"] for i in results["items"]]
    assert results["analysis"]["average_score"] == pytest.approx(round(sum(remaining) / 11, 2), abs=0.01)
    assert client.delete(f"/api/candidates/{fatima['candidate_id']}").status_code == 404


# --- Dashboard -------------------------------------------------------------------------------------------------------
def test_dashboard_stats_reflect_database(client, analyzed):
    stats = client.get("/api/dashboard/stats").json()
    assert stats["total_jobs"] >= 1 and stats["total_analyses"] >= 1
    assert stats["resumes_analyzed"] >= 12 and stats["total_candidates"] >= 12
    assert 0 <= stats["average_score"] <= 100
    assert sum(b["count"] for b in stats["score_distribution"]) == stats["total_matches"]
    assert [b["range"] for b in stats["score_distribution"]] == ["0-20", "20-40", "40-60", "60-80", "80-100"]
    assert stats["recent_analyses"][0]["id"] == analyzed["analysis"]["analysis"]["id"]
    assert len(stats["activity"]) == 30 and stats["activity"][-1]["analyses"] >= 1
    overview = stats["ranking_overview"]
    assert overview["analysis_id"] == analyzed["analysis"]["analysis"]["id"]
    assert len(overview["candidates"]) == 10 and overview["candidates"][0]["rank"] == 1


# --- Errors ------------------------------------------------------------------------------------------------------------
def test_database_outage_returns_503(client):
    def broken_db():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    app.dependency_overrides[get_db] = broken_db
    response = client.get("/api/jobs/")
    assert response.status_code == 503
    assert response.json() == {"detail": "The database is temporarily unavailable. Please try again."}


def test_settings_endpoint(client):
    body = client.get("/api/settings/").json()
    assert body["weights"] == pytest.approx({"semantic": 0.4, "skills": 0.35, "experience": 0.25})
    assert body["max_files_per_batch"] == settings.MAX_FILES_PER_BATCH
    assert body["allowed_extensions"] == [".pdf", ".docx"]


def test_swagger_lists_all_endpoints(client):
    paths = set(client.get("/openapi.json").json()["paths"])
    assert {
        "/api/jobs/", "/api/jobs/{job_id}", "/api/jobs/analyze", "/api/jobs/analyze-file", "/api/resumes/upload",
        "/api/analyze/{job_id}", "/api/results/{job_id}", "/api/results/{job_id}/export", "/api/analyses/",
        "/api/candidates/", "/api/candidates/{candidate_id}", "/api/candidates/{candidate_id}/analysis/{job_id}",
        "/api/dashboard/stats", "/api/health",
    } <= paths
