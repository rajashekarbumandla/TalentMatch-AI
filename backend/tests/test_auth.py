"""
HR accounts: password hashing, tokens, login, admin account management and
data isolation between HRs. Runs against Supabase inside a rolled-back transaction.
"""
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    password_problem,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Job
from app.services import user_service
from tests.conftest import TEST_PASSWORD

ROOT = Path(__file__).resolve().parents[2]
JD = (ROOT / "sample_jds" / "01_python_developer.txt").read_text(encoding="utf-8")


# --- Passwords & tokens (no database) ------------------------------------------------------------------
def test_password_hash_is_salted_and_verifiable():
    first, second = hash_password("Secret123"), hash_password("Secret123")
    assert first != second  # different random salt each time
    assert "Secret123" not in first and first.startswith("scrypt$")
    assert verify_password("Secret123", first) and verify_password("Secret123", second)
    assert not verify_password("secret123", first)
    assert not verify_password("Secret123", "not-a-valid-hash")


@pytest.mark.parametrize(
    "password, ok",
    [("short1", False), ("lettersonly", False), ("12345678", False), ("Recruit3r", True), ("a" * 127 + "1", True)],
)
def test_password_rules(password, ok):
    assert (password_problem(password) is None) is ok


def test_token_roundtrip_and_rejection():
    user_id = uuid.uuid4()
    token, expires_at = create_access_token(user_id, token_version=3)
    claims = decode_access_token(token)
    assert claims["sub"] == str(user_id) and claims["ver"] == 3
    assert expires_at > datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES - 1)
    assert decode_access_token(token + "x") is None  # tampered signature
    forged = jwt.encode({"sub": str(user_id), "ver": 3, "exp": expires_at}, "an-attackers-own-secret-key-0123456789", algorithm="HS256")
    assert decode_access_token(forged) is None
    expired = jwt.encode({"sub": str(user_id), "ver": 3, "exp": int(time.time()) - 5}, settings.JWT_SECRET_KEY, algorithm="HS256")
    assert decode_access_token(expired) is None


# --- API helpers -------------------------------------------------------------------------------------------
@pytest.fixture
def api(db_session):
    """Unauthenticated client; use login() to get a token."""
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def login(api, email, password=TEST_PASSWORD):
    response = api.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# --- Setup, login and protection ----------------------------------------------------------------------------
def test_first_admin_setup_takes_over_existing_data(api, db_session, monkeypatch):
    orphan = Job(job_title="Created before accounts", description="x" * 40)
    db_session.add(orphan)
    db_session.commit()
    monkeypatch.setattr(user_service, "user_count", lambda db: 0)  # simulate an install with no accounts
    assert api.get("/api/auth/setup-status").json() == {"needs_setup": True}
    response = api.post("/api/auth/setup", json={"full_name": "Asha Admin", "email": "Admin@Example.com", "password": "Admin1234"})
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["role"] == "admin" and body["user"]["email"] == "admin@example.com"
    db_session.expire_all()
    assert db_session.get(Job, orphan.id).owner_id == uuid.UUID(body["user"]["id"])
    monkeypatch.undo()
    assert api.get("/api/auth/setup-status").json() == {"needs_setup": False}
    again = api.post("/api/auth/setup", json={"full_name": "Mallory", "email": "m@example.com", "password": "Admin1234"})
    assert again.status_code == 400 and "already been completed" in again.json()["detail"]


def test_login_success_and_generic_failures(api, hr_user):
    ok = api.post("/api/auth/login", json={"email": hr_user.email.upper(), "password": TEST_PASSWORD})
    assert ok.status_code == 200 and ok.json()["user"]["email"] == hr_user.email
    assert ok.json()["user"]["last_login_at"] is not None
    wrong_password = api.post("/api/auth/login", json={"email": hr_user.email, "password": "Wrong12345"})
    unknown_email = api.post("/api/auth/login", json={"email": "nobody@example.com", "password": "Wrong12345"})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == {"detail": "Invalid email or password."}


def test_password_hash_never_returned(api, hr_user):
    headers = login(api, hr_user.email)
    assert "password" not in api.get("/api/auth/me", headers=headers).text


