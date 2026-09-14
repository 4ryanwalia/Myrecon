package com.aryan.myrecon

import com.aryan.myrecon.data.BlockGrid
import org.junit.Assert.*
import org.junit.Test
import java.awt.image.BufferedImage
import java.io.ByteArrayOutputStream
import javax.imageio.IIOImage
import javax.imageio.ImageIO
import javax.imageio.ImageWriteParam
import javax.imageio.stream.MemoryCacheImageOutputStream
import kotlin.math.sin
import kotlin.random.Random

/**
 * The eight-pixel trace, measured against real compression.
 *
 * The obvious way to test this is to paint a grid onto a synthetic image and
 * check it comes back. The first version did exactly that and it was nearly
 * useless: a hand-painted grid is whatever strength you decide to paint it, so
 * the thresholds end up tuned to the fixture rather than to anything a camera
 * or an editor produces.
 *
 * So the pictures here are put through the actual JPEG encoder, at the actual
 * quality settings software uses, and the numbers below are what came back:
 *
 *     never compressed                     1.01
 *     pure noise, never compressed         1.01
 *     JPEG quality 20 / 30 / 50 / 70       2.05 / 1.69 / 1.55 / 1.34
 *     JPEG quality 85 / 95                 1.02 / 1.00
 *     compressed, cropped by 3, re-saved   1.39–1.62 at offset 5,5
 *     compressed, then saved as a PNG      1.67
 *
 * Two things fall out of that and both are in the thresholds. There is a very
 * wide gap between an untouched picture and a compressed one, so the test can
 * afford to be strict. And above quality 85 there is no measurable grid at
 * all — which is a real limit of the method, pinned below so it is a known
 * blind spot rather than a surprise.
 */
class BlockGridTest {

    // ── Fixtures ─────────────────────────────────────────────────

    /**
     * Something with the structure of a photograph.
     *
     * Not white noise: noise has no low frequencies for the encoder to keep
     * and no high ones it can afford to throw away, so compressing it produces
     * mush rather than blocks, and it would be the wrong thing to measure.
     */
    private fun photo(w: Int = 384, h: Int = 384, seed: Int = 3): BufferedImage {
        val rng = Random(seed)
        val img = BufferedImage(w, h, BufferedImage.TYPE_INT_RGB)
        for (y in 0 until h) for (x in 0 until w) {
            val wave = sin(x / 11.0) * 40 + sin(y / 7.0) * 35 + sin((x + y) / 23.0) * 45
            val v = (128 + wave + rng.nextInt(30) - 15).toInt().coerceIn(0, 255)
            img.setRGB(
                x, y,
                ((v * 1.05).toInt().coerceIn(0, 255) shl 16) or
                    (v shl 8) or (v * 0.9).toInt().coerceIn(0, 255),
            )
        }
        return img
    }

    private fun compressed(img: BufferedImage, quality: Float): BufferedImage =
        ImageIO.read(encode(img, quality).inputStream())

    private fun encode(img: BufferedImage, quality: Float): ByteArray {
        val writer = ImageIO.getImageWritersByFormatName("jpeg").next()
        val out = ByteArrayOutputStream()
        MemoryCacheImageOutputStream(out).use { s ->
            writer.output = s
            writer.write(
                null, IIOImage(img, null, null),
                writer.defaultWriteParam.apply {
                    compressionMode = ImageWriteParam.MODE_EXPLICIT
                    compressionQuality = quality
                },
            )
            s.flush()
        }
        writer.dispose()
        return out.toByteArray()
    }

    private fun measure(img: BufferedImage): BlockGrid.Result? {
        val w = img.width
        val h = img.height
        val luma = IntArray(w * h)
        for (y in 0 until h) for (x in 0 until w) {
            val p = img.getRGB(x, y)
            val r = (p shr 16) and 0xFF
            val g = (p shr 8) and 0xFF
            val b = p and 0xFF
            luma[y * w + x] = (r * 299 + g * 587 + b * 114) / 1000
        }
        return BlockGrid.analyse(luma, w, h)
    }

    // ── What must stay quiet ─────────────────────────────────────

    @Test
    fun `a picture that was never compressed has no grid`() {
        val r = measure(photo()) ?: error("a detailed picture should be measurable")
        println("never compressed: %.3f".format(r.strength))
        assertTrue("got ${r.strength}", r.strength < BlockGrid.PRESENT)
    }

    @Test
    fun `pure noise has no grid either`() {
        // Noise maximises the denominator and can produce a spurious phase.
        // What matters is that the strength stays at the floor, because the
        // phase is only ever read once the strength has cleared a threshold.
        val rng = Random(11)
        val img = BufferedImage(384, 384, BufferedImage.TYPE_INT_RGB)
        for (y in 0 until 384) for (x in 0 until 384) {
            val v = rng.nextInt(256)
            img.setRGB(x, y, (v shl 16) or (v shl 8) or v)
        }
        val r = measure(img) ?: error("noise is measurable")
        println("pure noise: %.3f".format(r.strength))
        assertTrue("got ${r.strength}", r.strength < BlockGrid.PRESENT)
    }

