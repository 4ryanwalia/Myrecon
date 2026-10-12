#!/usr/bin/env bash
set -euo pipefail

# Keep GHunt's older httpx/protobuf constraints out of the application runtime.
python -m pip install --upgrade pip==26.2.1
python -m pip install -r requirements.txt
python -m venv .venv/ghunt
.venv/ghunt/bin/python -m pip install --upgrade pip==26.2.1
.venv/ghunt/bin/python -m pip install -r requirements-ghunt.txt
