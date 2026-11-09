"""Gunicorn configuration for Render deployment."""


def post_worker_init(worker):
    """Start background services safely inside the worker process after fork."""
    try:
        from services.colab_recovery import ensure_started
        ensure_started()
    except Exception:
        pass
