"""Vercel entry point for the ml-service.

Vercel looks for a FastAPI instance named `app` in app.py, so this just re-exports the
real service. Docker and local runs keep using service/app.py directly.
"""
from service.app import app  # noqa: F401
