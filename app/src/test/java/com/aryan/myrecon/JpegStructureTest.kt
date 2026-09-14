package com.aryan.myrecon

import com.aryan.myrecon.data.JpegStructure
import org.junit.Assert.*
import org.junit.Test
import java.awt.image.BufferedImage
import java.io.ByteArrayOutputStream
import javax.imageio.IIOImage
import javax.imageio.ImageIO
import javax.imageio.ImageWriteParam
import javax.imageio.stream.MemoryCacheImageOutputStream

/**
 * The encoder's handwriting.
 *
 * Every JPEG here is encoded by ImageIO at test time rather than hand-built,
 * because ImageIO writes through libjpeg — the same library behind Pillow,
 * GIMP, ImageMagick and most of the web. So "does this correctly recognise
 * ordinary software" is answered by ordinary software rather than by a fixture
 * written to agree with the parser.
 *
 * The camera side cannot be tested that way: there is no camera in a unit test.
 * What is tested instead is that a table which is *not* the standard one is
 * measured as far from it, which is the whole basis of the distinction.
 */
class JpegStructureTest {

    // ── Fixtures ─────────────────────────────────────────────────

    private fun image(w: Int = 96, h: Int = 96): BufferedImage {
        val img = BufferedImage(w, h, BufferedImage.TYPE_INT_RGB)
        for (y in 0 until h) for (x in 0 until w) {
            img.setRGB(x, y, ((x * 2) shl 16) or ((y * 2) shl 8) or ((x xor y) and 0xFF))
        }
        return img
    }

    private fun jpeg(quality: Float, progressive: Boolean = false): ByteArray {
        val writer = ImageIO.getImageWritersByFormatName("jpeg").next()
        val out = ByteArrayOutputStream()
        MemoryCacheImageOutputStream(out).use { stream ->
            writer.output = stream
            val param = writer.defaultWriteParam.apply {
                compressionMode = ImageWriteParam.MODE_EXPLICIT
                compressionQuality = quality
                if (progressive) progressiveMode = ImageWriteParam.MODE_DEFAULT
            }
            writer.write(null, IIOImage(image(), null, null), param)
            stream.flush()
        }
        writer.dispose()
        return out.toByteArray()
    }

    /** SOI, the segments asked for, then EOI. Enough for the marker walker. */
    private fun fakeJpeg(segments: List<Pair<Int, ByteArray>>): ByteArray {
        val out = ByteArrayOutputStream()
        out.write(0xFF); out.write(0xD8)
        for ((marker, payload) in segments) {
            val len = payload.size + 2
            out.write(0xFF); out.write(marker)
            out.write((len shr 8) and 0xFF); out.write(len and 0xFF)
            out.write(payload)
        }
        out.write(0xFF); out.write(0xD9)
        return out.toByteArray()
    }

    /** A DQT payload for slot 0, taking the 64 values in natural order. */
    private fun dqt(natural: IntArray): ByteArray {
        val out = ByteArrayOutputStream()
        out.write(0x00)
        for (i in 0 until 64) out.write(natural[ZIGZAG[i]].coerceIn(1, 255))
        return out.toByteArray()
    }

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

    // ── Tests ────────────────────────────────────────────────────

    @Test
    fun `a table is read back out of zigzag order`() {
        // The values go in zigzagged and must come out in rows. Reading them in
        // file order would still produce 64 plausible numbers, which is exactly
        // why this needs its own test rather than being assumed from the ones
        // below passing.
        val read = JpegStructure.firstLumaTable(dqt(STANDARD_LUMA))
        assertNotNull(read)
        assertArrayEquals(STANDARD_LUMA, read!!)
    }

    @Test
    fun `the reference table at quality fifty is the reference table`() {
        // Quality 50 is the fixed point of the scaling formula, so anything
        // other than an exact match means the arithmetic is wrong.
        val fit = JpegStructure.closestStandard(STANDARD_LUMA)
        assertNotNull(fit)
        assertEquals(50, fit!!.first)
        assertEquals(0, fit.second)
    }

    @Test
    fun `ordinary software is recognised as ordinary software`() {
        for (requested in listOf(0.5f, 0.75f, 0.9f, 0.95f)) {
            val r = JpegStructure.analyse(jpeg(requested))
            assertTrue("should parse", r.present)
            assertEquals(
                "libjpeg output must match the published tables",
                JpegStructure.Tables.Standard, r.tables,
            )
            val quality = r.quality ?: error("no quality estimate")
            val asked = (requested * 100).toInt()
            println("asked $asked -> read $quality, distance ${r.tableDistance}")
            assertTrue(
                "estimate $quality should be near the $asked that was asked for",
                kotlin.math.abs(quality - asked) <= 3,
            )
        }
    }

