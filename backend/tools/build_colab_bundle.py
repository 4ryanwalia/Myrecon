"""Build a reviewed source-only worker ZIP and ready-to-upload CPU notebook."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

FILES = (
    "services/scan_engine.py", "tools/colab_worker.py", "modules/sweep.py",
    "modules/username_checker.py", "modules/profile_identity.py", "core/netguard.py",
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
    cells = []

    def markdown(text):
        cells.append({"id": f"cell-{len(cells)}", "cell_type": "markdown", "metadata": {}, "source": text.splitlines(True)})

    def code(text):
        cells.append({"id": f"cell-{len(cells)}", "cell_type": "code", "metadata": {}, "source": text.splitlines(True),
                      "execution_count": None, "outputs": []})

    markdown("# MyRecon CPU scan worker\n\n"
        "Use **Runtime > Run all** after uploading the matching ZIP. Enter the hidden token prompt "
        "once and the worker starts automatically for up to **10 hours**. Google can end the runtime earlier. "
        "Render owns login, billing, "
        "storage and the fallback. This notebook does not host a public server or bypass session limits.\n\n"
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
        "Open the Files sidebar and use **Upload to session storage** to upload "
        "`myrecon-colab-worker.zip` before running the next cell. The hash check binds this notebook "
        "to the reviewed bundle. For later sessions you can keep the ZIP in a private Drive folder "
        "and load it manually; Drive stores files and Colab runs them.")
    code("from pathlib import Path\n"
         "import hashlib, zipfile\n"
         "name = Path('/content/myrecon-colab-worker.zip')\n"
         "assert name.is_file(), 'Upload the worker ZIP using Files > Upload to session storage'\n"
         f"assert hashlib.sha256(name.read_bytes()).hexdigest() == '{digest}', 'Wrong worker bundle'\n"
         "worker_root = Path('/content/myrecon-worker')\n"
         "worker_root.mkdir(exist_ok=True)\n"
         "with zipfile.ZipFile(name) as bundle:\n"
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
         "worker_token = getpass.getpass('Dedicated SCAN_WORKER_TOKEN (hidden, not saved): ').strip()\n"
         f"worker = Worker(api_origin, worker_token, concurrency=16, worker_label={worker_label!r})\n"
         "worker_token = ''\n"
         "try:\n"
         "    worker.run(duration_minutes=600)\n"
         "finally:\n"
         "    del worker\n")
    markdown("## Verification\n"
        "Start one scan in MyRecon, check progress and completion, then stop this worker during "
        "a second scan and confirm Render resumes it after lease expiry. Compare checked platforms "
        "and results, verify one allowance was spent, and watch Render CPU/memory. "
        "A notebook connection alone does not establish production reliability. "
        "Colab sessions and available resources are limited; restart manually when necessary.")
    notebook = {"nbformat": 4, "nbformat_minor": 5,
                "metadata": {"colab": {"name": "MyRecon CPU Scan Worker.ipynb"},
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
