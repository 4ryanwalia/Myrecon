"""Build a reviewed source-only worker ZIP and ready-to-upload CPU notebook."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import zipfile

FILES = (
    "services/scan_engine.py", "tools/colab_worker.py", "modules/sweep.py",
    "modules/username_checker.py", "modules/profile_identity.py", "modules/username_integrations.py", "core/netguard.py",
    "data/platforms_full.json", "data/platforms_extra.json",
)


def build(destination, worker_label="Colab worker", notebook_name="MyRecon CPU Scan Worker.ipynb"):
    root = Path(__file__).resolve().parents[1]
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / "myrecon-colab-worker.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in FILES:
            bundle.writestr(zipfile.ZipInfo(name), (root / name).read_bytes().replace(b"\r\n", b"\n"),
                            compress_type=zipfile.ZIP_DEFLATED)
        for package in ("services", "tools", "modules", "core"):
            bundle.writestr(zipfile.ZipInfo(package + "/__init__.py"), "", compress_type=zipfile.ZIP_DEFLATED)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    embedded_bundle = base64.b64encode(archive.read_bytes()).decode("ascii")
    cells = []

    def markdown(text):
        cells.append({"id": f"cell-{len(cells)}", "cell_type": "markdown", "metadata": {}, "source": text.splitlines(True)})

    def code(text):
        cells.append({"id": f"cell-{len(cells)}", "cell_type": "code", "metadata": {}, "source": text.splitlines(True),
                      "execution_count": None, "outputs": []})

    markdown("# MyRecon CPU scan worker\n\n"
        "Use **Runtime > Run all**. The worker files are included in this notebook and load automatically. The dedicated token is read "
        "from Colab Secrets when **SCAN_WORKER_TOKEN** has notebook access enabled; otherwise a hidden prompt asks for it. "
        "The worker starts automatically for up to **10 hours**. Google can end the runtime earlier. "
        "Render owns login, billing, "
        "storage and the fallback. This notebook does not host a public server or bypass session limits.\n\n"
        "Keep the final worker cell running. Closing the Colab tab can make Colab show **Connect** again. "
        "If the runtime is still running, connecting reattaches the page; if it ended, choose **Connect** and "
        "use **Runtime > Run all** again. MyRecon does not bypass Colab session limits or reconnect a stopped runtime.\n\n"
        "Choose **Runtime > Change runtime type > CPU**. Keep this notebook private. "
        "The ZIP contains scanner source and catalogue data, no account or payment secrets. "
        "An interrupted session leaves committed checkpoints on Render's persistent store.\n\n"
        "First deploy the matching backend and follow `docs/colab-scan-worker.md`. "
        "Use only the dedicated worker token; never enter Firebase or payment keys here.")
    code("import importlib.metadata, subprocess, sys\n"
         "colab_dependencies = importlib.metadata.requires('google-colab') or []\n"
         "requests_requirement = next((r for r in colab_dependencies "
         "if r.lower().startswith('requests')), 'requests')\n"
         "subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', "
         "requests_requirement, 'urllib3'])\n")
    code("import os, platform\n"
         "print('Logical CPUs:', os.cpu_count())\n"
         "print('Architecture:', platform.machine())\n"
         "import psutil\n"
         "print('RAM GiB:', round(psutil.virtual_memory().total / 1024**3, 1))\n")
    markdown("## Load the matching worker bundle\n"
        "The next cell loads the bundled scanner automatically. No ZIP upload or Drive access is needed. "
        "The hash check binds this notebook to the reviewed worker files.")
    code("from pathlib import Path\n"
         "import base64, hashlib, io, zipfile\n"
         f"bundle_bytes = base64.b64decode({embedded_bundle!r}, validate=True)\n"
         f"assert hashlib.sha256(bundle_bytes).hexdigest() == '{digest}', 'Wrong worker bundle'\n"
         "name = Path('/content/myrecon-colab-worker.zip')\n"
         "name.write_bytes(bundle_bytes)\n"
         "worker_root = Path('/content/myrecon-worker')\n"
         "worker_root.mkdir(exist_ok=True)\n"
         "with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as bundle:\n"
         "    for entry in bundle.infolist():\n"
         "        target = (worker_root / entry.filename).resolve()\n"
         "        assert target.is_relative_to(worker_root.resolve()), 'Invalid ZIP path'\n"
         "    bundle.extractall(worker_root)\n"
         "print('Worker bundle verified and extracted')\n")
    code("import sys, getpass\n"
         "sys.path.insert(0, str(worker_root))\n"
         "import importlib\n"
         "from tools import colab_worker\n"
         "Worker = importlib.reload(colab_worker).Worker\n"
         "api_origin = 'https://myrecon.onrender.com'\n"
         "from google.colab import userdata\n"
         "try:\n"
         "    worker_token = userdata.get('SCAN_WORKER_TOKEN').strip()\n"
         "except (userdata.SecretNotFoundError, userdata.NotebookAccessError, userdata.TimeoutException):\n"
         "    print('To avoid this prompt next time, save SCAN_WORKER_TOKEN in Colab Secrets and enable Notebook access.')\n"
         "    worker_token = getpass.getpass('Dedicated SCAN_WORKER_TOKEN (hidden, not saved): ').strip()\n"
         f"worker = Worker(api_origin, worker_token, concurrency=16, worker_label={worker_label!r})\n"
         "worker_token = ''\n"
         "try:\n"
         "    worker.run(duration_minutes=600)\n"
         "finally:\n"
         "    del worker\n")
    markdown("## Verification\n"
        "After the first poll, the worker cell prints **Live status confirmed**. Open the Worker Console and expect "
        "the matching label within about 10 seconds. Start one scan in MyRecon, check progress and completion, then stop this worker during "
        "a second scan and confirm Render resumes it after lease expiry. Compare checked platforms "
        "and results, verify one allowance was spent, and watch Render CPU/memory. "
        "A notebook connection alone does not establish production reliability. "
        "Colab sessions and available resources are limited; restart manually when necessary.")
    notebook = {"nbformat": 4, "nbformat_minor": 5,
                "metadata": {"colab": {"name": notebook_name},
                             "kernelspec": {"name": "python3", "display_name": "Python 3"}},
                "cells": cells}
    (destination / notebook_name).write_text(json.dumps(notebook, indent=2), encoding="utf-8")
    (destination / "SHA256.txt").write_text(digest + "  " + archive.name + "\n", encoding="utf-8")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(Path(__file__).resolve().parents[2] / "output" / "colab-worker"))
    parser.add_argument("--worker-label", default="Colab worker")
    parser.add_argument("--notebook-name", default="MyRecon CPU Scan Worker.ipynb")
    args = parser.parse_args()
    print(build(args.output, worker_label=args.worker_label, notebook_name=args.notebook_name))
