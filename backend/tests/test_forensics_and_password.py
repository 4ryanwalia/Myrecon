"""Tests for document metadata forensics (.docx/.xlsx/.pptx/.pdf) and CLI password breach check."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
import zlib

import pytest

from cli import __main__ as cli_main
from modules import image_forensics, password_check


def _make_ooxml_bytes(
    core_xml: str | None = None,
    app_xml: str | None = None,
    body_entry: str = "word/document.xml",
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(body_entry, "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'/>")
        if core_xml is not None:
            zf.writestr("docProps/core.xml", core_xml)
        if app_xml is not None:
            zf.writestr("docProps/app.xml", app_xml)
    return buf.getvalue()


SAMPLE_CORE_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties
    xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Incident Response Plan</dc:title>
  <dc:subject>Security Operations</dc:subject>
  <dc:creator>Ada Lovelace</dc:creator>
  <cp:keywords>osint, forensics</cp:keywords>
  <dc:description>Internal draft</dc:description>
  <cp:lastModifiedBy>Charles Babbage</cp:lastModifiedBy>
  <cp:revision>7</cp:revision>
  <dcterms:created xsi:type="dcterms:W3CDTF">2026-02-10T09:15:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">2026-02-12T18:45:30Z</dcterms:modified>
</cp:coreProperties>
"""

SAMPLE_APP_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>Microsoft Office Word</Application>
  <AppVersion>16.0000</AppVersion>
  <Company>Analytical Engine Ltd</Company>
  <Pages>4</Pages>
