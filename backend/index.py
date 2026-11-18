"""
Vercel entry point. Vercel looks for an ASGI application named `app` in index.py and
serves every request through it (the same FastAPI app used locally with uvicorn).
"""
from app.main import app  # noqa: F401