    @Test
    fun `a picture with nothing in it answers nothing rather than anything`() {
        // A flat or near-flat image divides by almost zero, and a ratio built
        // out of rounding dust is how this would accuse blank scans and
        // solid-colour graphics of having been through an editor.
        val w = 256
        assertNull("solid colour", BlockGrid.analyse(IntArray(w * w) { 128 }, w, w))

        val gradient = BufferedImage(384, 384, BufferedImage.TYPE_INT_RGB)
        for (y in 0 until 384) for (x in 0 until 384) {
            val v = x * 255 / 384
            gradient.setRGB(x, y, (v shl 16) or (v shl 8) or v)
        }
        val r = measure(gradient)
        assertTrue("a smooth gradient must stay quiet", r == null || r.strength < BlockGrid.PRESENT)
    }

    @Test
    fun `stripes in one direction only are not a grid`() {
        // A picket fence, a window blind, a table of text: strong periodic
        // structure across and nothing down. Compression does not pick a
        // direction, so neither does this.
        val w = 256
        val rng = Random(5)
        val base = IntArray(w * w) { 60 + rng.nextInt(140) }
        val striped = IntArray(w * w) { i ->
            (base[i] + if (i % w % 8 == 0) 70 else 0).coerceIn(0, 255)
        }
        val r = BlockGrid.analyse(striped, w, w)
        assertTrue(
            "one strong axis must not carry a verdict",
            r == null || r.strength < BlockGrid.PRESENT,
        )
    }

    @Test
    fun `a picture too small to hold enough blocks is declined`() {
        val rng = Random(2)
        assertNull(BlockGrid.analyse(IntArray(64 * 64) { rng.nextInt(256) }, 64, 64))
        assertNull(BlockGrid.analyse(IntArray(200 * 64) { rng.nextInt(256) }, 200, 64))
    }

    // ── What must be caught ──────────────────────────────────────

    @Test
    fun `real compression leaves a grid lined up with the corner`() {
        for (q in listOf(0.2f, 0.3f, 0.5f, 0.7f)) {
            val r = measure(compressed(photo(), q)) ?: error("q=$q should be measurable")
            println("quality ${(q * 100).toInt()}: %.3f at ${r.phaseX},${r.phaseY}".format(r.strength))
            assertTrue("q=$q strength ${r.strength}", r.strength >= BlockGrid.PRESENT)
            assertTrue("q=$q should be lined up, got ${r.phaseX},${r.phaseY}", r.aligned)
        }
    }

    @Test
    fun `cropping and re-saving leaves the old grid off-centre`() {
        // This is the entire crop claim. Three pixels off the top and left
        // moves every boundary to an offset of five; if that comes back as
        // zero, a trimmed-and-re-saved photo reads as an untouched one.
        for (first in listOf(0.25f, 0.4f, 0.6f)) {
            val once = compressed(photo(), first)
            val cropped = once.getSubimage(3, 3, once.width - 8, once.height - 8)
            val twice = compressed(cropped, 0.95f)

            val r = measure(twice) ?: error("should be measurable")
            println("q=${(first * 100).toInt()} cropped: %.3f at ${r.phaseX},${r.phaseY}".format(r.strength))
            assertTrue(r.strength >= BlockGrid.PRESENT)
            assertEquals("across", 5, r.phaseX)
            assertEquals("down", 5, r.phaseY)
            assertFalse(r.aligned)
        }
    }

    @Test
    fun `a compressed picture saved as a PNG still carries the grid`() {
        // The PNG has no lossy compression of its own, so a grid inside one
        // can only have come from an earlier life as something else.
        val png = ByteArrayOutputStream()
            .also { ImageIO.write(compressed(photo(), 0.35f), "png", it) }
            .toByteArray()
        val r = measure(ImageIO.read(png.inputStream())) ?: error("should be measurable")
        println("jpeg saved as png: %.3f".format(r.strength))
        assertTrue("got ${r.strength}", r.strength >= BlockGrid.CONVERTED)
    }

    // ── The known blind spot ─────────────────────────────────────

    @Test
    fun `very high quality compression leaves nothing to find`() {
        // Above about quality 85 the encoder keeps enough that no measurable
        // step survives. That is a real limit of the method, and it is pinned
        // here on purpose: the failure it produces is silence, which is safe,
        // and anyone who later loosens the threshold to "catch more" will find
        // this test telling them what they are about to start inventing.
        for (q in listOf(0.9f, 0.95f)) {
            val r = measure(compressed(photo(), q))
            val strength = r?.strength ?: 1.0
            println("quality ${(q * 100).toInt()}: %.3f".format(strength))
            assertTrue(
                "quality ${(q * 100).toInt()} should be below the threshold, got $strength",
                strength < BlockGrid.PRESENT,
            )
        }
    }
}