</Properties>
"""


# ── Document Metadata Forensics ──────────────────────────────────


def test_docx_metadata_forensics():
    raw = _make_ooxml_bytes(SAMPLE_CORE_XML, SAMPLE_APP_XML, body_entry="word/document.xml")
    report = image_forensics.analyse(raw, filename="plan.docx")

    assert report["file"]["format"] == "DOCX"
    assert report["file"]["mime"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert report["file"]["sha256"] == hashlib.sha256(raw).hexdigest()

    doc = report["document"]
    assert doc["present"] is True
    assert doc["author"] == "Ada Lovelace"
    assert doc["last_modified_by"] == "Charles Babbage"
    assert doc["creator_software"] == "Microsoft Office Word (16.0000)"
    assert doc["company"] == "Analytical Engine Ltd"
    assert doc["title"] == "Incident Response Plan"
    assert doc["subject"] == "Security Operations"
    assert doc["keywords"] == "osint, forensics"
    assert doc["revision"] == 7
    assert doc["pages"] == 4
    assert doc["created"] == "2026-02-10T09:15:00Z"
    assert doc["modified"] == "2026-02-12T18:45:30Z"

    codes = {s["code"] for s in report["signals"]}
    assert "author_present" in codes
    assert "multiple_authors" in codes
    assert "editing_software" in codes
    assert "company_present" in codes
    assert "timestamp_mismatch" in codes


@pytest.mark.parametrize(
    ("entry", "filename", "expected_format", "expected_mime"),
    [
        (
            "xl/workbook.xml",
            "budget.xlsx",
            "XLSX",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        (
            "ppt/presentation.xml",
            "deck.pptx",
            "PPTX",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
    ],
)
def test_xlsx_and_pptx_metadata_forensics(entry, filename, expected_format, expected_mime):
    raw = _make_ooxml_bytes(SAMPLE_CORE_XML, None, body_entry=entry)
    report = image_forensics.analyse(raw, filename=filename)

    assert report["file"]["format"] == expected_format
    assert report["file"]["mime"] == expected_mime
    assert report["document"]["author"] == "Ada Lovelace"
    assert report["document"]["created"] == "2026-02-10T09:15:00Z"


def test_pdf_header_and_info_metadata_forensics():
    raw = (
        b"%PDF-1.7\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog >>\n"
        b"endobj\n"
        b"2 0 obj\n"
        b"<< /Author (Grace Hopper)\n"
        b"   /Creator (LibreOffice 7.6)\n"
        b"   /Producer (macOS Version 14.2 (Build 23C64) Quartz PDFContext)\n"
        b"   /Title (Compiler Notes)\n"
        b"   /CreationDate (D:20260315102030Z)\n"
        b"   /ModDate (D:20260316143000+05'30')\n"
        b">>\n"
        b"endobj\n"
        b"%%EOF\n"
    )
    report = image_forensics.analyse(raw, filename="notes.pdf")

    assert report["file"]["format"] == "PDF"
    assert report["file"]["mime"] == "application/pdf"
    assert report["file"]["pdf_version"] == "1.7"

    doc = report["document"]
    assert doc["present"] is True
    assert doc["author"] == "Grace Hopper"
    assert doc["creator_software"] == "LibreOffice 7.6"
    assert doc["producer_software"] == "macOS Version 14.2 (Build 23C64) Quartz PDFContext"
    assert doc["title"] == "Compiler Notes"
    assert doc["created"] == "2026-03-15T10:20:30Z"
    assert doc["modified"] == "2026-03-16T14:30:00+05:30"

    codes = {s["code"] for s in report["signals"]}
    assert "author_present" in codes
    assert "editing_software" in codes
    assert "timestamp_mismatch" in codes


def test_pdf_hex_utf16_and_compressed_xmp():
    # "Alan Turing" in UTF-16BE with BOM FEFF
    author_hex = (b"\xfe\xff" + "Alan Turing".encode("utf-16-be")).hex().upper().encode("ascii")
    xmp_packet = (
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:xmp="http://ns.adobe.com/xap/1.0/"'
        b' xmlns:pdf="http://ns.adobe.com/pdf/1.3/">'
        b"<rdf:Description>"
        b"<xmp:CreatorTool>LaTeX with hyperref</xmp:CreatorTool>"
        b"<pdf:Producer>pdfTeX-1.40.25</pdf:Producer>"
        b"<xmp:CreateDate>2026-01-05T08:00:00Z</xmp:CreateDate>"
        b"</rdf:Description></rdf:RDF></x:xmpmeta>"
    )
    compressed_xmp = zlib.compress(xmp_packet)
    raw = (
        b"%PDF-1.5\n"
        b"1 0 obj\n<< /Author <" + author_hex + b"> >>\nendobj\n"
        b"2 0 obj\n<< /Filter /FlateDecode >>\nstream\n" + compressed_xmp + b"\nendstream\nendobj\n"
        b"%%EOF"
    )
    report = image_forensics.analyse(raw, filename="paper.pdf")
    doc = report["document"]
    assert doc["author"] == "Alan Turing"
    assert doc["creator_software"] == "LaTeX with hyperref"
    assert doc["producer_software"] == "pdfTeX-1.40.25"
    assert doc["created"] == "2026-01-05T08:00:00Z"


def test_cli_forensics_pdf_and_docx(tmp_path, capsys):
    docx_path = tmp_path / "sample.docx"
    docx_path.write_bytes(_make_ooxml_bytes(SAMPLE_CORE_XML, SAMPLE_APP_XML))

    rc = cli_main.main(["forensics", str(docx_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["file"]["format"] == "DOCX"
    assert payload["document"]["author"] == "Ada Lovelace"

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n<< /Author (Margaret Hamilton) /Creator (TeX) /CreationDate (D:20260401120000Z) >>\n%%EOF"
    )
    rc = cli_main.main(["forensics", str(pdf_path), "--color", "never"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Document forensics" in out
    assert "Margaret Hamilton" in out
    assert "TeX" in out
    assert "2026-04-01T12:00:00Z" in out


# ── CLI Password Breach Check ────────────────────────────────────


class _DummyResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text


def test_password_cli_k_anonymity_breached(monkeypatch, capsys):
    secret = "password123"
    digest = hashlib.sha1(secret.encode("utf-8")).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]

    called_urls = []
    called_headers = []

    def fake_get(url, headers=None, timeout=None):
        called_urls.append(url)
        called_headers.append(headers or {})
        body = (
            "00000000000000000000000000000000000:0\r\n"
            f"{suffix}:248910\r\n"
            "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:3\r\n"
        )
        return _DummyResponse(200, body)

    monkeypatch.setattr("cli.__main__.getpass.getpass", lambda prompt="Password: ": secret)
    monkeypatch.setattr(password_check.requests, "get", fake_get)

    rc = cli_main.main(["password", "--json"])
    assert rc == 0

    # Verify only the 5-char prefix was sent to Pwned Passwords
    assert called_urls == [f"https://api.pwnedpasswords.com/range/{prefix}"]
    assert called_headers[0].get("Add-Padding") == "true"

    raw_out = capsys.readouterr().out
    # Plaintext password and full SHA-1 must never appear in output
    assert secret not in raw_out
    assert suffix not in raw_out

    data = json.loads(raw_out)
    assert data["status"] == "ok"
    assert data["breached"] is True
    assert data["count"] == 248910
    assert data["sha1_prefix"] == prefix
    assert data["privacy"]["k_anonymity"] is True


def test_password_cli_clean_and_padded_zero(monkeypatch, capsys):
    secret = "c0rrect-H0rse-Battery-Staple!99"
    digest = hashlib.sha1(secret.encode("utf-8")).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]

    def fake_get(url, headers=None, timeout=None):
        assert url == f"https://api.pwnedpasswords.com/range/{prefix}"
        # Suffix present as a 0-count padding row
        return _DummyResponse(200, f"{suffix}:0\r\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:12\r\n")

    monkeypatch.setattr("cli.__main__.getpass.getpass", lambda prompt="Password: ": secret)
    monkeypatch.setattr(password_check.requests, "get", fake_get)

    rc = cli_main.main(["password", "--color", "never"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Not found in breach data" in out
    assert secret not in out


def test_password_cli_empty_and_upstream_error(monkeypatch, capsys):
    monkeypatch.setattr("cli.__main__.getpass.getpass", lambda prompt="Password: ": "")
    rc = cli_main.main(["password"])
    assert rc == 2

    monkeypatch.setattr("cli.__main__.getpass.getpass", lambda prompt="Password: ": "somepass")
    monkeypatch.setattr(
        password_check.requests,
        "get",
        lambda url, headers=None, timeout=None: _DummyResponse(503, "Unavailable"),
    )
    rc = cli_main.main(["password", "--json"])
    assert rc == 1
    err_data = json.loads(capsys.readouterr().out)
    assert err_data["status"] == "error"
