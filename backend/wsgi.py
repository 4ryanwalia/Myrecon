"""Gunicorn entry point for Render: `gunicorn wsgi:app`."""

from app import app

_recovery_started = False


def application(environ, start_response):
    global _recovery_started
    if not _recovery_started:
        _recovery_started = True
        try:
            from services.colab_recovery import ensure_started
            ensure_started()
        except Exception:
            pass
    return app(environ, start_response)


class _AppProxy:
    def __init__(self, inner):
        self._inner = inner

    def __call__(self, environ, start_response):
        return application(environ, start_response)

    def __getattr__(self, name):
        return getattr(self._inner, name)


app = _AppProxy(app)

__all__ = ["app"]
