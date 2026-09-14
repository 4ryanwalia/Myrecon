package com.aryan.myrecon.data

/**
 * How a JPEG was *compressed*, as opposed to what it says about itself.
 *
 * [ImageProvenance] reads labels, which is conclusive when a label is there and
 * useless when it is not — and it usually is not, because a screenshot, a
 * WhatsApp forward or an Instagram upload strips every label a file had. What
 * none of those can strip is the compression itself: the picture has to be
 * re-encoded to be re-saved, and the encoder leaves its own handwriting in the
 * quantisation tables, the scan layout and the segment order.
 *
 * That handwriting answers a question the labels cannot:
 *
 *  • Camera firmware ships quantisation tables its manufacturer tuned by hand.
 *    No two makers use the same ones, and none of them match the tables printed
 *    in the JPEG specification.
 *  • Ordinary software — Pillow, GIMP, ImageMagick, Android's own encoder, and
 *    every website that resizes an upload — uses the specification's tables
 *    scaled by a quality number, because that is what libjpeg does by default.
 *
 * So a file whose tables are the specification's did not come out of a camera,
 * whatever its EXIF claims, and a file whose tables match no published set very
 * probably did. Neither is proof, and this file returns measurements rather
 * than verdicts; [OriginCheck] is where they get weighed against each other.
 *
 * Pure Kotlin and no Android types, so every byte layout in here is unit
 * testable on the JVM — which it needs to be, because all of them are the kind
 * of thing that can be wrong by one field and still parse.
 */
object JpegStructure {

    enum class Tables {
        /** The tables printed in the specification. Written by ordinary software. */
        Standard,

        /** Tuned tables matching no published set. This is what cameras ship. */
        Custom,

        /** No quantisation table was found — not a readable JPEG. */
        None,
    }

    data class Report(
        val present: Boolean,
        /** Progressive scan. Cameras write baseline; this means software re-saved it. */
        val progressive: Boolean,
        /** Estimated IJG quality, 1–100. Meaningful mainly when [tables] is Standard. */
        val quality: Int?,
        val tables: Tables,
        /** Distance from the closest standard table, summed over all 64 cells. */
        val tableDistance: Int?,
        /** "4:4:4", "4:2:0", … — how much colour detail the encoder threw away. */
        val subsampling: String?,
        val components: Int,
        /** Restart markers: cameras use them for error resilience, encoders rarely do. */
        val restartInterval: Boolean,
        /** Size of the manufacturer's private EXIF block, when one is present. */
        val makerNoteBytes: Int?,
        /** An APP14 "Adobe" segment, written by Adobe applications. */
        val adobeSegment: Boolean,
        /** An APP13 Photoshop resource block. */
        val photoshopBlock: Boolean,
        val jfif: Boolean,
        val exifSegment: Boolean,
        /** Every application segment found, in file order. */
        val segments: List<String>,
    ) {
        val makerNote: Boolean get() = makerNoteBytes != null

        companion object {
            val NotJpeg = Report(
                present = false, progressive = false, quality = null,
                tables = Tables.None, tableDistance = null, subsampling = null,
                components = 0, restartInterval = false, makerNoteBytes = null,
                adobeSegment = false, photoshopBlock = false, jfif = false,
                exifSegment = false, segments = emptyList(),
            )
        }
    }

    // ── Entry point ──────────────────────────────────────────────

    fun analyse(bytes: ByteArray): Report {
        if (ImageProvenance.containerOf(bytes) != ImageProvenance.Container.Jpeg) {
            return Report.NotJpeg
        }
        val segments = ImageProvenance.jpegSegments(bytes)
        if (segments.isEmpty()) return Report.NotJpeg

        var luma: IntArray? = null
        var progressive = false
        var components = 0
        var subsampling: String? = null
        var restart = false
        val names = mutableListOf<String>()
        var makerNote: Int? = null
        var adobe = false
        var photoshop = false
        var jfif = false
        var exifSegment = false

        for ((marker, data) in segments) {
            when {
                marker == 0xDB -> if (luma == null) luma = firstLumaTable(data)

                // SOF0/1 are baseline and extended sequential, SOF2 progressive.
                // The rest are arithmetic-coded or lossless variants nothing in
                // the wild produces, but they carry the same frame header.
                marker in SOF_MARKERS -> {
                    if (marker in PROGRESSIVE_MARKERS) progressive = true
                    frameInfo(data)?.let { (n, s) -> components = n; subsampling = s }
                }

                marker == 0xDD -> restart = true

                marker in 0xE0..0xEF -> {
                    names += appName(marker, data)
                    when {
                        marker == 0xE0 && data.ascii(0, 4) == "JFIF" -> jfif = true
                        marker == 0xE1 && data.ascii(0, 4) == "Exif" -> {
                            exifSegment = true
                            if (makerNote == null) makerNote = makerNoteLength(data)
                        }
                        marker == 0xED && data.ascii(0, 9) == "Photoshop" -> photoshop = true
                        marker == 0xEE && data.ascii(0, 5) == "Adobe" -> adobe = true
                    }
                }
            }
        }

        val fit = luma?.let { closestStandard(it) }

        return Report(
            present = true,
            progressive = progressive,
            quality = fit?.first,
            tables = when {
                luma == null -> Tables.None
                // An exact match is the common case, because libjpeg builds the
                // table the same way this does. The allowance is for encoders
                // that round the final step differently; a camera table sits
                // hundreds away, so nothing is at risk of being confused.
                (fit?.second ?: Int.MAX_VALUE) <= 4 -> Tables.Standard
                else -> Tables.Custom
            },
            tableDistance = fit?.second,
            subsampling = subsampling,
            components = components,
            restartInterval = restart,
            makerNoteBytes = makerNote,
            adobeSegment = adobe,
            photoshopBlock = photoshop,
            jfif = jfif,
            exifSegment = exifSegment,
            segments = names,
        )
    }

