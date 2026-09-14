package com.aryan.myrecon.data

/**
 * Remove everything a file says about its owner, without touching the picture.
 *
 * The obvious implementation — decode to a bitmap and re-encode — throws away
 * all metadata, and also re-compresses the image. Nobody wants a visibly worse
 * copy of their own photo as the price of privacy, and a lossy round trip is
 * also the one step that would invalidate the hashes the rest of this screen
 * reports.
 *
 * So this edits the container instead. JPEG marker segments and PNG chunks are
 * both length-prefixed, which means the metadata blocks can be dropped and the
 * compressed image data copied through byte for byte. The result decodes to
 * exactly the same pixels.
 *
 * Pure Kotlin, no Android types: a stripper that quietly corrupts files is
 * worse than none, so this has to be testable without a device.
 */
object MetadataStrip {

    data class Result(
        val bytes: ByteArray,
        /** Human names of what came out, for telling the user what changed. */
        val removed: List<String>,
        val bytesSaved: Int,
    ) {
        // Data classes with an array member need these by hand, and leaving the
        // identity versions in place would make two identical results unequal.
        override fun equals(other: Any?): Boolean =
            this === other || (other is Result && bytes.contentEquals(other.bytes) &&
                removed == other.removed && bytesSaved == other.bytesSaved)

        override fun hashCode(): Int =
            31 * (31 * bytes.contentHashCode() + removed.hashCode()) + bytesSaved
    }

    /** Whether a clean copy can be made losslessly for this file. */
    fun supports(bytes: ByteArray): Boolean = when (ImageProvenance.containerOf(bytes)) {
        ImageProvenance.Container.Jpeg, ImageProvenance.Container.Png -> true
        else -> false
    }

    fun strip(bytes: ByteArray): Result? = when (ImageProvenance.containerOf(bytes)) {
        ImageProvenance.Container.Jpeg -> stripJpeg(bytes)
        ImageProvenance.Container.Png -> stripPng(bytes)
        else -> null
    }

    // ── JPEG ─────────────────────────────────────────────────────

    /**
     * Drop the application segments that carry metadata, keep the rest.
     *
     * Three are kept on purpose, and none of them can identify anyone:
     *
     *  • APP0 (JFIF) — the density header. Old decoders expect it.
     *  • APP2 when it holds an ICC profile — remove it and colours shift, which
     *    would be a visible change to the image the caller was told is intact.
     *  • APP14 (Adobe) — carries the colour transform flag. Dropping it turns
     *    some JPEGs into inverted or wrongly-channelled images.
     *
     * Everything else goes: APP1 is EXIF and XMP, APP11 is C2PA, APP13 is IPTC
     * and Photoshop resources, and COM is a free-text comment.
     */
    private fun stripJpeg(b: ByteArray): Result? {
        val out = java.io.ByteArrayOutputStream(b.size)
        val removed = linkedSetOf<String>()
        out.write(0xFF); out.write(0xD8)

        var pos = 2
        while (pos + 4 <= b.size) {
            if (b[pos] != 0xFF.toByte()) return null
            val marker = b[pos + 1].toInt() and 0xFF

            if (marker == 0xD8 || marker == 0x01 || marker in 0xD0..0xD7) {
                out.write(0xFF); out.write(marker)
                pos += 2
                continue
            }

            // Start of scan: compressed pixel data from here on. Copy it
            // verbatim rather than parsing — the entropy stream contains byte
            // pairs that look exactly like markers.
            //
            // It is copied only as far as the end-of-image marker, though.
            // Samsung and Pixel motion photos append an entire MP4 after EOI,
            // and a "clean copy" that still carries three seconds of video of
            // the moments around the shot is not clean. FF D9 is unambiguous
            // here: inside entropy data every FF is stuffed as FF 00 or is a
            // restart marker, so the first one found is the real end.
            if (marker == 0xDA) {
                val eoi = indexOfEoi(b, pos)
                val end = if (eoi >= 0) eoi + 2 else b.size
                out.write(b, pos, end - pos)
                if (end < b.size) removed += "A hidden video clip (motion photo)"
                pos = b.size
                break
            }
            if (marker == 0xD9) {
                out.write(0xFF); out.write(marker)
                if (pos + 2 < b.size) removed += "Hidden data stored after the picture"
                pos = b.size
                break
            }

            val len = ((b[pos + 2].toInt() and 0xFF) shl 8) or (b[pos + 3].toInt() and 0xFF)
            if (len < 2 || pos + 2 + len > b.size) return null
            val payload = b.copyOfRange(pos + 4, pos + 2 + len)

            val name = jpegMetadataName(marker, payload)
            if (name != null) {
                removed += name
            } else {
                out.write(0xFF); out.write(marker)
                out.write(b, pos + 2, len)
            }
            pos += 2 + len
        }

        // A truncated file would otherwise be silently rewritten shorter than
        // it started, which is data loss dressed up as a privacy feature.
        if (pos < b.size) out.write(b, pos, b.size - pos)

        val result = out.toByteArray()
        return Result(result, removed.toList(), b.size - result.size)
    }

