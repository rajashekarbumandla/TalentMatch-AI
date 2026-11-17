"""
FastAPI dependencies that protect the API.

    current_user: User = Depends(get_current_user)   -> any logged-in, active HR
    admin: User = Depends(require_admin)             -> admins only

A request is rejected with 401 if the token is missing, invalid, expired, belongs to a
disabled account, or was issued before the user's last password change (token_version).
"""
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.database import get_db
from app.models import User

bearer = HTTPBearer(auto_error=False, description="Log in via POST /api/auth/login and paste the access_token here.")

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Your session has expired or is invalid. Please log in again.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please log in.", headers={"WWW-Authenticate": "Bearer"})
    claims = decode_access_token(credentials.credentials)
    if claims is None:
        raise _UNAUTHORIZED
    try:
        user = db.get(User, uuid.UUID(claims["sub"]))
    except ValueError:
        raise _UNAUTHORIZED from None
    if user is None or not user.is_active or user.token_version != claims["ver"]:
        raise _UNAUTHORIZED
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an admin can manage accounts.")
    return user
