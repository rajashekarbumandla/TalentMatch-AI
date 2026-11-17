"""Login endpoints: first-time admin setup, login, current user, change own password."""
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.security import create_access_token
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, PasswordChange, SetupRequest, SetupStatus, TokenResponse, UserRead
from app.services import user_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def token_response(user: User) -> TokenResponse:
    token, expires_at = create_access_token(user.id, user.token_version)
    return TokenResponse(access_token=token, expires_at=expires_at, user=UserRead.model_validate(user))


@router.get("/setup-status", response_model=SetupStatus, summary="Is the one-time admin setup still needed?")
def setup_status(db: Session = Depends(get_db)):
    return SetupStatus(needs_setup=user_service.needs_setup(db))


@router.post("/setup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED,
             summary="Create the first (admin) account - only works while no accounts exist")
def setup(payload: SetupRequest, db: Session = Depends(get_db)):
    admin = user_service.setup_first_admin(db, payload.full_name, payload.email, payload.password)
    admin = user_service.authenticate(db, payload.email, payload.password)  # records the first login
    return token_response(admin)


@router.post("/login", response_model=TokenResponse, summary="Log in with email and password")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return token_response(user_service.authenticate(db, payload.email, payload.password))


@router.get("/me", response_model=UserRead, summary="The logged-in HR")
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT,
             summary="Change your own password (logs out your other sessions)")
def change_password(payload: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_service.change_own_password(db, user, payload.current_password, payload.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
