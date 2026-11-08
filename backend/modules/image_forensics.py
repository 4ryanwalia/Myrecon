"""
Image and document forensics, deterministic, local, provider-free.

Everything in this module is computed from the file bytes themselves. There
are no network calls and no API keys, so these findings are always available
and always reproducible: the same bytes yield the same report.

Supported inputs:
  • Images (JPEG, PNG, WebP, TIFF, GIF, ...) — EXIF, GPS, cryptographic and
    perceptual hashes, provenance signals. Requires Pillow and numpy.
  • Office Open XML documents (.docx, .xlsx, .pptx) — inspects docProps/core.xml
    and docProps/app.xml via Python's built-in zipfile + xml.etree (zero
    external dependencies) for author names, creator software, company,
    revision history, and timestamps.
  • PDF documents (.pdf) — inspects PDF headers, Document Information
    dictionaries (/Author, /Creator, /Producer, /CreationDate, /ModDate,
    /Title, /Subject, /Keywords) and embedded XMP streams with zero external
    dependencies.

Deliberately NOT here:
  • Face recognition / identity inference. Detecting that a face is present is
    a geometry question; asserting *whose* face it is from appearance alone is
    not something this platform does.
  • Anything requiring a model download or a system binary. This runs inside a
    512 MB Render worker.
"""

from __future__ import annotations

import hashlib
import io
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from datetime import datetime
from typing import Any, Optional

try:
    import numpy as np
    from PIL import ExifTags, Image, ImageFile

    # A truncated upload should degrade to a partial read rather than raising,
    # so forensics still returns what it can for a damaged file.
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    _EXIF_TAGS = {v: k for k, v in ExifTags.TAGS.items()}
    _GPS_TAGS = {v: k for k, v in ExifTags.GPSTAGS.items()}
    _IMAGE_DEPS_ERROR: Optional[ImportError] = None
except ImportError as _exc:  # pragma: no cover - exercised when Pillow/numpy absent
    np = None  # type: ignore[assignment]
    ExifTags = Image = ImageFile = None  # type: ignore[assignment]
    _EXIF_TAGS = {}
    _GPS_TAGS = {}
    _IMAGE_DEPS_ERROR = _exc

# Refuse absurd dimensions before allocating pixels. Pillow's own bomb guard
# raises a warning; this makes the limit explicit and returns a clean error.
MAX_PIXELS = 80_000_000          # ~80 MP
MAX_BYTES = 25 * 1024 * 1024     # 25 MB
_MAX_XML_BYTES = 2 * 1024 * 1024  # 2 MB cap per embedded XML / stream member

# Perceptual hash sizes. 8x8 is the conventional choice: 64-bit digests whose
# Hamming distance is meaningful up to roughly 10 bits.
_AHASH_SIZE = 8
_DHASH_SIZE = 8
_PHASH_SIZE = 32                 # DCT input; low-frequency 8x8 block is kept

_OOXML_MIMES = {
    "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "PPTX": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "OOXML": "application/vnd.openxmlformats-package",
}

_OOXML_EXTENSIONS = {
    ".docx": "DOCX",
    ".xlsx": "XLSX",
    ".pptx": "PPTX",
}

_PDF_DATE_RE = re.compile(
    r"^(?:D:)?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?"
    r"(?:([Zz]|[+-])(\d{2})?'?(\d{2})?'?)?$"
)


class ImageForensicsError(ValueError):
    """Raised for input we refuse to process (too large, unreadable file)."""


# ──────────────────────────────────────────────────────────────────────
#  Hashing
# ──────────────────────────────────────────────────────────────────────

