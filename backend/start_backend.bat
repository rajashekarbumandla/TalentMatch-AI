@echo off
REM Starts the TalentMatch AI API on http://localhost:8000 (Swagger: /docs).
REM Uses "python -m uvicorn" because Windows Smart App Control blocks the uvicorn.exe launcher.
cd /d "%~dp0"
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
