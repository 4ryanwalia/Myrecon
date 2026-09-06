"""
Local development entry point.

`python app.py` starts the server but leaves FLASK_ENV unset, and config.py
defaults that to "production" — which swaps the CORS allowlist to the live
domains and makes every request from a localhost frontend fail preflight. The
symptom ("Could not reach the MyRecon API") looks like the backend is down
when it is actually running fine and refusing the origin.

Setting the variable has to happen before `app` is imported, because config.py
reads the environment at import time. Hence this file rather than a flag.

    python backend/dev.py

Production is unaffected: Render runs `gunicorn wsgi:app` and never loads this.
"""

import os

os.environ.setdefault("FLASK_ENV", "development")

from app import app  # noqa: E402 - must follow the env default above

if __name__ == "__main__":
    # The reloader forks a second process, which leaves supervisors tracking
    # the wrong PID. Off by default; restart manually after backend edits.
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", 5000)),
        debug=True,
        use_reloader=False,
    )