def cryptographic_hashes(raw: bytes) -> dict:
    """
    Exact-duplicate identifiers. Two files share these only if their bytes are
    identical, so they answer "is this the same file?" but say nothing about
    visual similarity, a re-encode changes them completely.
    """
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "md5": hashlib.md5(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _to_luma_array(img: "Image.Image", size: int) -> "np.ndarray":
    """Downscale to size×size greyscale as float, the common front half of
    every perceptual hash below."""
    small = img.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    return np.asarray(small, dtype=np.float64)


def _bits_to_hex(bits: "np.ndarray") -> str:
    """Pack a boolean array (row-major) into a lowercase hex digest."""
    flat = bits.flatten()
    # np.packbits is big-endian per byte, which keeps the digest stable across
    # platforms and matches the conventional imagehash string layout.
    return np.packbits(flat).tobytes().hex()


def average_hash(img: "Image.Image") -> str:
    """aHash, each pixel brighter than the mean becomes a 1. Cheap, tolerant
    of re-compression, but easily collided by flat images."""
    px = _to_luma_array(img, _AHASH_SIZE)
    return _bits_to_hex(px > px.mean())


def difference_hash(img: "Image.Image") -> str:
    """dHash, encodes horizontal gradient direction. Robust to brightness and
    scaling shifts, which makes it the best single choice for "same photo,
    different upload" matching."""
    # Resized directly rather than via _to_luma_array, which squares its input:
    # dHash needs one extra column so each row yields SIZE comparisons.
    small = img.convert("L").resize((_DHASH_SIZE + 1, _DHASH_SIZE),
                                    Image.Resampling.LANCZOS)
    px = np.asarray(small, dtype=np.float64)
    return _bits_to_hex(px[:, 1:] > px[:, :-1])


def perceptual_hash(img: "Image.Image") -> str:
    """
    pHash, DCT-II on a 32×32 luma grid, keeping the top-left 8×8 block of low
    frequencies (excluding the DC term from the median). Slowest of the three
    and the most resistant to crops, overlays and heavy re-encoding.
    """
    px = _to_luma_array(img, _PHASH_SIZE)
    dct = _dct2(px)
    block = dct[:8, :8]
    # The DC coefficient carries overall brightness and would dominate the
    # median, so it is excluded from the threshold but kept in the digest grid.
    med = np.median(block.flatten()[1:])
    return _bits_to_hex(block > med)


def _dct2(a: "np.ndarray") -> "np.ndarray":
    """
    2-D DCT-II via matrix multiplication.

    scipy.fft would be the obvious tool, but scipy is a ~90 MB dependency for
    one transform on a 32×32 array. The basis matrix is built once per call and
    the multiply is trivial at this size.
    """
    n = a.shape[0]
    k = np.arange(n)
    # basis[i, j] = cos(pi * (2j + 1) * i / (2n)), orthonormalised.
    basis = np.cos(np.pi * (2 * k[None, :] + 1) * k[:, None] / (2 * n))
    basis[0] *= 1.0 / np.sqrt(2)
    basis *= np.sqrt(2.0 / n)
    return basis @ a @ basis.T


def hamming_distance(hex_a: str, hex_b: str) -> Optional[int]:
    """
    Differing-bit count between two hex digests, or None if they are not
    comparable (different lengths, or malformed). Callers treat None as
    "unknown", never as "identical".
    """
    if not hex_a or not hex_b or len(hex_a) != len(hex_b):
        return None
    try:
        return bin(int(hex_a, 16) ^ int(hex_b, 16)).count("1")
    except ValueError:
        return None


def similarity_from_distance(distance: Optional[int], bits: int = 64) -> Optional[float]:
    """Map a Hamming distance to a 0–100 similarity. Linear in bits, which is
    honest about what the metric is, it is not a probability."""
    if distance is None:
        return None
    return round(max(0.0, 1.0 - distance / bits) * 100, 1)


# ──────────────────────────────────────────────────────────────────────
#  EXIF
# ──────────────────────────────────────────────────────────────────────

def _coerce(value: Any) -> Any:
    """Make an EXIF value JSON-safe. Pillow hands back IFDRational, bytes and
    nested tuples, none of which survive json.dumps."""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace").strip("\x00").strip() or None
    if isinstance(value, tuple):
        return [_coerce(v) for v in value]
    # IFDRational and friends expose numerator/denominator.
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        try:
            return float(value)
        except (ZeroDivisionError, TypeError):
            return None
    if isinstance(value, str):
        return value.strip("\x00").strip() or None
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)


def _rational_to_degrees(parts: Any) -> Optional[float]:
    """Convert EXIF (degrees, minutes, seconds) to decimal degrees."""
    try:
        d, m, s = (float(p) for p in parts[:3])
        return d + m / 60.0 + s / 3600.0
    except (TypeError, ValueError, IndexError, ZeroDivisionError):
        return None


def extract_gps(gps_ifd: dict) -> dict:
    """
    Decode the GPS IFD into decimal coordinates.

    GPS presence is one of the highest-value findings in image forensics, it
    places a device at a location and time, so the raw reference letters are
    reported alongside the decimals for auditability.
    """
    out: dict[str, Any] = {"present": False}
    if not gps_ifd:
        return out

    lat = _rational_to_degrees(gps_ifd.get(_GPS_TAGS.get("GPSLatitude")))
    lon = _rational_to_degrees(gps_ifd.get(_GPS_TAGS.get("GPSLongitude")))
    lat_ref = _coerce(gps_ifd.get(_GPS_TAGS.get("GPSLatitudeRef")))
    lon_ref = _coerce(gps_ifd.get(_GPS_TAGS.get("GPSLongitudeRef")))

    if lat is None or lon is None:
        return out

    # South and West are negative. A missing ref is ambiguous, so it is
    # surfaced rather than assumed.
    if lat_ref and str(lat_ref).upper().startswith("S"):
        lat = -lat
    if lon_ref and str(lon_ref).upper().startswith("W"):
        lon = -lon

    alt = gps_ifd.get(_GPS_TAGS.get("GPSAltitude"))
    out.update({
        "present": True,
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
        "latitude_ref": lat_ref,
        "longitude_ref": lon_ref,
        "ref_assumed": not (lat_ref and lon_ref),
        "altitude_m": round(float(alt), 1) if alt is not None else None,
        "maps_url": f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map=16/{lat:.6f}/{lon:.6f}",
    })
    return out


