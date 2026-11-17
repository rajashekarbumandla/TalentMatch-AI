"""
FastAPI routers, one module per resource. Routes stay thin: they validate input and call services.

Every router except /api/auth and /api/health requires a logged-in HR, and each HR only
ever sees their own jobs, candidates and analyses.
"""
from app.routes import (
    analysis_routes,
    auth_routes,
    candidate_routes,
    dashboard_routes,
    job_routes,
    resume_routes,
    settings_routes,
    user_routes,
)

ALL_ROUTERS = [
    auth_routes.router,
    user_routes.router,
    job_routes.router,
    resume_routes.router,
    analysis_routes.router,
    candidate_routes.router,
    dashboard_routes.router,
    settings_routes.router,
]
