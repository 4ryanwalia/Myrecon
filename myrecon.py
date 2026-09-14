#!/usr/bin/env python3
"""
MyRecon terminal client launcher.

    python myrecon.py username torvalds
    python myrecon.py --help

Exists so the CLI runs from a clone with nothing installed and no packaging
step — `python -m cli` works identically for anyone who prefers it. The real
implementation is in cli/, and the lookups themselves are backend/services,
unchanged and shared with the API.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli.__main__ import main  # noqa: E402 - must follow the sys.path line above

if __name__ == "__main__":
    sys.exit(main())
