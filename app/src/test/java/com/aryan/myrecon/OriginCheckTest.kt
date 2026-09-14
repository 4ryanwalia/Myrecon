package com.aryan.myrecon

import com.aryan.myrecon.data.BlockGrid
import com.aryan.myrecon.data.ImageForensics
import com.aryan.myrecon.data.ImageProvenance
import com.aryan.myrecon.data.JpegStructure
import com.aryan.myrecon.data.OriginCheck
import org.junit.Assert.*
import org.junit.Test

/**
 * The decision table, written as situations rather than as images.
 *
 * The dangerous failure for this feature is not missing an AI picture. It is
 * telling somebody their holiday photo was generated, or that their screenshot
 * has been doctored — a wrong accusation is worse than no answer, and it is the
 * kind of thing a scorer does quietly as clues accumulate.
 *
 * So roughly half of what is pinned here is the negative case: the ordinary
 * files people will actually put through this screen, and the requirement that
 * none of them come back accused. The positive cases exist to prove the thing
 * still works after the guards are in place.
 */
class OriginCheckTest {

    // ── Situations ───────────────────────────────────────────────

    /** Straight off a phone: private block, shot settings, its own compression. */
    private fun phonePhoto(
        name: String = "PXL_20260914_101500123.jpg",
        thumbnail: ImageForensics.Match = ImageForensics.Match.Consistent,
    ) = OriginCheck.Evidence(
        fileName = name,
        container = ImageProvenance.Container.Jpeg,
        width = 4080, height = 3072,
        exifPresent = true,
        cameraMake = "Google", cameraModel = "Pixel 8",
        hasGps = true,
        captureSettings = 4,
        capturedAt = "2026-09-14 10:15:00",
        modifiedAt = "2026-09-14 10:15:00",
        jpeg = jpeg(tables = JpegStructure.Tables.Custom, makerNoteBytes = 8192),
        thumbnail = thumbnail,
    )

    /** A screenshot: PNG, nothing inside it at all. */
    private fun screenshot(w: Int = 1080, h: Int = 2400) = OriginCheck.Evidence(
        fileName = "Screenshot_20260914-101500.png",
        container = ImageProvenance.Container.Png,
        width = w, height = h,
    )

    /** Arrived through WhatsApp: squashed by software, stripped bare. */
    private fun forwarded(w: Int = 1024, h: Int = 1024) = OriginCheck.Evidence(
        fileName = "IMG-20260914-WA0007.jpg",
        container = ImageProvenance.Container.Jpeg,
        width = w, height = h,
        jpeg = jpeg(tables = JpegStructure.Tables.Standard, quality = 95),
    )

    private fun jpeg(
        tables: JpegStructure.Tables = JpegStructure.Tables.None,
        quality: Int? = null,
        progressive: Boolean = false,
        makerNoteBytes: Int? = null,
        adobe: Boolean = false,
        photoshop: Boolean = false,
    ) = JpegStructure.Report(
        present = true,
        progressive = progressive,
        quality = quality,
        tables = tables,
        tableDistance = if (tables == JpegStructure.Tables.Custom) 900 else 0,
        subsampling = "4:2:0",
        components = 3,
        restartInterval = false,
        makerNoteBytes = makerNoteBytes,
        adobeSegment = adobe,
        photoshopBlock = photoshop,
        jfif = false,
        exifSegment = makerNoteBytes != null,
        segments = emptyList(),
    )

    // ── The files that must never be accused ─────────────────────

    @Test
    fun `an ordinary phone photo reads as a real photo and not as an edit`() {
        val v = OriginCheck.of(phonePhoto())
        println("${v.made} / ${v.touched} — ${v.headline}")
        assertEquals(OriginCheck.Made.LooksCamera, v.made)
        assertTrue("nothing should point at a generator", v.towardAi.isEmpty())
        assertEquals(OriginCheck.Touched.NoSign, v.touched)
    }

