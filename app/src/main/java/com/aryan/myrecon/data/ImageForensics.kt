package com.aryan.myrecon.data

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.exifinterface.media.ExifInterface
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.security.MessageDigest

/**
 * Local image forensics.
 *
 * Everything here is derived from the file's own bytes, so it needs no network,
 * no key, and returns the same answer every time. That property matters: a
 * finding a user can reproduce is evidence, where a model's opinion is not.
 *
 * Anything requiring a third-party model — OCR, landmark or logo recognition —
 * is deliberately absent. Face detection is available via ML Kit but reports
 * geometry only; this platform does not infer identity from appearance.
 */
object ImageForensics {

    /** Refuse absurd input before allocating pixels for it. */
    private const val MAX_BYTES = 25L * 1024 * 1024

    data class Report(
        val file: FileFacts,
        val exif: Exif,
        val hashes: Hashes,
        val signals: List<Signal>,
    )

    data class FileFacts(
        val name: String?,
        val mime: String?,
        val sizeBytes: Long,
        val width: Int,
        val height: Int,
        val megapixels: Double,
        val sha256: String,
    )

    data class Exif(
        val present: Boolean,
        val make: String? = null,
        val model: String? = null,
        val lens: String? = null,
        val serial: String? = null,
        val software: String? = null,
        val capturedAt: String? = null,
        val modifiedAt: String? = null,
        val iso: String? = null,
        val aperture: String? = null,
        val exposure: String? = null,
        val focalLength: String? = null,
        val gps: Gps = Gps(false),
    )

    data class Gps(
        val present: Boolean,
        val latitude: Double? = null,
        val longitude: Double? = null,
        val altitudeM: Double? = null,
    )

    data class Hashes(val ahash: String, val dhash: String, val phash: String)

    /** An observation with its basis, not a verdict. */
    data class Signal(val label: String, val detail: String, val weight: String)

    // ── Entry point ──────────────────────────────────────────────

    suspend fun analyse(context: Context, uri: Uri): Result<Report> = withContext(Dispatchers.IO) {
        runCatching {
            val resolver = context.contentResolver

            val bytes = resolver.openInputStream(uri)?.use { it.readBytes() }
                ?: error("The image could not be opened.")
            require(bytes.isNotEmpty()) { "The file is empty." }
            require(bytes.size <= MAX_BYTES) {
                "Image is ${"%.1f".format(bytes.size / 1e6)} MB; the limit is 25 MB."
            }

            // Dimensions first, without decoding pixels.
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
            require(bounds.outWidth > 0 && bounds.outHeight > 0) { "Not a readable image." }

            val exif = readExif(bytes)
            val hashes = hashesFor(bytes)

            Report(
                file = FileFacts(
                    name = displayName(context, uri),
                    mime = bounds.outMimeType ?: resolver.getType(uri),
                    sizeBytes = bytes.size.toLong(),
                    width = bounds.outWidth,
                    height = bounds.outHeight,
                    megapixels = (bounds.outWidth.toLong() * bounds.outHeight) / 1e6,
                    sha256 = sha256(bytes),
                ),
                exif = exif,
                hashes = hashes,
                signals = signalsFor(exif, bounds.outMimeType, bounds.outWidth, bounds.outHeight),
            )
        }
    }

    // ── EXIF ─────────────────────────────────────────────────────

    /**
     * androidx's ExifInterface resolves the Exif sub-IFD transparently, so
     * DateTimeOriginal, ISO, aperture and body serial all come back from a
     * plain getAttribute. The Python port had to walk both IFDs by hand, and
     * silently returned null for most of the capture block until it did.
     */
    private fun readExif(bytes: ByteArray): Exif {
        val exif = runCatching { ExifInterface(bytes.inputStream()) }.getOrNull()
            ?: return Exif(present = false)

        fun tag(name: String): String? =
            exif.getAttribute(name)?.trim()?.takeIf { it.isNotBlank() && it != "0" }

        val hasAny = listOf(
            ExifInterface.TAG_MAKE, ExifInterface.TAG_MODEL, ExifInterface.TAG_DATETIME,
            ExifInterface.TAG_DATETIME_ORIGINAL, ExifInterface.TAG_SOFTWARE,
        ).any { exif.getAttribute(it) != null }

        val latLong = FloatArray(2)
        val hasGps = exif.getLatLong(latLong)
        val altitude = exif.getAltitude(Double.NaN).takeIf { !it.isNaN() }

        return Exif(
            present = hasAny || hasGps,
            make = tag(ExifInterface.TAG_MAKE),
            model = tag(ExifInterface.TAG_MODEL),
            lens = tag(ExifInterface.TAG_LENS_MODEL),
            serial = tag(ExifInterface.TAG_BODY_SERIAL_NUMBER),
            software = tag(ExifInterface.TAG_SOFTWARE),
            capturedAt = isoDate(tag(ExifInterface.TAG_DATETIME_ORIGINAL)),
            modifiedAt = isoDate(tag(ExifInterface.TAG_DATETIME)),
            iso = tag(ExifInterface.TAG_PHOTOGRAPHIC_SENSITIVITY),
            aperture = tag(ExifInterface.TAG_F_NUMBER)?.let { "f/$it" },
            exposure = tag(ExifInterface.TAG_EXPOSURE_TIME)?.let { "${it}s" },
            focalLength = tag(ExifInterface.TAG_FOCAL_LENGTH),
            gps = if (hasGps) {
                Gps(true, latLong[0].toDouble(), latLong[1].toDouble(), altitude)
            } else Gps(false),
        )
    }