    @Test
    fun `a tuned table is measured as far from the published one`() {
        // Roughly the shape of a phone camera's table: gentle on the low
        // frequencies the eye notices, harsh on the high ones it does not.
        val tuned = IntArray(64) { i ->
            val row = i / 8
            val col = i % 8
            (2 + (row + col) * (row + col)).coerceIn(1, 255)
        }
        val fit = JpegStructure.closestStandard(tuned)
        assertNotNull(fit)
        println("tuned table sits ${fit!!.second} away from the closest standard one")
        assertTrue("must not be mistaken for a standard table", fit.second > 200)

        val r = JpegStructure.analyse(fakeJpeg(listOf(0xDB to dqt(tuned))))
        assertEquals(JpegStructure.Tables.Custom, r.tables)
    }

    @Test
    fun `progressive layout is spotted, and baseline is not mistaken for it`() {
        assertFalse(JpegStructure.analyse(jpeg(0.9f)).progressive)
        assertTrue(JpegStructure.analyse(jpeg(0.9f, progressive = true)).progressive)
    }

    @Test
    fun `the frame header gives the colour detail that was thrown away`() {
        val r = JpegStructure.analyse(jpeg(0.9f))
        assertEquals(3, r.components)
        assertNotNull("subsampling should be readable", r.subsampling)
        println("subsampling: ${r.subsampling}, segments: ${r.segments}")
        assertTrue(r.subsampling!!.startsWith("4:"))
    }

    @Test
    fun `the private camera block is found by walking to it`() {
        val length = 4096
        val app1 = exifWithMakerNote(length)
        assertEquals(length, JpegStructure.makerNoteLength(app1))

        val r = JpegStructure.analyse(fakeJpeg(listOf(0xE1 to app1)))
        assertTrue(r.exifSegment)
        assertTrue(r.makerNote)
        assertEquals(length, r.makerNoteBytes)
    }

    @Test
    fun `EXIF without a private block does not invent one`() {
        // The walk has to end in "absent" rather than in whatever the bytes
        // after the directory happen to say.
        val app1 = exifWithMakerNote(null)
        assertNull(JpegStructure.makerNoteLength(app1))
        assertFalse(JpegStructure.analyse(fakeJpeg(listOf(0xE1 to app1))).makerNote)
    }

    @Test
    fun `a truncated or lying EXIF block is refused rather than followed`() {
        // Every offset in there comes from the file. A crafted one must not
        // walk this off the end of the array.
        val good = exifWithMakerNote(2048)
        for (cut in listOf(8, 14, 20, 30, 40)) {
            assertNull(JpegStructure.makerNoteLength(good.copyOfRange(0, cut)))
        }
        val lying = good.copyOf().also {
            // Point IFD0 a long way past the end of the segment.
            it[10] = 0x00; it[11] = 0x40; it[12] = 0x00; it[13] = 0x00
        }
        assertNull(JpegStructure.makerNoteLength(lying))
    }

    @Test
    fun `a PNG is not analysed as a JPEG`() {
        val png = ByteArrayOutputStream().also { ImageIO.write(image(), "png", it) }.toByteArray()
        val r = JpegStructure.analyse(png)
        assertFalse(r.present)
        assertEquals(JpegStructure.Tables.None, r.tables)
    }

    /**
     * "Exif  ", a TIFF header, IFD0 pointing at the Exif directory,
     * and that directory holding a maker note of the requested size.
     */
    private fun exifWithMakerNote(length: Int?): ByteArray {
        val out = ByteArrayOutputStream()
        out.write("Exif".toByteArray(Charsets.ISO_8859_1)); out.write(0); out.write(0)

        fun u16(v: Int) { out.write(v and 0xFF); out.write((v shr 8) and 0xFF) }
        fun u32(v: Int) {
            out.write(v and 0xFF); out.write((v shr 8) and 0xFF)
            out.write((v shr 16) and 0xFF); out.write((v shr 24) and 0xFF)
        }

        out.write("II".toByteArray(Charsets.ISO_8859_1))
        u16(42)
        u32(8)                       // IFD0 starts right after the header

        u16(1)                       // one entry
        u16(0x8769); u16(4); u32(1); u32(26)   // Exif directory lives at 26
        u32(0)                       // no IFD1

        if (length == null) {
            u16(1)
            u16(0x0201); u16(4); u32(1); u32(64)   // something that is not a maker note
        } else {
            u16(1)
            u16(0x927C); u16(7); u32(length); u32(64)
        }
        u32(0)
        return out.toByteArray()
    }
}
