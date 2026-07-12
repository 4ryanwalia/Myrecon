"""Gunicorn entry point for Render: `gunicorn wsgi:app`."""

from app import app

__all__ = ["app"]
