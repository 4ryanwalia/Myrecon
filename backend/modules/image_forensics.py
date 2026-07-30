"""
Image forensics — deterministic, local, provider-free.

Everything in this module is computed from the image bytes themselves. There
are no network calls and no API keys, so these findings are always available
and always reproducible: the same bytes yield the same report.

That property matters for an investigation tool. Anything derived from a
third-party model (OCR, landmark, logo, face attributes) is a *claim* with a
confidence attached and lives behind the provider registry instead — see
modules/providers/. This module only reports what the file actually contains.

Deliberately NOT here:
  • Face recognition / identity inference. Detecting that a face is present is
    a geometry question; asserting *whose* face it is from appearance alone is
    not something this platform does.
  • Anything requiring a model download or a system binary. This runs inside a
    512 MB Render worker.

Dependencies: Pillow (image decode + EXIF), numpy (hash DCT). Both small.
"""

from __future__ import annotations

import hashlib
import io
from datetime import datetime
from typing import Any, Optional

import numpy as np
from PIL import ExifTags, Image, ImageFile

# A truncated upload should degrade to a partial read rather than raising, so
# forensics still returns what it can for a damaged file.
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Refuse absurd dimensions before allocating pixels. Pillow's own bomb guard
# raises a warning; this makes the limit explicit and returns a clean error.
MAX_PIXELS = 80_000_000          # ~80 MP
MAX_BYTES = 25 * 1024 * 1024     # 25 MB

# Perceptual hash sizes. 8x8 is the conventional choice: 64-bit digests whose
# Hamming distance is meaningful up to roughly 10 bits.
_AHASH_SIZE = 8
_DHASH_SIZE = 8
_PHASH_SIZE = 32                 # DCT input; low-frequency 8x8 block is kept

# Tag id -> name lookups, inverted once at import.
_EXIF_TAGS = {v: k for k, v in ExifTags.TAGS.items()}
_GPS_TAGS = {v: k for k, v in ExifTags.GPSTAGS.items()}


class ImageForensicsError(ValueError):
    """Raised for input we refuse to process (too large, not an image)."""


# ──────────────────────────────────────────────────────────────────────
#  Hashing
# ──────────────────────────────────────────────────────────────────────

def cryptographic_hashes(raw: bytes) -> dict:
    """
    Exact-duplicate identifiers. Two files share these only if their bytes are
    identical, so they answer "is this the same file?" but say nothing about
    visual similarity — a re-encode changes them completely.
    """
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "md5": hashlib.md5(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _to_luma_array(img: Image.Image, size: int) -> np.ndarray:
    """Downscale to size×size greyscale as float — the common front half of
    every perceptual hash below."""
    small = img.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    return np.asarray(small, dtype=np.float64)


def _bits_to_hex(bits: np.ndarray) -> str:
    """Pack a boolean array (row-major) into a lowercase hex digest."""
    flat = bits.flatten()
    # np.packbits is big-endian per byte, which keeps the digest stable across
    # platforms and matches the conventional imagehash string layout.
    return np.packbits(flat).tobytes().hex()


def average_hash(img: Image.Image) -> str:
    """aHash — each pixel brighter than the mean becomes a 1. Cheap, tolerant
    of re-compression, but easily collided by flat images."""
    px = _to_luma_array(img, _AHASH_SIZE)
    return _bits_to_hex(px > px.mean())


def difference_hash(img: Image.Image) -> str:
    """dHash — encodes horizontal gradient direction. Robust to brightness and
    scaling shifts, which makes it the best single choice for "same photo,
    different upload" matching."""
    # Resized directly rather than via _to_luma_array, which squares its input:
    # dHash needs one extra column so each row yields SIZE comparisons.
    small = img.convert("L").resize((_DHASH_SIZE + 1, _DHASH_SIZE),
                                    Image.Resampling.LANCZOS)
    px = np.asarray(small, dtype=np.float64)
    return _bits_to_hex(px[:, 1:] > px[:, :-1])


def perceptual_hash(img: Image.Image) -> str:
    """
    pHash — DCT-II on a 32×32 luma grid, keeping the top-left 8×8 block of low
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


def _dct2(a: np.ndarray) -> np.ndarray:
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
    honest about what the metric is — it is not a probability."""
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

    GPS presence is one of the highest-value findings in image forensics — it
    places a device at a location and time — so the raw reference letters are
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


def extract_exif(img: Image.Image) -> dict:
    """
    Pull the EXIF blocks that matter for provenance: camera identity, capture
    time, software, and GPS.

    Absence is itself a signal and is reported explicitly — most social
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
    # wants — DateTimeOriginal, ISO, aperture, focal length, lens, body serial
    # — live in the Exif sub-IFD behind the ExifOffset pointer, so both must be
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
#  Provenance signals
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
    Full local forensic report for one image.

    Args:
        raw: the image bytes as uploaded.
        filename: original name, recorded for provenance only — never trusted
            for type detection, which comes from the decoded content.

    Returns a JSON-serialisable dict. Raises ImageForensicsError for input we
    decline to process.
    """
    if not raw:
        raise ImageForensicsError("Empty upload.")
    if len(raw) > MAX_BYTES:
        raise ImageForensicsError(
            f"Image is {len(raw) / 1e6:.1f} MB; the limit is {MAX_BYTES / 1e6:.0f} MB."
        )

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
