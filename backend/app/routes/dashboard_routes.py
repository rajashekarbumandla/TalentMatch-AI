"""Dashboard statistics endpoint (the logged-in HR's own numbers)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import DashboardStats
from app.services.dashboard_service import get_dashboard_stats

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats, summary="Your totals, score distribution, recent activity")
def dashboard_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Every number is computed from this HR's data at request time; nothing is hardcoded."""
    return get_dashboard_stats(db, owner_id=user.id)