def _parse_exif_datetime(value: Any) -> Optional[str]:
    """EXIF timestamps are 'YYYY:MM:DD HH:MM:SS' with no timezone. Normalise to
    ISO 8601 without inventing an offset."""
    if not isinstance(value, str):
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt).isoformat()
        except ValueError:
            continue
    return None


def extract_exif(img: "Image.Image") -> dict:
    """
    Pull the EXIF blocks that matter for provenance: camera identity, capture
    time, software, and GPS.

    Absence is itself a signal and is reported explicitly, most social
    platforms strip EXIF on upload, so a photo with no EXIF has very likely
    been through one.
    """
    result: dict[str, Any] = {
        "present": False, "camera": {}, "capture": {},
        "software": None, "gps": {"present": False}, "raw_tag_count": 0,
    }
    try:
        exif = img.getexif()
    except Exception:
        return result
    if not exif:
        return result

    # EXIF is split across IFDs. getexif() returns only the 0th (image) IFD,
    # which holds Make/Model/Software/DateTime. The tags an investigator most
    # wants, DateTimeOriginal, ISO, aperture, focal length, lens, body serial,
    # live in the Exif sub-IFD behind the ExifOffset pointer, so both must be
    # consulted or those fields silently read as None.
    try:
        sub = exif.get_ifd(_EXIF_TAGS.get("ExifOffset")) or {}
    except Exception:
        sub = {}

    result["present"] = True
    result["raw_tag_count"] = len(exif) + len(sub)

    def tag(name: str) -> Any:
        tid = _EXIF_TAGS.get(name)
        if tid is None:
            return None
        # Base IFD wins when a tag appears in both; fall through to the sub-IFD.
        if tid in exif:
            return _coerce(exif.get(tid))
        return _coerce(sub.get(tid)) if tid in sub else None

    result["camera"] = {
        "make": tag("Make"),
        "model": tag("Model"),
        "lens": tag("LensModel"),
        "serial": tag("BodySerialNumber"),
    }
    result["software"] = tag("Software")
    result["capture"] = {
        "datetime_original": _parse_exif_datetime(tag("DateTimeOriginal")),
        "datetime_digitized": _parse_exif_datetime(tag("DateTimeDigitized")),
        "datetime_modified": _parse_exif_datetime(tag("DateTime")),
        "orientation": tag("Orientation"),
        "iso": tag("ISOSpeedRatings"),
        "f_number": tag("FNumber"),
        "exposure_time": tag("ExposureTime"),
        "focal_length_mm": tag("FocalLength"),
        "flash": tag("Flash"),
    }

    # GPS lives in its own sub-IFD; get_ifd returns {} when absent.
    try:
        result["gps"] = extract_gps(exif.get_ifd(_EXIF_TAGS.get("GPSInfo")) or {})
    except Exception:
        result["gps"] = {"present": False}

    return result


# ──────────────────────────────────────────────────────────────────────
#  Document metadata (.docx / .xlsx / .pptx and .pdf)
# ──────────────────────────────────────────────────────────────────────

def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip("\x00").strip()
    return text or None


def _parse_document_datetime(value: Any) -> Optional[str]:
    """
    Normalise PDF (`D:YYYYMMDDHHmmSSOHH'mm'`) and OOXML/ISO timestamps into
    ISO 8601 strings without inventing a timezone when none was recorded.
    """
    text = _clean_text(value)
    if not text:
        return None

    m = _PDF_DATE_RE.match(text)
    if m:
        year = int(m.group(1))
        month = min(12, max(1, int(m.group(2) or 1)))
        day = min(31, max(1, int(m.group(3) or 1)))
        hour = min(23, max(0, int(m.group(4) or 0)))
        minute = min(59, max(0, int(m.group(5) or 0)))
        second = min(59, max(0, int(m.group(6) or 0)))
        iso = f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}"
        tz_sign = m.group(7)
        tz_hr = m.group(8)
        tz_min = m.group(9) or "00"
        if tz_sign:
            if tz_sign.upper() == "Z":
                iso += "Z"
            elif tz_hr is not None:
                iso += f"{tz_sign}{int(tz_hr):02d}:{int(tz_min):02d}"
        return iso

    exif_dt = _parse_exif_datetime(text)
    if exif_dt:
        return exif_dt

    return text


