"""Gunicorn configuration for Render deployment."""

# Active scans are memory-only and all worker API calls must reach this process.
workers = 1


def post_worker_init(worker):
    """Start background services safely inside the worker process after fork."""
    try:
        from core.privacy_cleanup import ensure_started as start_cleanup
        start_cleanup()
        from services.colab_recovery import ensure_started
        ensure_started()
    except Exception:
        pass
