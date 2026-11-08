"""One managed CPU session using Google's pinned Colab CLI library.

Run only in .venv/colab. Never logs credentials, remote code or provider errors.
The parent renews a durable lease and supplies only the dedicated worker token.
"""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid


def notebook_id(token):
    # Stable across Render restarts; never attaches to the user's other notebooks.
    digest = hmac.new(token.encode(), b"myrecon-colab-auto-cpu-v1", hashlib.sha256).digest()
    return uuid.UUID(bytes=digest[:16])


def bootstrap(archive, origin, token):
    payload = base64.b64encode(archive).decode("ascii")
    digest = hashlib.sha256(archive).hexdigest()
    return f'''
import base64, hashlib, importlib.metadata, io, pathlib, subprocess, sys, zipfile
requirements = importlib.metadata.requires('google-colab') or []
requests_requirement = next((r for r in requirements if r.lower().startswith('requests')), 'requests')
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', requests_requirement, 'urllib3'])
payload = base64.b64decode({payload!r}, validate=True)
assert hashlib.sha256(payload).hexdigest() == {digest!r}
root = pathlib.Path('/content/myrecon-auto-worker')
root.mkdir(exist_ok=True)
with zipfile.ZipFile(io.BytesIO(payload)) as bundle:
    assert all((root / item.filename).resolve().is_relative_to(root.resolve()) for item in bundle.infolist())
    bundle.extractall(root)
sys.path.insert(0, str(root))
from tools.colab_worker import Worker
worker = Worker({origin!r}, {token!r}, concurrency=16, worker_label='Auto CPU worker')
try:
    worker.run(duration_minutes=600)
finally:
    del worker
'''


def run():
    # Imports are intentionally isolated from Flask and GHunt dependencies.
    from colab_cli.client import Accelerator, Client, PostAssignmentResponse, Prod, Variant
    from colab_cli.runtime import ColabRuntime
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.credentials import Credentials
    from build_colab_bundle import build

    try:
        info = json.loads(os.environ["COLAB_GOOGLE_CREDENTIALS_JSON"])
        if info.get("type") != "authorized_user":
            return 78
        token = os.environ["SCAN_WORKER_TOKEN"].strip()
        if len(token) < 32:
            return 78
        # Fix the refresh destination; never trust a supplied token_uri.
        credentials = Credentials(None, refresh_token=info["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=info["client_id"], client_secret=info["client_secret"])
        origin = os.getenv("COLAB_API_ORIGIN", "https://myrecon.onrender.com")
        from urllib.parse import urlsplit
        parts = urlsplit(origin)
        if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
                or parts.path not in ("", "/") or parts.query or parts.fragment):
            return 78
    except (KeyError, ValueError, TypeError):
        return 78

    session = AuthorizedSession(credentials)
    client = Client(Prod(), session)
    endpoint = None
    try:
        balance = client.get_consumption_user_info().paid_compute_units_balance
        if balance <= 0:
            return 75  # Wait for included units; never purchase or change accounts.
        assignment = client.assign(notebook_id(token), variant=Variant.DEFAULT,
                                   accelerator=Accelerator.NONE)
        endpoint = assignment.endpoint
        # Reap only our stable assignment, including any process orphaned by a
        # previous Render shutdown. Other notebook sessions are never stopped.
        if not isinstance(assignment, PostAssignmentResponse):
            client.unassign(endpoint)
            endpoint = None
            assignment = client.assign(notebook_id(token), variant=Variant.DEFAULT,
                                       accelerator=Accelerator.NONE)
            endpoint = assignment.endpoint
        with tempfile.TemporaryDirectory(prefix="myrecon-colab-") as directory:
            archive = build(Path(directory)).read_bytes()
        proxy = assignment.runtime_proxy_info
        runtime = ColabRuntime(proxy.url, proxy.token)
        # No CLI history logger or file containing remote code/worker credentials.
        outputs = runtime.execute_code(bootstrap(archive, origin, token), timeout=0)
        return 1 if any(item.get("output_type") == "error" for item in outputs) else 0
    except Exception as error:
        from google.auth.exceptions import RefreshError
        return 78 if isinstance(error, RefreshError) else 1
    finally:
        if endpoint:
            try:
                client.unassign(endpoint)
            except Exception:
                pass
        session.close()


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception:
        sys.exit(1)