def _local_tag(tag: str) -> str:
    """Strip `{namespace}` prefix from an ElementTree tag name."""
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    if ":" in tag:
        return tag.rsplit(":", 1)[1]
    return tag


def _detect_ooxml_format(namelist: list[str], filename: str = "") -> Optional[str]:
    lower_names = [n.lower() for n in namelist]
    if any(n.startswith("word/") for n in lower_names):
        return "DOCX"
    if any(n.startswith("xl/") for n in lower_names):
        return "XLSX"
    if any(n.startswith("ppt/") for n in lower_names):
        return "PPTX"

    ext = ""
    if filename and "." in filename:
        ext = "." + filename.rsplit(".", 1)[1].lower()
    if ext in _OOXML_EXTENSIONS:
        return _OOXML_EXTENSIONS[ext]

    if any(n in ("docprops/core.xml", "docprops/app.xml", "[content_types].xml")
           for n in lower_names):
        return "DOCX"
    return None


def _read_zip_xml(zf: zipfile.ZipFile, member_name: str) -> Optional[ET.Element]:
    """Read and parse an XML member from a ZipFile if present and bounded."""
    target = None
    for info in zf.infolist():
        if info.filename.lower() == member_name.lower():
            target = info
            break
    if target is None or target.file_size > _MAX_XML_BYTES:
        return None
    try:
        raw_xml = zf.read(target.filename)
        return ET.fromstring(raw_xml)
    except Exception:
        return None


