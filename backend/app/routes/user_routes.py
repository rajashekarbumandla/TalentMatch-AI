"""Account management (admin only): list, create, update/disable, reset password."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models import User
from app.schemas import PasswordReset, UserCreate, UserRead, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/api/users", tags=["Accounts (admin)"])


def get_user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = user_service.get_user(db, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found.")
    return user


@router.get("/", response_model=list[UserRead], summary="All HR accounts")
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return user_service.list_users(db)


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="Create an HR account")
def create_user(payload: UserCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return user_service.create_user(db, payload.full_name, payload.email, payload.password, payload.role)


@router.patch("/{user_id}", response_model=UserRead, summary="Rename, change role, disable or re-enable an account")
def update_user(user_id: uuid.UUID, payload: UserUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return user_service.update_user(db, admin, get_user_or_404(db, user_id), **payload.model_dump(exclude_unset=True))


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT,
             summary="Set a new password for an account (logs that account out everywhere)")
def reset_password(user_id: uuid.UUID, payload: PasswordReset, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    user_service.set_password(db, get_user_or_404(db, user_id), payload.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
