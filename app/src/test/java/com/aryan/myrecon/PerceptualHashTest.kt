package com.aryan.myrecon

import com.aryan.myrecon.data.PerceptualHash
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.abs
import kotlin.random.Random

/**
 * The hashing maths, checked against its own defining properties.
 *
 * The Python original was validated against scipy's DCT to 2.89e-14; there is
 * no scipy here, so the orthonormality and energy-preservation identities are
 * asserted directly instead. A wrong DCT still produces plausible-looking
 * digests, so "it ran" proves nothing.
 */
class PerceptualHashTest {

    @Test
    fun `dct of a constant grid puts all energy in the DC term`() {
        val n = 32
        val constant = Array(n) { DoubleArray(n) { 7.0 } }
        val d = PerceptualHash.dct2(constant)

        assertTrue("DC term should be large, was ${d[0][0]}", abs(d[0][0]) > 1.0)
        for (r in 0 until n) for (c in 0 until n) {
            if (r == 0 && c == 0) continue
            assertEquals("coefficient [$r][$c] should vanish", 0.0, d[r][c], 1e-9)
        }
    }

    @Test
    fun `dct preserves energy`() {
        val rng = Random(42)
        val n = 32
        val a = Array(n) { DoubleArray(n) { rng.nextDouble() } }
        val d = PerceptualHash.dct2(a)

        val before = a.sumOf { row -> row.sumOf { it * it } }
        val after = d.sumOf { row -> row.sumOf { it * it } }
        assertEquals("orthonormal transform must preserve energy", before, after, 1e-6)
    }

    @Test
    fun `digests are 64 bits wide`() {
        val rng = Random(1)
        assertEquals(16, PerceptualHash.average(IntArray(64) { rng.nextInt(256) }).length)
        assertEquals(16, PerceptualHash.difference(IntArray(72) { rng.nextInt(256) }).length)
        assertEquals(16, PerceptualHash.perceptual(IntArray(1024) { rng.nextInt(256) }).length)
    }

    @Test
    fun `same input yields the same digest`() {
        val rng = Random(7)
        val luma = IntArray(1024) { rng.nextInt(256) }
        assertEquals(PerceptualHash.perceptual(luma), PerceptualHash.perceptual(luma))
        assertEquals(PerceptualHash.average(luma.copyOf(64)), PerceptualHash.average(luma.copyOf(64)))
    }

    @Test
    fun `a small brightness shift barely moves the digest`() {
        val rng = Random(11)
        val base = IntArray(1024) { rng.nextInt(200) }
        // Uniform brightening: perceptually the same picture.
        val brighter = IntArray(1024) { (base[it] + 20).coerceAtMost(255) }

        val d = PerceptualHash.hamming(
            PerceptualHash.perceptual(base),
            PerceptualHash.perceptual(brighter),
        )
        assertNotNull(d)
        assertTrue("brightness shift moved pHash by $d bits, expected <= 10", d!! <= 10)
    }

    @Test
    fun `unrelated images are far apart`() {
        val a = IntArray(1024) { Random(1).nextInt(256) }
        val b = IntArray(1024) { Random(999).nextInt(256) }
        val d = PerceptualHash.hamming(
            PerceptualHash.perceptual(a),
            PerceptualHash.perceptual(b),
        )
        assertNotNull(d)
        assertTrue("unrelated images only $d bits apart", d!! > 10)
    }

    @Test
    fun `hamming rejects incomparable input rather than guessing`() {
        assertNull(PerceptualHash.hamming("abcd", "abcdef"))
        assertNull(PerceptualHash.hamming("", "abcd"))
        assertNull(PerceptualHash.hamming(null, "abcd"))
        assertNull("non-hex must not silently score", PerceptualHash.hamming("zzzz", "abcd"))
        assertEquals(0, PerceptualHash.hamming("abcd", "abcd"))
    }

    @Test
    fun `similarity maps distance onto a sane scale`() {
        assertEquals(100.0, PerceptualHash.similarity(0)!!, 1e-9)
        assertEquals(0.0, PerceptualHash.similarity(64)!!, 1e-9)
        assertEquals(50.0, PerceptualHash.similarity(32)!!, 1e-9)
        assertNull(PerceptualHash.similarity(null))
        // Never negative, even past the bit width.
        assertEquals(0.0, PerceptualHash.similarity(100)!!, 1e-9)
    }

    @Test
    fun `wrong grid size is rejected, not silently misread`() {
        // Passing a square grid to dHash would read the rows misaligned and
        // produce a confident, wrong digest.
        try {
            PerceptualHash.difference(IntArray(64) { 0 })
            fail("dHash should reject a 8x8 grid; it needs 9x8")
        } catch (e: IllegalArgumentException) {
            assertTrue(e.message!!.contains("9x8"))
        }
        try {
            PerceptualHash.average(IntArray(63) { 0 })
            fail("aHash should reject a short grid")
        } catch (_: IllegalArgumentException) {
        }
    }
}