def extract_ooxml_metadata(raw: bytes, filename: str = "") -> dict[str, Any]:
    """
    Inspect an Office Open XML archive (`.docx`, `.xlsx`, `.pptx`) using
    Python's built-in `zipfile` and `xml.etree.ElementTree` on
    `docProps/core.xml` (and `docProps/app.xml` when present).
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except Exception as exc:
        raise ImageForensicsError(f"Not a valid Office document archive: {exc}") from exc

    with zf:
        fmt = _detect_ooxml_format(zf.namelist(), filename=filename)
        if fmt is None:
            raise ImageForensicsError("ZIP archive is not an Office document (.docx/.xlsx/.pptx).")

        core_root = _read_zip_xml(zf, "docProps/core.xml")
        app_root = _read_zip_xml(zf, "docProps/app.xml")

    core_fields: dict[str, str] = {}
    if core_root is not None:
        for elem in core_root.iter():
            if elem is core_root:
                continue
            name = _local_tag(elem.tag).lower()
            val = _clean_text(elem.text)
            if val and name not in core_fields:
                core_fields[name] = val

    app_fields: dict[str, str] = {}
    if app_root is not None:
        for elem in app_root.iter():
            if elem is app_root:
                continue
            name = _local_tag(elem.tag).lower()
            val = _clean_text(elem.text)
            if val and name not in app_fields:
                app_fields[name] = val

    author = core_fields.get("creator") or core_fields.get("author")
    last_modified_by = core_fields.get("lastmodifiedby")
    created = _parse_document_datetime(core_fields.get("created"))
    modified = _parse_document_datetime(core_fields.get("modified"))
    title = core_fields.get("title")
    subject = core_fields.get("subject")
    description = core_fields.get("description")
    keywords = core_fields.get("keywords")
    category = core_fields.get("category")
    language = core_fields.get("language")
    revision: Optional[Any] = core_fields.get("revision")
    if isinstance(revision, str) and revision.isdigit():
        revision = int(revision)

    app_name = (
        app_fields.get("application")
        or core_fields.get("application")
        or core_fields.get("software")
        or core_fields.get("creatortool")
    )
    app_version = app_fields.get("appversion")
    if app_name and app_version and app_version not in app_name:
        creator_software = f"{app_name} ({app_version})"
    else:
        creator_software = app_name

    company = app_fields.get("company")
    template = app_fields.get("template")

    pages: Optional[int] = None
    for count_key in ("pages", "slides", "sheets"):
        raw_count = app_fields.get(count_key)
        if raw_count and raw_count.isdigit():
            pages = int(raw_count)
            break

    present = any(
        v is not None
        for v in (
            author, last_modified_by, creator_software, company,
            title, subject, description, keywords, category,
            language, revision, created, modified, template, pages,
        )
    )

    return {
        "present": present,
        "format": fmt,
        "author": author,
        "last_modified_by": last_modified_by,
        "creator_software": creator_software,
        "producer_software": app_version,
        "software": creator_software,
        "company": company,
        "template": template,
        "title": title,
        "subject": subject,
        "description": description,
        "keywords": keywords,
        "category": category,
        "language": language,
        "revision": revision,
        "pages": pages,
        "created": created,
        "modified": modified,
    }


def _decode_pdf_bytes(raw_bytes: bytes) -> Optional[str]:
    if not raw_bytes:
        return None
    if raw_bytes.startswith(b"\xfe\xff"):
        text = raw_bytes[2:].decode("utf-16-be", "replace")
    elif raw_bytes.startswith(b"\xff\xfe"):
        text = raw_bytes[2:].decode("utf-16-le", "replace")
    elif raw_bytes.startswith(b"\xef\xbb\xbf"):
        text = raw_bytes[3:].decode("utf-8", "replace")
    else:
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = raw_bytes.decode("latin-1", "replace")
    return _clean_text(text)


def _read_pdf_literal(buf: bytes, open_paren_index: int) -> bytes:
    """
    Parse a PDF literal string `(...)` starting at `open_paren_index`, handling
    balanced nested parentheses, backslash escapes and octal character codes.
    """
    out = bytearray()
    i = open_paren_index + 1
    n = len(buf)
    depth = 1
    while i < n and depth > 0:
        b = buf[i]
        if b == 0x5C:  # backslash
            i += 1
            if i >= n:
                break
            esc = buf[i]
            if esc == ord("n"):
                out.append(0x0A)
                i += 1
            elif esc == ord("r"):
                out.append(0x0D)
                i += 1
            elif esc == ord("t"):
                out.append(0x09)
                i += 1
            elif esc == ord("b"):
                out.append(0x08)
                i += 1
            elif esc == ord("f"):
                out.append(0x0C)
                i += 1
            elif esc in (ord("("), ord(")"), ord("\\")):
                out.append(esc)
                i += 1
            elif esc in (0x0A, 0x0D):
                # Line continuation
                if esc == 0x0D and i + 1 < n and buf[i + 1] == 0x0A:
                    i += 2
                else:
                    i += 1
            elif ord("0") <= esc <= ord("7"):
                oct_digits = bytes([esc])
                i += 1
                for _ in range(2):
                    if i < n and ord("0") <= buf[i] <= ord("7"):
                        oct_digits += bytes([buf[i]])
                        i += 1
                    else:
                        break
                out.append(int(oct_digits, 8) & 0xFF)
            else:
                out.append(esc)
                i += 1
        elif b == 0x28:  # '('
            depth += 1
            out.append(b)
            i += 1
        elif b == 0x29:  # ')'
            depth -= 1
            if depth > 0:
                out.append(b)
            i += 1
        else:
            out.append(b)
            i += 1
    return bytes(out)


def _extract_pdf_tag(buffers: list[bytes], key: str) -> Optional[str]:
    """Find `/Key (...)` or `/Key <HEX>` across PDF header/object buffers."""
    pattern = re.compile(rb"/" + key.encode("ascii") + rb"(?![A-Za-z0-9_])\s*([(<])")
    for buf in buffers:
        for match in pattern.finditer(buf):
            delim = match.group(1)
            pos = match.start(1)
            if delim == b"(":
                raw_val = _read_pdf_literal(buf, pos)
                decoded = _decode_pdf_bytes(raw_val)
                if decoded:
                    return decoded
            elif delim == b"<":
                # Avoid dictionary opener `<<`
                if pos + 1 < len(buf) and buf[pos + 1 : pos + 2] == b"<":
                    continue
                end = buf.find(b">", pos + 1)
                if end != -1:
                    hex_str = re.sub(rb"\s+", b"", buf[pos + 1 : end]).decode("ascii", "ignore")
                    if len(hex_str) % 2 == 1:
                        hex_str += "0"
                    try:
                        raw_val = bytes.fromhex(hex_str)
                    except ValueError:
                        continue
                    decoded = _decode_pdf_bytes(raw_val)
                    if decoded:
                        return decoded
    return None


def _extract_pdf_xmp(buffers: list[bytes]) -> dict[str, str]:
    """Extract XMP metadata fields if an embedded RDF/XMP packet is present."""
    out: dict[str, str] = {}
    for buf in buffers:
        for marker in (b"<x:xmpmeta", b"<rdf:RDF"):
            start = buf.find(marker)
            if start == -1:
                continue
            end_tag = b"</x:xmpmeta>" if marker == b"<x:xmpmeta" else b"</rdf:RDF>"
            end = buf.find(end_tag, start)
            if end == -1 or (end - start) > _MAX_XML_BYTES:
                continue
            snippet = buf[start : end + len(end_tag)]
            try:
                root = ET.fromstring(snippet)
            except Exception:
                continue
            for elem in root.iter():
                local = _local_tag(elem.tag).lower()
                if local in ("creator", "title", "description", "subject"):
                    # In XMP, dc:creator / dc:title often wrap text in rdf:Seq/rdf:li or rdf:Alt/rdf:li
                    texts = [
                        _clean_text(li.text)
                        for li in elem.iter()
                        if _local_tag(li.tag).lower() == "li" and _clean_text(li.text)
                    ]
                    val = ", ".join(t for t in texts if t) if texts else _clean_text(elem.text)
                    if val and local not in out:
                        out[local] = val
                elif local in ("creatortool", "producer", "createdate", "modifydate", "keywords"):
                    val = _clean_text(elem.text)
                    if val and local not in out:
                        out[local] = val
    return out


def extract_pdf_metadata(raw: bytes) -> dict[str, Any]:
    """
    Inspect a `.pdf` file's header, Document Information dictionary (`/Author`,
    `/Creator`, `/Producer`, `/CreationDate`, `/ModDate`, `/Title`, `/Subject`,
    `/Keywords`) and any XMP packet for provenance metadata.
    """
    header_window = raw[:1024]
    if b"%PDF-" not in header_window:
        raise ImageForensicsError("Not a valid PDF file (missing %PDF- header).")

    ver_match = re.search(rb"%PDF-(\d+\.\d+)", header_window)
    pdf_version = ver_match.group(1).decode("ascii") if ver_match else None

    buffers: list[bytes] = [raw]
    # Also inspect small FlateDecode streams in case /Info or XMP is compressed.
    for stream_match in re.finditer(rb"stream\r?\n", raw):
        s_start = stream_match.end()
        s_end = raw.find(b"endstream", s_start)
        if s_end == -1 or (s_end - s_start) > 512 * 1024:
            continue
        chunk = raw[s_start:s_end].strip(b"\r\n")
        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                decomp = zlib.decompress(chunk, wbits, _MAX_XML_BYTES)
                if len(decomp) <= _MAX_XML_BYTES:
                    buffers.append(decomp)
                break
            except Exception:
                continue
        if len(buffers) >= 25:
            break

    author = _extract_pdf_tag(buffers, "Author")
    creator_software = _extract_pdf_tag(buffers, "Creator")
    producer_software = _extract_pdf_tag(buffers, "Producer")
    created_raw = _extract_pdf_tag(buffers, "CreationDate")
    modified_raw = _extract_pdf_tag(buffers, "ModDate")
    title = _extract_pdf_tag(buffers, "Title")
    subject = _extract_pdf_tag(buffers, "Subject")
    keywords = _extract_pdf_tag(buffers, "Keywords")

    xmp = _extract_pdf_xmp(buffers)
    if not author:
        author = xmp.get("creator")
    if not creator_software:
        creator_software = xmp.get("creatortool")
    if not producer_software:
        producer_software = xmp.get("producer")
    if not created_raw:
        created_raw = xmp.get("createdate")
    if not modified_raw:
        modified_raw = xmp.get("modifydate")
    if not title:
        title = xmp.get("title")
    if not subject:
        subject = xmp.get("description") or xmp.get("subject")
    if not keywords:
        keywords = xmp.get("keywords")

    created = _parse_document_datetime(created_raw)
    modified = _parse_document_datetime(modified_raw)

    if creator_software and producer_software and creator_software != producer_software:
        software = f"{creator_software} / {producer_software}"
    else:
        software = creator_software or producer_software

    encrypted = bool(re.search(rb"/Encrypt(?![A-Za-z0-9_])", raw))

    present = any(
        v is not None
        for v in (
            author, creator_software, producer_software,
            created, modified, title, subject, keywords,
        )
    )

    return {
        "present": present,
        "format": "PDF",
        "pdf_version": pdf_version,
        "author": author,
        "last_modified_by": None,
        "creator_software": creator_software,
        "producer_software": producer_software,
        "software": software,
        "company": None,
        "title": title,
        "subject": subject,
        "keywords": keywords,
        "created": created,
        "modified": modified,
        "encrypted": encrypted,
    }


def document_provenance_signals(doc: dict, fmt: str) -> list[dict]:
    """Derive provenance observations from document metadata."""
    signals: list[dict] = []

    def add(code: str, label: str, detail: str, weight: str) -> None:
        signals.append({"code": code, "label": label, "detail": detail, "confidence": weight})

    if not doc.get("present"):
        add(
            "no_document_metadata",
            "No document metadata",
            f"The {fmt} file carries no author, software or timestamp tags. "
            "Metadata may have been scrubbed or omitted by the exporter.",
            "high",
        )
        return signals

    author = doc.get("author")
    last_mod = doc.get("last_modified_by")
    if author:
        add(
            "author_present",
            "Author identity embedded",
            f"Document metadata records the author as {author!r}.",
            "high",
        )
    if last_mod and author and last_mod != author:
        add(
            "multiple_authors",
            "Modified by a different account",
            f"Created by {author!r} and last saved by {last_mod!r}, exposing two distinct user identities.",
            "high",
        )
    elif last_mod and not author:
        add(
            "modifier_present",
            "Last-modified user embedded",
            f"Document metadata records lastModifiedBy as {last_mod!r}.",
            "high",
        )

    software = doc.get("software") or doc.get("creator_software") or doc.get("producer_software")
    if software:
        add(
            "editing_software",
            "Creator software recorded",
            f"Document headers identify the producing software as {software!r}.",
            "high",
        )

    company = doc.get("company")
    if company:
        add(
            "company_present",
            "Organisation metadata present",
            f"Extended document properties record the organisation as {company!r}.",
            "medium",
        )

    created = doc.get("created")
    modified = doc.get("modified")
    if created and modified and created != modified:
        add(
            "timestamp_mismatch",
            "Modified after creation",
            f"Creation timestamp ({created}) differs from last-modified timestamp ({modified}), indicating later edits.",
            "medium",
        )

    return signals


def _is_document_input(raw: bytes, filename: str = "") -> Optional[str]:
    """
    Return `'PDF'` or `'OOXML'` when the file bytes or extension represent a
    supported document format, or `None` for images.
    """
    ext = ""
    if filename and "." in filename:
        ext = "." + filename.rsplit(".", 1)[1].lower()

    if b"%PDF-" in raw[:1024] or ext == ".pdf":
        return "PDF"

    if ext in _OOXML_EXTENSIONS:
        return "OOXML"

    if raw[:4] == b"PK\x03\x04" and zipfile.is_zipfile(io.BytesIO(raw)):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                if _detect_ooxml_format(zf.namelist(), filename=filename) is not None:
                    return "OOXML"
        except Exception:
            pass
    return None


def _analyse_document(raw: bytes, filename: str, kind: str) -> dict:
    if kind == "PDF":
        doc = extract_pdf_metadata(raw)
        fmt = "PDF"
        mime = "application/pdf"
    else:
        doc = extract_ooxml_metadata(raw, filename=filename)
        fmt = doc.get("format") or "DOCX"
        mime = _OOXML_MIMES.get(fmt, _OOXML_MIMES["OOXML"])

    file_block: dict[str, Any] = {
        "filename": filename or None,
        "format": fmt,
        "mime": mime,
        **cryptographic_hashes(raw),
    }
    if doc.get("pdf_version"):
        file_block["pdf_version"] = doc["pdf_version"]

    return {
        "file": file_block,
        "document": doc,
        "exif": {
            "present": doc["present"],
            "author": doc.get("author"),
            "last_modified_by": doc.get("last_modified_by"),
            "software": doc.get("software"),
            "creator_software": doc.get("creator_software"),
            "producer_software": doc.get("producer_software"),
            "company": doc.get("company"),
            "title": doc.get("title"),
            "subject": doc.get("subject"),
            "keywords": doc.get("keywords"),
            "revision": doc.get("revision"),
            "created": doc.get("created"),
            "modified": doc.get("modified"),
            "gps": {"present": False},
        },
        "signals": document_provenance_signals(doc, fmt),
        "provenance": {
            "source": "local",
            "requires_network": False,
            "deterministic": True,
            "note": "Computed from the file bytes. No third-party service involved.",
        },
    }


# ──────────────────────────────────────────────────────────────────────
#  Provenance signals (images)
# ──────────────────────────────────────────────────────────────────────

def provenance_signals(exif: dict, fmt: Optional[str], width: int, height: int) -> list[dict]:
    """
    Derive what the metadata implies about the file's history.

    Each signal is an observation with a stated basis, not a verdict. "EXIF was
    stripped" is evidence consistent with a platform upload; it is not proof of
    tampering, and the wording keeps that distinction.
    """
    signals: list[dict] = []

    def add(code: str, label: str, detail: str, weight: str) -> None:
        signals.append({"code": code, "label": label, "detail": detail, "confidence": weight})

    camera = exif.get("camera") or {}
    software = exif.get("software")
    capture = exif.get("capture") or {}

    if not exif.get("present"):
        add("no_exif", "No EXIF metadata",
            "The file carries no EXIF block. Most social and messaging platforms "
            "strip metadata on upload, so this is expected for a downloaded image.",
            "high")
    else:
        if not camera.get("make") and not camera.get("model"):
            add("exif_no_camera", "EXIF present but no camera identity",
                "EXIF tags exist without Make or Model, which is typical of an "
                "image re-saved by an editor rather than one straight off a device.",
                "medium")
        if software:
            add("editing_software", "Processed by software",
                f"The Software tag reads {software!r}, so the file was written by "
                "an application rather than exported directly by a camera.",
                "high")
        if camera.get("serial"):
            add("camera_serial", "Camera serial number present",
                "A body serial number is recorded. This links the file to a "
                "specific physical device and survives most copies.",
                "high")
        orig = capture.get("datetime_original")
        mod = capture.get("datetime_modified")
        if orig and mod and mod != orig:
            add("timestamp_mismatch", "Modified after capture",
                f"Capture time ({orig}) differs from the file's last-modified "
                f"time ({mod}), indicating a later re-save.",
                "medium")

    if (exif.get("gps") or {}).get("present"):
        add("gps_present", "GPS coordinates embedded",
            "The file records where it was taken. This is the strongest single "
            "location finding available from an image and needs no external service.",
            "high")

    if fmt == "PNG" and not exif.get("present"):
        add("likely_screenshot", "Consistent with a screenshot",
            "PNG with no EXIF is the usual signature of a screen capture or a "
            "generated image rather than a photograph.",
            "low")

    if width and height:
        ratio = width / height if height else 0
        if abs(ratio - 1.0) < 0.01:
            add("square_crop", "Square aspect ratio",
                "Exactly square dimensions suggest a deliberate crop, commonly "
                "an avatar or profile image.",
                "low")

    return signals


# ──────────────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────────────

def analyse(raw: bytes, filename: str = "") -> dict:
    """
    Full local forensic report for one image or document (`.pdf`, `.docx`,
    `.xlsx`, `.pptx`).

    Args:
        raw: the file bytes as read from disk.
        filename: original name, recorded for provenance and used as a fallback
            hint for OOXML sub-formats when archive paths are minimal.

    Returns a JSON-serialisable dict. Raises ImageForensicsError for input we
    decline to process.
    """
    if not raw:
        raise ImageForensicsError("Empty upload.")
    if len(raw) > MAX_BYTES:
        raise ImageForensicsError(
            f"Image is {len(raw) / 1e6:.1f} MB; the limit is {MAX_BYTES / 1e6:.0f} MB."
        )

    doc_kind = _is_document_input(raw, filename=filename)
    if doc_kind is not None:
        return _analyse_document(raw, filename=filename, kind=doc_kind)

    if _IMAGE_DEPS_ERROR is not None:
        raise ImportError(str(_IMAGE_DEPS_ERROR)) from _IMAGE_DEPS_ERROR

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:
        raise ImageForensicsError(f"Not a readable image: {exc}") from exc

    width, height = img.size
    if width * height > MAX_PIXELS:
        raise ImageForensicsError(
            f"Image is {width}x{height} ({width * height / 1e6:.0f} MP); "
            f"the limit is {MAX_PIXELS / 1e6:.0f} MP."
        )

    exif = extract_exif(img)

    # Hashes run on a consistently-oriented copy so that the same photo saved
    # with a different EXIF orientation flag still matches perceptually.
    try:
        from PIL import ImageOps
        oriented = ImageOps.exif_transpose(img) or img
    except Exception:
        oriented = img

    return {
        "file": {
            "filename": filename or None,
            "format": img.format,
            "mime": Image.MIME.get(img.format or "", None),
            "mode": img.mode,
            "width": width,
            "height": height,
            "megapixels": round(width * height / 1e6, 2),
            "aspect_ratio": round(width / height, 4) if height else None,
            "animated": getattr(img, "n_frames", 1) > 1,
            **cryptographic_hashes(raw),
        },
        "perceptual": {
            # Three algorithms because they fail differently: aHash on flat
            # images, dHash on heavy crops, pHash on nothing cheaply. Agreement
            # across them is what raises confidence in a match.
            "ahash": average_hash(oriented),
            "dhash": difference_hash(oriented),
            "phash": perceptual_hash(oriented),
            "bits": 64,
            "note": "Compare with hamming_distance(); <=10 bits is a likely match.",
        },
        "exif": exif,
        "signals": provenance_signals(exif, img.format, width, height),
        "provenance": {
            "source": "local",
            "requires_network": False,
            "deterministic": True,
            "note": "Computed from the file bytes. No third-party service involved.",
        },
    }
