"""Gunicorn entry point for Render: `gunicorn wsgi:app`."""

from app import app

from services.colab_recovery import ensure_started

# Runs in the Gunicorn worker (no --preload), including after Render wakes up.
ensure_started()

__all__ = ["app"]