    @Test
    fun `a screenshot is not accused of being generated`() {
        // No camera, no date, no settings, and a PNG. Every one of those is
        // also true of a generated picture, which is exactly why the name has
        // to be allowed to explain them.
        val v = OriginCheck.of(screenshot())
        println("${v.made} — ruled out: ${v.explained.map { it.text }}")
        assertEquals(OriginCheck.Made.Unknown, v.made)
        assertTrue("the reason must be visible", v.explained.isNotEmpty())
    }

    @Test
    fun `a square screenshot is still not accused`() {
        // 1024x1024 is a generator size and a perfectly ordinary crop. On its
        // own it must never be enough.
        val v = OriginCheck.of(screenshot(1024, 1024))
        assertNotEquals(OriginCheck.Made.LooksAi, v.made)
    }

    @Test
    fun `a picture forwarded through WhatsApp is not accused`() {
        val v = OriginCheck.of(forwarded())
        println("${v.made} — ruled out: ${v.explained.map { it.text }}")
        assertNotEquals(OriginCheck.Made.LooksAi, v.made)
        assertTrue(v.explained.any { it.text.contains("messaging", ignoreCase = true) })
    }

    @Test
    fun `a bare download is left as unknown rather than guessed at`() {
        // No name worth anything, no metadata, an unremarkable size. This is
        // most of what anyone will ever check, and the honest answer is that
        // the file does not say.
        val v = OriginCheck.of(
            OriginCheck.Evidence(
                fileName = "image.jpg",
                container = ImageProvenance.Container.Jpeg,
                width = 1600, height = 900,
                jpeg = jpeg(tables = JpegStructure.Tables.Standard, quality = 80),
            )
        )
        assertEquals(OriginCheck.Made.Unknown, v.made)
        assertTrue(v.plain.contains("does not mean it is real"))
    }

    // ── The files that should be caught ──────────────────────────

    @Test
    fun `a label inside the file settles it on its own`() {
        val v = OriginCheck.of(
            phonePhoto().copy(
                declared = ImageProvenance.Origin.DeclaredAiGenerated,
                generator = "Midjourney",
            )
        )
        assertEquals(OriginCheck.Made.DeclaredAi, v.made)
        assertTrue("the tool should be named in the headline", v.headline.contains("Midjourney"))
    }

    @Test
    fun `a generator's own filename is caught`() {
        val v = OriginCheck.of(
            OriginCheck.Evidence(
                fileName = "Gemini_Generated_Image_4k1x9v.jpeg",
                container = ImageProvenance.Container.Jpeg,
                width = 1024, height = 1024,
                jpeg = jpeg(tables = JpegStructure.Tables.Standard, quality = 95),
            )
        )
        println("${v.made}: ${v.towardAi.map { it.text }}")
        assertEquals(OriginCheck.Made.LooksAi, v.made)
        assertTrue(v.towardAi.any { it.text.contains("Google Gemini") })
    }

    @Test
    fun `names that are ordinary words are not treated as tool names`() {
        // "dream", "flux", "designer" and "imagine" are all the names of real
        // generators and all the names of ordinary pictures. Matching them
        // loosely is how this would accuse half a camera roll.
        listOf(
            "dream holiday.png", "flux capacitor.jpg", "Designer.png",
            "imagine that.jpeg", "midsummer.jpg", "IMG_4821.JPG",
        ).forEach {
            assertNull("$it must not be read as a tool name", OriginCheck.aiFromName(it))
        }
        // And the real ones still are.
        assertEquals("ComfyUI", OriginCheck.aiFromName("ComfyUI_00042_.png"))
        assertEquals("Stable Diffusion", OriginCheck.aiFromName("00042-3517829461.png"))
        assertEquals("DALL·E", OriginCheck.aiFromName("DALL-E 2026-09-14 10.15.00.png"))
    }

    @Test
    fun `an exact generator shape with an empty file is enough`() {
        val v = OriginCheck.of(
            OriginCheck.Evidence(
                fileName = "download.png",
                container = ImageProvenance.Container.Png,
                width = 1216, height = 832,
            )
        )
        println("${v.made}: ${v.towardAi.map { it.text }}")
        assertEquals(OriginCheck.Made.LooksAi, v.made)
    }

