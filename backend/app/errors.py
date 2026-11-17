"""
Global exception handlers: turn known errors into clear JSON responses with the
right HTTP status, and never leak stack traces or credentials to the client.

    {"detail": "human readable message"}
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

from app.database import describe_db_error
from app.nlp.jd_analyzer import JDAnalysisError
from app.parser import DocumentParseError
from app.services.analysis_service import AnalysisError
from app.services.resume_service import UploadError
from app.services.user_service import AccountError, AuthenticationError
from app.utils.file_validator import FileValidationError

logger = logging.getLogger("talentmatch.errors")


def _json(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AnalysisError)
    @app.exception_handler(UploadError)
    @app.exception_handler(AccountError)
    async def bad_request(_: Request, exc: Exception):
        return _json(status.HTTP_400_BAD_REQUEST, str(exc))

    @app.exception_handler(AuthenticationError)
    async def unauthorized(_: Request, exc: AuthenticationError):
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": str(exc)},
                            headers={"WWW-Authenticate": "Bearer"})

    @app.exception_handler(JDAnalysisError)
    @app.exception_handler(FileValidationError)
    @app.exception_handler(DocumentParseError)
    async def unprocessable(_: Request, exc: Exception):
        return _json(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))

    @app.exception_handler(IntegrityError)
    async def conflict(_: Request, exc: IntegrityError):
        logger.warning("Integrity error: %s", describe_db_error(exc))
        return _json(status.HTTP_409_CONFLICT, "The data conflicts with existing records or violates a database rule.")

    @app.exception_handler(OperationalError)
    @app.exception_handler(DBAPIError)
    async def database_unavailable(_: Request, exc: Exception):
        logger.error("Database error: %s", describe_db_error(exc))
        return _json(status.HTTP_503_SERVICE_UNAVAILABLE, "The database is temporarily unavailable. Please try again.")

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception):
        logger.exception("Unhandled error: %s", type(exc).__name__)
        return _json(status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred. Please try again.")
