"""
MyRecon terminal client.

The same investigation engine the website runs, driven from a shell instead of
a browser. Commands call `backend/services/*` directly — the very functions the
Flask routes wrap — so a CLI answer and a myrecon.xyz answer come from one
implementation and cannot drift apart.

No server is involved: `python myrecon.py username torvalds` does the work in
this process. That also means the CLI inherits the platform's rule that every
source is free and keyless, and that the two commands needing a Google Custom
Search key (`name`, `image`) say so instead of failing obscurely.
"""

__all__ = ["main"]


def main(argv=None) -> int:
    from cli.__main__ import main as _main
    return _main(argv)