@pytest.mark.parametrize("path", ["/api/jobs/", "/api/dashboard/stats", "/api/candidates/", "/api/analyses/", "/api/settings/", "/api/users/"])
def test_endpoints_require_login(api, path):
    assert api.get(path).status_code == 401
    assert api.get(path, headers={"Authorization": "Bearer not-a-real-token"}).status_code == 401


def test_health_and_setup_status_are_public(api):
    assert api.get("/api/health").status_code == 200
    assert api.get("/api/auth/setup-status").status_code == 200


def test_disabled_account_is_locked_out_immediately(api, make_user):
    admin, hr = make_user(role="admin"), make_user()
    hr_headers, admin_headers = login(api, hr.email), login(api, admin.email)
    assert api.get("/api/jobs/", headers=hr_headers).status_code == 200
    assert api.patch(f"/api/users/{hr.id}", json={"is_active": False}, headers=admin_headers).status_code == 200
    assert api.get("/api/jobs/", headers=hr_headers).status_code == 401  # existing token stops working
    failed = api.post("/api/auth/login", json={"email": hr.email, "password": TEST_PASSWORD})
    assert failed.status_code == 401 and "disabled" in failed.json()["detail"]
    api.patch(f"/api/users/{hr.id}", json={"is_active": True}, headers=admin_headers)
    assert api.get("/api/jobs/", headers=login(api, hr.email)).status_code == 200


def test_change_own_password_invalidates_old_sessions(api, hr_user):
    old = login(api, hr_user.email)
    wrong = api.post("/api/auth/change-password", json={"current_password": "Wrong12345", "new_password": "Brand2New"}, headers=old)
    assert wrong.status_code == 400
    weak = api.post("/api/auth/change-password", json={"current_password": TEST_PASSWORD, "new_password": "short"}, headers=old)
    assert weak.status_code == 400
    ok = api.post("/api/auth/change-password", json={"current_password": TEST_PASSWORD, "new_password": "Brand2New"}, headers=old)
    assert ok.status_code == 204
    assert api.get("/api/auth/me", headers=old).status_code == 401
    assert api.get("/api/auth/me", headers=login(api, hr_user.email, "Brand2New")).status_code == 200


# --- Admin account management ------------------------------------------------------------------------------------
def test_only_admins_manage_accounts(api, make_user):
    hr = make_user()
    hr_headers = login(api, hr.email)
    assert api.get("/api/users/", headers=hr_headers).status_code == 403
    denied = api.post("/api/users/", json={"full_name": "X Y", "email": "x@example.com", "password": "Passw0rd1"}, headers=hr_headers)
    assert denied.status_code == 403


def test_admin_creates_updates_and_resets_accounts(api, make_user):
    admin = make_user(role="admin")
    headers = login(api, admin.email)
    created = api.post("/api/users/", json={"full_name": "Ravi Kumar", "email": "Ravi@Example.com", "password": "Temp1234"}, headers=headers)
    assert created.status_code == 201 and created.json()["role"] == "hr" and created.json()["email"] == "ravi@example.com"
    new_id = created.json()["id"]
    duplicate = api.post("/api/users/", json={"full_name": "Ravi Two", "email": "ravi@example.com", "password": "Temp1234"}, headers=headers)
    assert duplicate.status_code == 400 and "already exists" in duplicate.json()["detail"]
    weak = api.post("/api/users/", json={"full_name": "Weak Pw", "email": "weak@example.com", "password": "abc"}, headers=headers)
    assert weak.status_code == 400
    bad_email = api.post("/api/users/", json={"full_name": "Bad Email", "email": "not-an-email", "password": "Temp1234"}, headers=headers)
    assert bad_email.status_code == 400

    renamed = api.patch(f"/api/users/{new_id}", json={"full_name": "Ravi K."}, headers=headers)
    assert renamed.json()["full_name"] == "Ravi K."
    assert api.post(f"/api/users/{new_id}/reset-password", json={"new_password": "Reset1234"}, headers=headers).status_code == 204
    assert api.post("/api/auth/login", json={"email": "ravi@example.com", "password": "Temp1234"}).status_code == 401
    assert api.post("/api/auth/login", json={"email": "ravi@example.com", "password": "Reset1234"}).status_code == 200
    assert any(u["email"] == "ravi@example.com" for u in api.get("/api/users/", headers=headers).json())


