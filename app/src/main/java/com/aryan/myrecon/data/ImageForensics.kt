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
        val provenance: ImageProvenance.Report,
        val thumbnail: ThumbnailCheck,
        /** What this file discloses about the person who made it. */
        val leaks: List<Leak>,
        val cleanCopy: CleanCopyPlan,
    )

    /**
     * The embedded thumbnail against the image it claims to represent.
     *
     * Cameras write a small preview at the moment of capture. Most editors
     * rewrite the full image and leave that preview alone, so a thumbnail that
     * no longer looks like the picture is evidence the picture changed after it
     * was taken — deterministic, reproducible by anyone, and needing no model.
     */
    data class ThumbnailCheck(
        val present: Boolean,
        val width: Int? = null,
        val height: Int? = null,
        /** Differing bits between the two pHashes, out of 64. */
        val distance: Int? = null,
        val verdict: Match = Match.NoThumbnail,
    )

    enum class Match {
        NoThumbnail,

        /** The preview matches. No evidence of a later edit. */
        Consistent,

        /** Different enough to notice, not enough to claim anything. */
        Inconclusive,

        /** The preview is a different shape — the image was cropped. */
        Cropped,

        /** The preview shows a different picture. */
        Mismatch,
    }

    /** Something the file gives away about its owner. */
    data class Leak(val what: String, val detail: String, val severity: String)

    /** What a stripped copy would remove, worked out from the real bytes. */
    data class CleanCopyPlan(
        val supported: Boolean,
        val removes: List<String>,
        val bytesSaved: Int,
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
        val artist: String? = null,
        val owner: String? = null,
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

            // Built once and shared: the thumbnail check needs the same
            // instance the tag read used, and parsing the file twice to get it
            // would double the work for nothing.
            val exifInterface = runCatching { ExifInterface(bytes.inputStream()) }.getOrNull()
            val exif = readExif(exifInterface)
            val hashes = hashesFor(bytes)
            val provenance = ImageProvenance.analyse(bytes, exif.software)
            val thumbnail = thumbnailCheck(
                exifInterface, hashes.phash, bounds.outWidth, bounds.outHeight,
            )
            val cleanCopy = cleanCopyPlan(bytes)

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
                signals = signalsFor(
                    exif, bounds.outMimeType, bounds.outWidth, bounds.outHeight, thumbnail,
                ),
                provenance = provenance,
                thumbnail = thumbnail,
                leaks = leaksFor(exif, provenance, cleanCopy),
                cleanCopy = cleanCopy,
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
    private fun readExif(exif: ExifInterface?): Exif {
        if (exif == null) return Exif(present = false)

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
            artist = tag(ExifInterface.TAG_ARTIST),
            owner = tag(ExifInterface.TAG_CAMERA_OWNER_NAME),
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

    // ── Embedded thumbnail ───────────────────────────────────────

    /**
     * Compare the capture-time preview against the image as it stands now.
     *
     * Two failure modes are separated on purpose, because they mean different
     * things and only one of them is about content. A preview with a different
     * *shape* means the frame was cropped, which is worth saying plainly; a
     * preview of the same shape showing a different *picture* is the tamper
     * signal. Running a pHash across a crop would only produce a large distance
     * and a vague accusation, so the shape is checked first and the hashes are
     * never compared across different aspect ratios.
     *
     * The threshold is deliberately loose. A thumbnail is a heavily compressed
     * 160x120 preview of a 12-megapixel frame, so some distance is normal, and
     * the middle band is reported as inconclusive rather than forced into a
     * verdict. Calling an untouched holiday photo doctored is a much worse
     * failure than saying nothing.
     */
    private fun thumbnailCheck(
        exif: ExifInterface?,
        mainPhash: String,
        mainWidth: Int,
        mainHeight: Int,
    ): ThumbnailCheck {
        val thumb = exif?.takeIf { it.hasThumbnail() }?.thumbnailBytes
            ?: return ThumbnailCheck(present = false)

        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(thumb, 0, thumb.size, bounds)
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0 || mainWidth <= 0 || mainHeight <= 0) {
            return ThumbnailCheck(present = true)
        }

        val thumbAspect = bounds.outWidth.toDouble() / bounds.outHeight
        val mainAspect = mainWidth.toDouble() / mainHeight
        if (kotlin.math.abs(thumbAspect - mainAspect) / mainAspect > 0.06) {
            return ThumbnailCheck(
                present = true,
                width = bounds.outWidth,
                height = bounds.outHeight,
                verdict = Match.Cropped,
            )
        }

        val bitmap = BitmapFactory.decodeByteArray(thumb, 0, thumb.size)
            ?: return ThumbnailCheck(present = true, bounds.outWidth, bounds.outHeight)
        val thumbPhash = try {
            PerceptualHash.perceptual(lumaGrid(bitmap, 32, 32))
        } finally {
            bitmap.recycle()
        }

        val distance = PerceptualHash.hamming(mainPhash, thumbPhash)
        return ThumbnailCheck(
            present = true,
            width = bounds.outWidth,
            height = bounds.outHeight,
            distance = distance,
            verdict = when {
                distance == null -> Match.Inconclusive
                distance <= 12 -> Match.Consistent
                distance >= 24 -> Match.Mismatch
                else -> Match.Inconclusive
            },
        )
    }

    // ── Clean copy ───────────────────────────────────────────────

    /**
     * What stripping would actually remove, computed from the bytes.
     *
     * Run now so the offer can name the real blocks in this file rather than a
     * generic promise. The stripped bytes themselves are discarded — holding a
     * second copy of a 25 MB image for the whole time a report is on screen, on
     * the chance the user taps the button, is not a trade worth making.
     */
    private fun cleanCopyPlan(bytes: ByteArray): CleanCopyPlan {
        if (!MetadataStrip.supports(bytes)) {
            return CleanCopyPlan(supported = false, removes = emptyList(), bytesSaved = 0)
        }
        val stripped = MetadataStrip.strip(bytes)
            ?: return CleanCopyPlan(supported = false, removes = emptyList(), bytesSaved = 0)
        return CleanCopyPlan(
            supported = true,
            removes = stripped.removed,
            bytesSaved = stripped.bytesSaved,
        )
    }

    // ── What the file gives away ─────────────────────────────────

    /**
     * The same findings, read back from the owner's side.
     *
     * Everything above answers "what is this file". This answers "what does it
     * say about me", which is the question the person holding the phone
     * actually has before they upload something — and the one that turns a
     * report into a decision.
     */
    private fun leaksFor(
        exif: Exif,
        provenance: ImageProvenance.Report,
        plan: CleanCopyPlan,
    ): List<Leak> {
        val out = mutableListOf<Leak>()

        if (exif.gps.present && exif.gps.latitude != null && exif.gps.longitude != null) {
            out += Leak(
                "Where you were",
                "The file records %.6f, %.6f — a specific spot, not a general area. On a photo "
                    .format(exif.gps.latitude, exif.gps.longitude) +
                    "taken at home, that is your address.",
                "high",
            )
        }
        exif.capturedAt?.let {
            out += Leak(
                "When you were there",
                "Captured $it. Combined with a location this places you somewhere at a time.",
                if (exif.gps.present) "high" else "medium",
            )
        }
        exif.serial?.let {
            out += Leak(
                "Your camera's serial number",
                "Serial $it identifies one physical device. Anyone holding two of your photos " +
                    "can prove the same camera took both, even across anonymous accounts.",
                "high",
            )
        }
        listOfNotNull(exif.artist, exif.owner).distinct().forEach {
            out += Leak(
                "Your name",
                "Written into the file as the owner or author: \"$it\".",
                "high",
            )
        }
        provenance.prompt?.let {
            out += Leak(
                "The prompt you typed",
                "The full generation prompt is stored inside the image and travels with it. " +
                    "Anyone who downloads this file can read exactly what was asked for.",
                "high",
            )
        }
        if (exif.make != null || exif.model != null) {
            out += Leak(
                "The device you used",
                listOfNotNull(exif.make, exif.model).joinToString(" ") +
                    ". Narrows down who took it, though it does not identify you alone.",
                "low",
            )
        }
        if (plan.removes.any { it.contains("appended", ignoreCase = true) }) {
            out += Leak(
                "A video you may not know is there",
                "Data is appended after the end of the image. Motion photos store a few " +
                    "seconds of video and audio from around the moment of the shot, and it " +
                    "goes wherever the photo goes.",
                "high",
            )
        }
        return out
    }

    // ── Provenance ───────────────────────────────────────────────

    private fun signalsFor(
        exif: Exif,
        mime: String?,
        width: Int,
        height: Int,
        thumbnail: ThumbnailCheck,
    ): List<Signal> {
        val out = mutableListOf<Signal>()

        when (thumbnail.verdict) {
            Match.Mismatch -> out += Signal(
                "Embedded preview shows a different picture",
                "The camera wrote a preview at capture, and it no longer matches the image " +
                    "(${thumbnail.distance} of 64 bits differ). Editors usually rewrite the " +
                    "full image and leave the preview behind, so this is a sign the picture " +
                    "was changed after it was taken. Re-run it yourself: the comparison is " +
                    "just two perceptual hashes.",
                "high",
            )
            Match.Cropped -> out += Signal(
                "Cropped after capture",
                "The embedded preview is ${thumbnail.width}x${thumbnail.height}, a different " +
                    "shape from the ${width}x$height image. The frame was cut down after the " +
                    "camera wrote it.",
                "medium",
            )
            Match.Consistent -> out += Signal(
                "Embedded preview matches",
                "The capture-time preview still matches the image (${thumbnail.distance} of 64 " +
                    "bits differ). No sign of an edit after capture — though an editor that " +
                    "rewrites both would leave no trace here.",
                "low",
            )
            Match.Inconclusive, Match.NoThumbnail -> Unit
        }

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
