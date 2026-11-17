"""
HR accounts: first-time admin setup, login, and account management by the admin.

Rules
- The very first account is created through a one-time "setup" step and becomes admin.
  It also takes ownership of any data that existed before accounts were introduced.
- After that there is no public sign-up: only an admin can create accounts.
- Accounts are disabled rather than deleted (their data stays intact). Disabling an
  account or changing its password bumps token_version, logging it out everywhere.
- An admin cannot disable or demote themselves, so the system can't be locked out.
"""
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.security import burn_password_check, hash_password, password_problem, verify_password
from app.models import Candidate, Job, User

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
ROLES = ("admin", "hr")


class AccountError(ValueError):
    """Invalid account request; the message is safe to show to the user."""


class AuthenticationError(ValueError):
    """Wrong email/password or disabled account."""


def normalize_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise AccountError("Enter a valid email address.")
    return email


def _validate_password(password: str) -> None:
    problem = password_problem(password or "")
    if problem:
        raise AccountError(problem)


def user_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User)) or 0


def needs_setup(db: Session) -> bool:
    return user_count(db) == 0


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalars(select(User).where(User.email == email.strip().lower())).first()


def create_user(db: Session, full_name: str, email: str, password: str, role: str = "hr", commit: bool = True) -> User:
    full_name = " ".join((full_name or "").split())
    if len(full_name) < 2:
        raise AccountError("Enter the person's full name.")
    if role not in ROLES:
        raise AccountError("Role must be admin or hr.")
    email = normalize_email(email)
    _validate_password(password)
    if get_by_email(db, email):
        raise AccountError("An account with this email already exists.")
    user = User(full_name=full_name, email=email, password_hash=hash_password(password), role=role)
    db.add(user)
    if commit:
        db.commit()
        db.refresh(user)
    else:
        db.flush()
    return user


def setup_first_admin(db: Session, full_name: str, email: str, password: str) -> User:
    """One-time setup: create the admin and give them any data created before accounts existed."""
    if not needs_setup(db):
        raise AccountError("Setup has already been completed. Ask your admin for an account.")
    admin = create_user(db, full_name, email, password, role="admin", commit=False)
    for model in (Job, Candidate):
        db.execute(update(model).where(model.owner_id.is_(None)).values(owner_id=admin.id))
    db.commit()
    db.refresh(admin)
    return admin


def authenticate(db: Session, email: str, password: str) -> User:
    """Check credentials. The same generic error is used for 'no such email' and 'wrong password'."""
    user = get_by_email(db, email or "")
    if user is None:
        burn_password_check(password or "")  # equal timing: don't reveal which emails exist
        raise AuthenticationError("Invalid email or password.")
    if not verify_password(password or "", user.password_hash):
        raise AuthenticationError("Invalid email or password.")
    if not user.is_active:
        raise AuthenticationError("This account has been disabled. Contact your admin.")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return user


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at)))


def get_user(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def update_user(db: Session, acting_admin: User, user: User, *, full_name=None, role=None, is_active=None) -> User:
    if user.id == acting_admin.id and (is_active is False or (role is not None and role != "admin")):
        raise AccountError("You cannot disable your own account or remove your own admin role.")
    if full_name is not None:
        full_name = " ".join(full_name.split())
        if len(full_name) < 2:
            raise AccountError("Enter the person's full name.")
        user.full_name = full_name
    if role is not None:
        if role not in ROLES:
            raise AccountError("Role must be admin or hr.")
        user.role = role
    if is_active is not None and is_active != user.is_active:
        user.is_active = is_active
        user.token_version += 1  # disabling logs the user out everywhere
    db.commit()
    db.refresh(user)
    return user


def set_password(db: Session, user: User, new_password: str) -> None:
    _validate_password(new_password)
    user.password_hash = hash_password(new_password)
    user.token_version += 1  # every existing login token stops working
    db.commit()


def change_own_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password or "", user.password_hash):
        raise AccountError("Your current password is incorrect.")
    if current_password == new_password:
        raise AccountError("Choose a password different from your current one.")
    set_password(db, user, new_password)