    @Test
    fun `a generator shape is dropped as soon as a camera is named`() {
        // A photo cropped to 1216x832 in an editor that kept the EXIF must not
        // inherit the generator's verdict.
        val v = OriginCheck.of(phonePhoto().copy(width = 1216, height = 832))
        assertTrue(v.towardAi.isEmpty())
    }

    // ── Editing ──────────────────────────────────────────────────

    @Test
    fun `an edit log in the file is taken at its word`() {
        val v = OriginCheck.of(
            phonePhoto().copy(editHistory = listOf("Adobe Photoshop 26.0 (Windows)"))
        )
        assertEquals(OriginCheck.Touched.Declared, v.touched)
        assertTrue(v.edits.any { it.why.contains("Adobe Photoshop") })
    }

    @Test
    fun `a preview that no longer matches outranks a weaker later finding`() {
        // The strongest finding has to survive whatever order the checks run
        // in. Getting the comparison backwards downgrades a tampered photo to
        // "re-saved", which is the difference between a warning and a shrug.
        val v = OriginCheck.of(
            phonePhoto(thumbnail = ImageForensics.Match.Mismatch).copy(
                jpeg = jpeg(tables = JpegStructure.Tables.Custom, progressive = true),
                modifiedAt = "2026-09-20 18:00:00",
            )
        )
        assertEquals(OriginCheck.Touched.Likely, v.touched)
        assertTrue(v.edits.size >= 3)
    }

    @Test
    fun `a compression grid in a lossless file says it was something else before`() {
        val v = OriginCheck.of(
            screenshot().copy(grid = BlockGrid.Result(0, 0, 1.6))
        )
        assertEquals(OriginCheck.Touched.Likely, v.touched)
        assertTrue(v.edits.any { it.text.contains("different kind of file") })
    }

    @Test
    fun `a grid sitting off-centre in a JPEG says it was cropped`() {
        val v = OriginCheck.of(
            phonePhoto().copy(grid = BlockGrid.Result(3, 5, 1.4))
        )
        assertEquals(OriginCheck.Touched.Likely, v.touched)
        assertTrue(v.edits.any { it.text.contains("Cropped") })
    }

    @Test
    fun `a grid lined up with the corner is not held against a JPEG`() {
        // Every JPEG ever written has this. Reporting it would put "edited" on
        // literally every photograph.
        val v = OriginCheck.of(phonePhoto().copy(grid = BlockGrid.Result(0, 0, 1.9)))
        assertEquals(OriginCheck.Touched.NoSign, v.touched)
    }

    @Test
    fun `being re-saved is reported as re-saved and not as editing`() {
        val v = OriginCheck.of(
            OriginCheck.Evidence(
                fileName = "photo.jpg",
                container = ImageProvenance.Container.Jpeg,
                width = 1600, height = 1200,
                exifPresent = true,
                cameraMake = "Canon", cameraModel = "EOS R6",
                jpeg = jpeg(tables = JpegStructure.Tables.Standard, quality = 85),
            )
        )
        assertEquals(OriginCheck.Touched.ReSaved, v.touched)
    }

    // ── The contract the screen relies on ────────────────────────

    @Test
    fun `every clue carries a reason a person can read`() {
        val situations = listOf(
            phonePhoto(),
            screenshot(),
            forwarded(),
            phonePhoto(thumbnail = ImageForensics.Match.Mismatch),
            screenshot().copy(grid = BlockGrid.Result(0, 0, 1.6)),
            OriginCheck.Evidence(fileName = "ComfyUI_00042_.png", width = 1024, height = 1024),
        )
        situations.forEach { e ->
            val v = OriginCheck.of(e)
            assertTrue("headline", v.headline.length in 10..120)
            assertTrue("explanation", v.plain.length > 40)
            (v.towardAi + v.towardCamera + v.edits + v.explained).forEach { c ->
                assertTrue("clue text on ${e.fileName}", c.text.isNotBlank())
                assertTrue("clue reason on ${e.fileName}: ${c.text}", c.why.length > 20)
            }
        }
    }
}
