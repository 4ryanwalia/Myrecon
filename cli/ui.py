"""
Terminal presentation primitives — colour, rules, key/value rows, progress.

Deliberately dependency-free. The backend installs Flask, requests and gunicorn
and nothing else; asking someone to `pip install rich` to read a username scan
would make the CLI heavier than the API it borrows from.

Two host quirks are handled here rather than at every call site:

  • Windows consoles need VT processing switched on before ANSI escapes mean
    anything, otherwise the user reads raw escape sequences instead of colour.
  • A console on a legacy code page raises UnicodeEncodeError on box-drawing
    characters, so the glyph set is chosen from what the stream can encode.

Progress and diagnostics go to stderr, results to stdout. That split is what
makes `myrecon username x --json > out.json` produce a clean file while the
scan still reports what it is doing on screen.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import textwrap

# ── Capability detection ─────────────────────────────────────────

_COLOR = False
_UNICODE = False

_CODES = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "grey": "\033[90m",
    "bright_red": "\033[91m",
}

# The wordmark is drawn out of its own letters — every M is made of Ms. It
# needs no box-drawing characters, so it survives a console on any code page,
# which the usual block-glyph banner does not.
_LETTERS = {
    "M": ("M     M", "MM   MM", "M M M M", "M  M  M", "M     M", "M     M"),
    "Y": ("Y     Y", " Y   Y ", "  Y Y  ", "   Y   ", "   Y   ", "   Y   "),
    "R": ("RRRRRR ", "R     R", "R     R", "RRRRRR ", "R    R ", "R     R"),
    "E": ("EEEEEEE", "E      ", "EEEEE  ", "E      ", "E      ", "EEEEEEE"),
    "C": (" CCCCC ", "C     C", "C      ", "C      ", "C     C", " CCCCC "),
    "O": (" OOOOO ", "O     O", "O     O", "O     O", "O     O", " OOOOO "),
    "N": ("N     N", "NN    N", "N N   N", "N  N  N", "N   N N", "N     N"),
}

_GLYPHS = {
    True: {"rule": "─", "bullet": "•", "arrow": "→", "tick": "✓", "cross": "✗",
           "warn": "!", "dot": "·", "bar_full": "█", "bar_empty": "░"},
    False: {"rule": "-", "bullet": "*", "arrow": "->", "tick": "+", "cross": "x",
            "warn": "!", "dot": ".", "bar_full": "#", "bar_empty": "."},
}


def _enable_windows_vt() -> None:
    """Turn on ANSI escape handling for the current console, if it needs it."""
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        for handle in (-11, -12):  # stdout, stderr
            mode = ctypes.c_uint32()
            h = kernel32.GetStdHandle(handle)
            if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
                # 0x0004 = ENABLE_VIRTUAL_TERMINAL_PROCESSING
                kernel32.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:  # noqa: BLE001 - cosmetics must never break a scan
        pass


def _can_encode_box() -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        "─•→✓".encode(encoding)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def configure(color: str = "auto") -> None:
    """
    Decide once whether this run is colourful, and in which alphabet.

    `color` is "auto", "always" or "never". NO_COLOR is honoured in auto mode
    because it is the convention every other CLI on the user's machine follows.
    """
    global _COLOR, _UNICODE

    if color == "always":
        _COLOR = True
    elif color == "never":
        _COLOR = False
    else:
        _COLOR = (
            sys.stdout.isatty()
            and os.environ.get("NO_COLOR") is None
            and os.environ.get("TERM") != "dumb"
        )

    if _COLOR:
        _enable_windows_vt()

    # Redirecting to a file or a pipe on Windows hands Python the ANSI code
    # page, where a single em dash in a bio is enough to end a scan with
    # UnicodeEncodeError after the network work is already done. Substituting
    # is the right trade: a report with one "?" in it beats no report.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:  # noqa: BLE001 - older or wrapped streams
            pass

    _UNICODE = _can_encode_box()


def glyph(name: str) -> str:
    return _GLYPHS[_UNICODE][name]


def width() -> int:
    return min(shutil.get_terminal_size((88, 24)).columns, 100)


# ── Text styling ─────────────────────────────────────────────────

def paint(text: str, *styles: str) -> str:
    if not _COLOR or not styles:
        return text
    prefix = "".join(_CODES.get(s, "") for s in styles)
    return prefix + text + _CODES["reset"]


def _out(text: str = "") -> None:
    print(text, file=sys.stdout)


def _err(text: str = "") -> None:
    # stdout is block-buffered when redirected while stderr is not, so without
    # this flush a warning can appear above the report it belongs to.
    sys.stdout.flush()
    print(text, file=sys.stderr)


# ── Blocks ───────────────────────────────────────────────────────

def logo_lines(word: str = "MYRECON") -> list:
    """The wordmark as text rows, or [] if this terminal is too narrow."""
    letters = [_LETTERS[c] for c in word if c in _LETTERS]
    if not letters:
        return []
    rows = len(letters[0])
    art = [" ".join(letter[row] for letter in letters) for row in range(rows)]
    return art if len(art[0]) + 4 <= width() else []


def banner(subtitle: str = "") -> None:
    """The wordmark in red, with a compact fallback for narrow terminals."""
    art = logo_lines()
    _out()
    if art:
        for row in art:
            _out("  " + paint(row, "bold", "bright_red"))
        _out()
        _out("  " + paint("OSINT from the terminal", "grey") +
             paint("   myrecon.xyz", "grey"))
    else:
        _out("  " + paint("MyRecon", "bold", "bright_red") +
             paint("   OSINT from the terminal", "grey"))
    if subtitle:
        _out("  " + paint(subtitle, "grey"))
    _out()


def heading(title: str, note_text: str = "") -> None:
    """A titled rule that opens a report."""
    rule = glyph("rule") * max(4, width() - len(title) - 3)
    _out()
    _out(paint(title + " ", "bold") + paint(rule, "grey"))
    if note_text:
        _out(paint("  " + note_text, "grey"))


def section(title: str) -> None:
    _out()
    _out(paint("  " + title, "bold", "blue"))


def kv(label: str, value, indent: int = 2, label_width: int = 18) -> None:
    """One `label  value` row. Empty values are skipped, not printed blank."""
    if value is None or value == "" or value == [] or value == {}:
        return
    if isinstance(value, bool):
        value = "yes" if value else "no"
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    pad = " " * indent
    _out(pad + paint(str(label).ljust(label_width), "grey") + str(value))


def bullet(text: str, indent: int = 2, style: str = "") -> None:
    pad = " " * indent
    mark = paint(glyph("bullet"), "grey")
    body = paint(text, style) if style else text
    _out(pad + mark + " " + body)


def line(text: str = "", indent: int = 2, style: str = "") -> None:
    pad = " " * indent
    _out(pad + (paint(text, style) if style else text))


def wrapped(text: str, indent: int = 2) -> None:
    for chunk in textwrap.wrap(text, width=width() - indent - 2) or [""]:
        line(chunk, indent)


def table(headers, rows, indent: int = 2) -> None:
    """Left-aligned columns sized to their content; the last column runs on."""
    if not rows:
        return
    widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    pad = " " * indent
    head = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
    _out(pad + paint(head.rstrip(), "grey"))
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            text = str(cell)
            cells.append(text.ljust(widths[i]) if i < len(row) - 1 else text)
        _out(pad + "  ".join(cells).rstrip())


def count_line(label: str, value: int, style: str = "") -> None:
    _out("  " + paint(str(value).rjust(5), style or "bold") + "  " + paint(label, "grey"))


def note(text: str) -> None:
    _err(paint("  " + glyph("warn") + " " + text, "yellow"))


def error(text: str) -> None:
    _err(paint("  " + glyph("cross") + " " + text, "red"))


def success(text: str) -> None:
    _err(paint("  " + glyph("tick") + " " + text, "green"))


def dump_json(payload) -> None:
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False, default=str)
    sys.stdout.write("\n")


# ── Live progress ────────────────────────────────────────────────

class Progress:
    """
    A single self-overwriting status line on stderr.

    Scans take tens of seconds. Without this the terminal sits blank and the
    honest question is whether the tool has hung; with it, every phase the
    engine already reports to the web UI shows up here too.
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and sys.stderr.isatty()
        self._last_len = 0

    def update(self, event: dict) -> None:
        if not self.enabled or event.get("type") != "progress":
            return
        percent = int(event.get("percent") or 0)
        phase = event.get("phase") or ""
        detail = event.get("detail") or ""

        filled = max(0, min(20, int(percent / 5)))
        bar = glyph("bar_full") * filled + glyph("bar_empty") * (20 - filled)
        text = "  " + bar + " " + str(percent).rjust(3) + "%  " + phase
        if detail:
            text += " " + glyph("dot") + " " + detail

        text = text[: width()]
        sys.stderr.write("\r" + text.ljust(self._last_len))
        sys.stderr.flush()
        self._last_len = len(text)

    def clear(self) -> None:
        if self.enabled and self._last_len:
            sys.stderr.write("\r" + " " * self._last_len + "\r")
            sys.stderr.flush()
            self._last_len = 0