    /** Offset of the end-of-image marker at or after [from], or -1. */
    private fun indexOfEoi(b: ByteArray, from: Int): Int {
        var i = from
        while (i + 1 < b.size) {
            if (b[i] == 0xFF.toByte() && b[i + 1] == 0xD9.toByte()) return i
            i++
        }
        return -1
    }

    /** The label for a segment worth removing, or null to keep it. */
    private fun jpegMetadataName(marker: Int, payload: ByteArray): String? {
        fun starts(s: String) =
            payload.size >= s.length &&
                String(payload, 0, s.length, Charsets.ISO_8859_1) == s

        return when {
            marker == 0xE0 -> null                       // JFIF density
            marker == 0xE2 && starts("ICC_PROFILE") -> null
            marker == 0xEE && starts("Adobe") -> null
            marker == 0xE1 && starts("Exif") -> "Camera, date and location (EXIF)"
            marker == 0xE1 && starts("http://ns.adobe.com/xap") -> "Extra hidden details"
            marker == 0xE1 -> "Hidden details"
            marker == 0xEB -> "The record of how it was made"
            marker == 0xED -> "Editing app data"
            marker == 0xFE -> "A hidden comment"
            marker in 0xE2..0xEF -> "Extra hidden data"
            else -> null
        }
    }

    // ── PNG ──────────────────────────────────────────────────────

    /**
     * Keep only the chunks that affect how the image decodes and displays.
     *
     * A whitelist rather than a blacklist: PNG is extensible, so an unknown
     * chunk could be anything, and "anything" is exactly what should not be
     * carried into a copy the user is about to share.
     */
    private fun stripPng(b: ByteArray): Result? {
        val chunks = ImageProvenance.pngChunks(b)
        if (chunks.isEmpty()) return null

        val out = java.io.ByteArrayOutputStream(b.size)
        out.write(b, 0, 8)
        val removed = linkedSetOf<String>()

        for ((type, data) in chunks) {
            if (type in PNG_KEEP) {
                writeChunk(out, type, data)
            } else {
                removed += pngChunkName(type)
            }
        }

        val result = out.toByteArray()
        return Result(result, removed.toList(), b.size - result.size)
    }

    private fun writeChunk(out: java.io.ByteArrayOutputStream, type: String, data: ByteArray) {
        val len = data.size
        out.write((len ushr 24) and 0xFF); out.write((len ushr 16) and 0xFF)
        out.write((len ushr 8) and 0xFF); out.write(len and 0xFF)
        val typeBytes = type.toByteArray(Charsets.ISO_8859_1)
        out.write(typeBytes)
        out.write(data)

        // The CRC covers the type and the payload but not the length, and it
        // has to be recomputed rather than copied: a chunk written back with a
        // stale CRC makes the whole file unreadable to a strict decoder.
        val crc = java.util.zip.CRC32()
        crc.update(typeBytes)
        crc.update(data)
        val v = crc.value
        out.write(((v ushr 24) and 0xFF).toInt()); out.write(((v ushr 16) and 0xFF).toInt())
        out.write(((v ushr 8) and 0xFF).toInt()); out.write((v and 0xFF).toInt())
    }

    private fun pngChunkName(type: String): String = when (type) {
        "tEXt", "zTXt", "iTXt" -> "Hidden text"
        "eXIf" -> "Camera, date and location (EXIF)"
        "caBX" -> "The record of how it was made"
        "tIME" -> "The date it was last saved"
        else -> "Extra hidden data"
    }

    private val PNG_KEEP = setOf(
        // Required for the image to exist at all.
        "IHDR", "PLTE", "IDAT", "IEND",
        // Affect how it renders: transparency, colour and gamma.
        "tRNS", "gAMA", "cHRM", "sRGB", "iCCP", "sBIT", "bKGD", "pHYs",
        // APNG animation. Dropping these turns an animation into one frame.
        "acTL", "fcTL", "fdAT",
    )
}