    /** EXIF stamps are "YYYY:MM:DD HH:MM:SS" with no zone. Normalise, don't invent one. */
    private fun isoDate(raw: String?): String? {
        val s = raw?.trim() ?: return null
        return Regex("""^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}:\d{2}:\d{2})""")
            .find(s)?.let { "${it.groupValues[1]}-${it.groupValues[2]}-${it.groupValues[3]} ${it.groupValues[4]}" }
            ?: s
    }

    // ── Hashes ───────────────────────────────────────────────────

    private fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it) }

    /**
     * Downsampled once, then reused for all three digests.
     *
     * Decoding at full resolution to produce a 32x32 grid would allocate tens
     * of megabytes for nothing, and a phone will not thank you for it.
     */
    private fun hashesFor(bytes: ByteArray): Hashes {
        val opts = BitmapFactory.Options().apply { inSampleSize = sampleSizeFor(bytes, 64) }
        val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opts)
            ?: error("The image could not be decoded.")
        return try {
            Hashes(
                ahash = PerceptualHash.average(lumaGrid(bitmap, 8, 8)),
                // dHash needs one extra column so each row yields 8 comparisons.
                dhash = PerceptualHash.difference(lumaGrid(bitmap, 9, 8)),
                phash = PerceptualHash.perceptual(lumaGrid(bitmap, 32, 32)),
            )
        } finally {
            bitmap.recycle()
        }
    }

    private fun sampleSizeFor(bytes: ByteArray, target: Int): Int {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        var sample = 1
        var longest = maxOf(bounds.outWidth, bounds.outHeight)
        while (longest / 2 >= target) {
            longest /= 2
            sample *= 2
        }
        return sample
    }

    /** Scale to w x h and reduce to perceptual luma. */
    private fun lumaGrid(source: Bitmap, w: Int, h: Int): IntArray {
        val scaled = Bitmap.createScaledBitmap(source, w, h, true)
        val pixels = IntArray(w * h)
        scaled.getPixels(pixels, 0, w, 0, 0, w, h)
        if (scaled != source) scaled.recycle()
        return IntArray(pixels.size) { i ->
            val p = pixels[i]
            // Rec. 601 luma — matches how the eye weights the channels, so the
            // digest tracks perceived brightness rather than raw averages.
            val r = (p shr 16) and 0xFF
            val g = (p shr 8) and 0xFF
            val b = p and 0xFF
            ((r * 299 + g * 587 + b * 114) / 1000)
        }
    }

    // ── Provenance ───────────────────────────────────────────────

    private fun signalsFor(exif: Exif, mime: String?, width: Int, height: Int): List<Signal> {
        val out = mutableListOf<Signal>()

        if (!exif.present) {
            out += Signal(
                "No EXIF metadata",
                "The file carries no metadata block. Most social and messaging platforms strip " +
                    "it on upload, so this is expected for a downloaded image and is not itself " +
                    "a sign of tampering.",
                "high",
            )
        } else {
            if (exif.make == null && exif.model == null) {
                out += Signal(
                    "Metadata present but no camera identity",
                    "Tags exist without a make or model, which is typical of an image re-saved " +
                        "by an editor rather than one straight off a device.",
                    "medium",
                )
            }
            exif.software?.let {
                out += Signal(
                    "Processed by software",
                    "The Software tag reads \"$it\", so an application wrote this file rather " +
                        "than a camera exporting it directly.",
                    "high",
                )
            }
            exif.serial?.let {
                out += Signal(
                    "Camera serial number present",
                    "A body serial number is recorded. This ties the file to one specific " +
                        "physical device and survives copying.",
                    "high",
                )
            }
            if (exif.capturedAt != null && exif.modifiedAt != null &&
                exif.capturedAt != exif.modifiedAt
            ) {
                out += Signal(
                    "Modified after capture",
                    "Captured ${exif.capturedAt}, last written ${exif.modifiedAt}. The gap " +
                        "indicates a later re-save.",
                    "medium",
                )
            }
        }

        if (exif.gps.present) {
            out += Signal(
                "GPS coordinates embedded",
                "The file records where it was taken. This is the strongest location finding " +
                    "available from an image, and needs no external service to read.",
                "high",
            )
        }

        if (mime?.contains("png") == true && !exif.present) {
            out += Signal(
                "Consistent with a screenshot",
                "PNG with no metadata is the usual signature of a screen capture or a generated " +
                    "image rather than a photograph.",
                "low",
            )
        }

        if (width > 0 && height > 0 && kotlin.math.abs(width.toDouble() / height - 1.0) < 0.01) {
            out += Signal(
                "Square aspect ratio",
                "Exactly square dimensions suggest a deliberate crop, commonly a profile picture.",
                "low",
            )
        }

        return out
    }

    private fun displayName(context: Context, uri: Uri): String? = runCatching {
        context.contentResolver.query(uri, null, null, null, null)?.use { c ->
            val i = c.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
            if (i >= 0 && c.moveToFirst()) c.getString(i) else null
        }
    }.getOrNull()
}