    // ── Quantisation tables ──────────────────────────────────────

    /**
     * The first luminance table, returned in natural order.
     *
     * One DQT segment can hold several tables back to back, each introduced by
     * a byte packing the precision into the high nibble and the slot into the
     * low one. Slot 0 is luminance by universal convention — the specification
     * does not require it, but every encoder ever written follows it.
     *
     * Values are stored zigzagged, so they are put back into rows here. Reading
     * them in file order and comparing against a natural-order reference is the
     * obvious way to get this subtly and consistently wrong.
     */
    fun firstLumaTable(data: ByteArray): IntArray? {
        var pos = 0
        while (pos < data.size) {
            val header = data[pos].toInt() and 0xFF
            val wide = (header shr 4) == 1
            val slot = header and 0x0F
            val span = if (wide) 128 else 64
            if (pos + 1 + span > data.size) return null
            if (slot == 0) {
                val zigzag = IntArray(64) { i ->
                    if (wide) {
                        ((data[pos + 1 + i * 2].toInt() and 0xFF) shl 8) or
                            (data[pos + 2 + i * 2].toInt() and 0xFF)
                    } else {
                        data[pos + 1 + i].toInt() and 0xFF
                    }
                }
                return IntArray(64).also { out ->
                    for (i in 0 until 64) out[ZIGZAG[i]] = zigzag[i]
                }
            }
            pos += 1 + span
        }
        return null
    }

    /**
     * The quality setting whose standard table sits closest, and how close.
     *
     * Brute force over all hundred settings rather than the usual trick of
     * inverting the formula from a single cell. The inversion is ambiguous at
     * the top of the range, where several settings land on the same value in
     * whichever cell is picked, and it yields no distance — and the distance is
     * the part that says whether this is a standard table at all.
     */
    fun closestStandard(table: IntArray): Pair<Int, Int>? {
        if (table.size != 64) return null
        var bestQ = 0
        var bestErr = Int.MAX_VALUE
        for (q in 1..100) {
            var err = 0
            for (i in 0 until 64) {
                err += kotlin.math.abs(table[i] - scaled(STANDARD_LUMA[i], q))
                if (err >= bestErr) break
            }
            if (err < bestErr) {
                bestErr = err
                bestQ = q
            }
        }
        return if (bestQ == 0) null else bestQ to bestErr
    }

    /** The scaling libjpeg applies to the reference table for a given quality. */
    private fun scaled(base: Int, quality: Int): Int {
        val q = quality.coerceIn(1, 100)
        val scale = if (q < 50) 5000 / q else 200 - 2 * q
        return ((base * scale + 50) / 100).coerceIn(1, 255)
    }

    // ── Frame header ─────────────────────────────────────────────

    /** Component count, and the subsampling those components describe. */
    private fun frameInfo(data: ByteArray): Pair<Int, String>? {
        // precision(1) height(2) width(2) components(1), then 3 bytes each.
        if (data.size < 6) return null
        val n = data[5].toInt() and 0xFF
        if (n == 0 || data.size < 6 + n * 3) return null
        if (n == 1) return 1 to "None (greyscale)"

        val sampling = data[7].toInt() and 0xFF
        val h = sampling shr 4
        val v = sampling and 0x0F
        val label = when {
            h == 1 && v == 1 -> "4:4:4"
            h == 2 && v == 1 -> "4:2:2"
            h == 1 && v == 2 -> "4:4:0"
            h == 2 && v == 2 -> "4:2:0"
            h == 4 && v == 1 -> "4:1:1"
            else -> "${h}x$v"
        }
        return n to label
    }

    // ── EXIF, far enough in to reach the maker note ──────────────