def test_admin_cannot_lock_themselves_out(api, make_user):
    admin = make_user(role="admin")
    headers = login(api, admin.email)
    for change in ({"is_active": False}, {"role": "hr"}):
        response = api.patch(f"/api/users/{admin.id}", json=change, headers=headers)
        assert response.status_code == 400 and "your own" in response.json()["detail"]


# --- Each HR only sees their own data ------------------------------------------------------------------------------
def test_hrs_cannot_see_each_others_data(api, make_user):
    alice, bob = make_user(name="Alice HR"), make_user(name="Bob HR")
    alice_h, bob_h = login(api, alice.email), login(api, bob.email)

    job = api.post("/api/jobs/", json={"job_title": "Alice's Python role", "description": JD, "required_skills": ["Python"]}, headers=alice_h).json()
    resume = ROOT / "sample_resumes" / "01_arjun_mehta_python_backend.pdf"
    upload = api.post("/api/resumes/upload", files=[("files", (resume.name, resume.read_bytes(), "application/pdf"))], headers=alice_h).json()
    candidate_id = upload["candidate_ids"][0]
    analysis = api.post(f"/api/analyze/{job['id']}", json={"candidate_ids": [candidate_id]}, headers=alice_h).json()

    # Alice sees everything she created.
    assert api.get(f"/api/results/{job['id']}", headers=alice_h).status_code == 200
    assert api.get("/api/dashboard/stats", headers=alice_h).json()["total_jobs"] == 1

    # Bob gets "not found" for every one of Alice's records, and his lists don't include them.
    for path in (f"/api/jobs/{job['id']}", f"/api/results/{job['id']}", f"/api/results/{job['id']}/export",
                 f"/api/candidates/{candidate_id}", f"/api/candidates/{candidate_id}/analysis/{job['id']}"):
        assert api.get(path, headers=bob_h).status_code == 404, path
    assert api.get("/api/jobs/", headers=bob_h).json() == []
    assert api.get("/api/candidates/", headers=bob_h).json()["total"] == 0
    assert api.get("/api/analyses/", headers=bob_h).json() == []
    bob_stats = api.get("/api/dashboard/stats", headers=bob_h).json()
    assert bob_stats["total_jobs"] == bob_stats["total_candidates"] == bob_stats["total_analyses"] == 0

    # Bob cannot change, delete or reuse Alice's records.
    assert api.put(f"/api/jobs/{job['id']}", json={"job_title": "Hacked"}, headers=bob_h).status_code == 404
    assert api.delete(f"/api/jobs/{job['id']}", headers=bob_h).status_code == 404
    assert api.delete(f"/api/candidates/{candidate_id}", headers=bob_h).status_code == 404
    bob_job = api.post("/api/jobs/", json={"job_title": "Bob's role", "description": JD}, headers=bob_h).json()
    reuse = api.post(f"/api/analyze/{bob_job['id']}", json={"candidate_ids": [candidate_id]}, headers=bob_h)
    assert reuse.status_code == 400 and "None of the selected resumes" in reuse.json()["detail"]
    other = api.get(f"/api/results/{bob_job['id']}", params={"analysis_id": analysis["analysis"]["id"]}, headers=bob_h)
    assert other.status_code == 404

    # Alice's data is untouched.
    assert api.get(f"/api/jobs/{job['id']}", headers=alice_h).json()["job_title"] == "Alice's Python role"


def test_admin_also_only_sees_own_candidates(api, make_user, db_session):
    admin, hr = make_user(role="admin"), make_user()
    hr_job = api.post("/api/jobs/", json={"job_title": "HR job", "description": JD}, headers=login(api, hr.email)).json()
    assert api.get(f"/api/jobs/{hr_job['id']}", headers=login(api, admin.email)).status_code == 404
    assert db_session.scalar(select(Job.owner_id).where(Job.id == uuid.UUID(hr_job["id"]))) == hr.id