    /**
     * The length of the manufacturer's private block, or null if there is none.
     *
     * This is the most reliable "a real camera made this" marker available
     * without a network. It is undocumented binary that only the manufacturer's
     * own firmware writes, it is large, and essentially every editor and upload
     * pipeline drops it rather than try to carry it forward — so it survives
     * nothing except being left alone.
     *
     * Reaching it means walking the TIFF structure by hand: IFD0, then the
     * pointer it holds to the Exif sub-directory, then the tag inside that.
     * Every offset in here comes from the file being examined, so every one is
     * checked against the real length before it is followed.
     */
    fun makerNoteLength(app1: ByteArray): Int? {
        // "Exif  " then the TIFF header, which all offsets are relative to.
        if (app1.size < 14 || app1.ascii(0, 4) != "Exif") return null
        val tiff = 6
        val little = when (app1.ascii(tiff, 2)) {
            "II" -> true
            "MM" -> false
            else -> return null
        }

        fun u16(at: Int): Int {
            if (at < 0 || at + 2 > app1.size) return -1
            val a = app1[at].toInt() and 0xFF
            val b = app1[at + 1].toInt() and 0xFF
            return if (little) (b shl 8) or a else (a shl 8) or b
        }

        fun u32(at: Int): Long {
            if (at < 0 || at + 4 > app1.size) return -1
            var value = 0L
            for (i in 0 until 4) {
                val byte = app1[at + if (little) 3 - i else i].toInt() and 0xFF
                value = (value shl 8) or byte.toLong()
            }
            return value
        }

        if (u16(tiff + 2) != 42) return null
        val ifd0Offset = u32(tiff + 4)
        if (ifd0Offset < 8 || ifd0Offset > app1.size) return null

        val exifIfd = findTag(app1, tiff + ifd0Offset.toInt(), tiff, ::u16, ::u32, EXIF_IFD_POINTER)
            ?.takeIf { it in 8..app1.size.toLong() }
            ?.let { tiff + it.toInt() }
            ?: return null

        return findTag(app1, exifIfd, tiff, ::u16, ::u32, MAKER_NOTE, wantCount = true)
            ?.takeIf { it in 1..MAX_MAKER_NOTE }
            ?.toInt()
    }

    /**
     * Read one tag out of a directory: its value, or its length when asked.
     *
     * [wantCount] separates the two things a caller can want. A pointer tag is
     * wanted for where it leads; the maker note is wanted only for how big it
     * is, since its contents are proprietary and there is nothing honest to say
     * about them beyond "the camera wrote this much".
     */
    private fun findTag(
        b: ByteArray,
        ifd: Int,
        tiff: Int,
        u16: (Int) -> Int,
        u32: (Int) -> Long,
        tag: Int,
        wantCount: Boolean = false,
    ): Long? {
        if (ifd < tiff || ifd + 2 > b.size) return null
        val count = u16(ifd)
        if (count <= 0 || count > MAX_IFD_ENTRIES) return null
        for (i in 0 until count) {
            val entry = ifd + 2 + i * 12
            if (entry + 12 > b.size) return null
            if (u16(entry) != tag) continue
            return if (wantCount) u32(entry + 4) else u32(entry + 8)
        }
        return null
    }

    // ── Naming ───────────────────────────────────────────────────

    private fun appName(marker: Int, data: ByteArray): String {
        val n = marker - 0xE0
        val id = data.ascii(0, 12)
            .takeWhile { it.isLetterOrDigit() || it == '.' || it == '_' || it == '-' }
        return if (id.isBlank()) "APP$n" else "APP$n $id"
    }

    private fun ByteArray.ascii(at: Int, len: Int): String =
        if (at < 0 || at + len > size) "" else String(this, at, len, Charsets.ISO_8859_1)

    private val SOF_MARKERS = setOf(
        0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
    )
    private val PROGRESSIVE_MARKERS = setOf(0xC2, 0xC6, 0xCA, 0xCE)
    private const val EXIF_IFD_POINTER = 0x8769
    private const val MAKER_NOTE = 0x927C
    private const val MAX_MAKER_NOTE = 16L * 1024 * 1024
    private const val MAX_IFD_ENTRIES = 512

    /** Natural-order position of each zigzag index. */
    private val ZIGZAG = intArrayOf(
        0, 1, 8, 16, 9, 2, 3, 10,
        17, 24, 32, 25, 18, 11, 4, 5,
        12, 19, 26, 33, 40, 48, 41, 34,
        27, 20, 13, 6, 7, 14, 21, 28,
        35, 42, 49, 56, 57, 50, 43, 36,
        29, 22, 15, 23, 30, 37, 44, 51,
        58, 59, 52, 45, 38, 31, 39, 46,
        53, 60, 61, 54, 47, 55, 62, 63,
    )

    /** Annex K of the JPEG specification, in natural order. */
    private val STANDARD_LUMA = intArrayOf(
        16, 11, 10, 16, 24, 40, 51, 61,
        12, 12, 14, 19, 26, 58, 60, 55,
        14, 13, 16, 24, 40, 57, 69, 56,
        14, 17, 22, 29, 51, 87, 80, 62,
        18, 22, 37, 56, 68, 109, 103, 77,
        24, 35, 55, 64, 81, 104, 113, 92,
        49, 64, 78, 87, 103, 121, 120, 101,
        72, 92, 95, 98, 112, 100, 103, 99,
    )
}
