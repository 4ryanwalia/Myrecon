package com.aryan.myrecon.data

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sqrt

/**
 * Perceptual hashing — pure maths, no Android types.
 *
 * Deliberately free of Bitmap so it can be unit tested on the JVM. Callers hand
 * in a greyscale luma grid; producing that grid from an image is the caller's
 * problem.
 *
 * Three algorithms because they fail differently — aHash on flat images, dHash
 * on heavy crops, pHash on nothing cheaply. Agreement between them is what
 * raises confidence that two files are the same picture.
 */
object PerceptualHash {

    const val BITS = 64

    /**
     * aHash — every pixel brighter than the mean becomes a 1.
     *
     * @param luma row-major greyscale, [size] x [size].
     */
    fun average(luma: IntArray, size: Int = 8): String {
        require(luma.size == size * size) { "expected ${size * size} samples, got ${luma.size}" }
        val mean = luma.average()
        return pack(BooleanArray(luma.size) { luma[it] > mean })
    }

    /**
     * dHash — encodes horizontal gradient direction.
     *
     * Takes a grid one column WIDER than tall, so each row yields [size]
     * comparisons. Most robust of the three to brightness and scale shifts,
     * which makes it the best single choice for "same photo, different upload".
     */
    fun difference(luma: IntArray, size: Int = 8): String {
        require(luma.size == (size + 1) * size) {
            "dHash expects ${(size + 1) * size} samples (${size + 1}x$size), got ${luma.size}"
        }
        val bits = BooleanArray(size * size)
        var b = 0
        for (row in 0 until size) {
            for (col in 0 until size) {
                val i = row * (size + 1) + col
                bits[b++] = luma[i + 1] > luma[i]
            }
        }
        return pack(bits)
    }

    /**
     * pHash — DCT-II on a 32x32 grid, keeping the top-left 8x8 block of low
     * frequencies. Slowest and most resistant to crops, overlays and heavy
     * re-encoding.
     */
    fun perceptual(luma: IntArray, size: Int = 32): String {
        require(luma.size == size * size) { "expected ${size * size} samples, got ${luma.size}" }
        val grid = Array(size) { r -> DoubleArray(size) { c -> luma[r * size + c].toDouble() } }
        val dct = dct2(grid)

        val block = DoubleArray(64)
        for (r in 0 until 8) for (c in 0 until 8) block[r * 8 + c] = dct[r][c]

        // The DC term carries overall brightness and would dominate the median,
        // so it is excluded from the threshold but kept in the digest grid.
        val median = block.drop(1).sorted().let {
            if (it.size % 2 == 0) (it[it.size / 2 - 1] + it[it.size / 2]) / 2 else it[it.size / 2]
        }
        return pack(BooleanArray(64) { block[it] > median })
    }

    /**
     * 2-D DCT-II by matrix multiplication.
     *
     * A library FFT would be the obvious tool, but pulling one in for a single
     * 32x32 transform is not worth the dependency. The basis is built once per
     * call and the multiply is trivial at this size.
     */
    fun dct2(a: Array<DoubleArray>): Array<DoubleArray> {
        val n = a.size
        val basis = Array(n) { i ->
            DoubleArray(n) { j ->
                val v = cos(PI * (2 * j + 1) * i / (2.0 * n)) * sqrt(2.0 / n)
                if (i == 0) v / sqrt(2.0) else v
            }
        }
        // basis * a * basis^T
        val tmp = Array(n) { i ->
            DoubleArray(n) { j ->
                var s = 0.0
                for (k in 0 until n) s += basis[i][k] * a[k][j]
                s
            }
        }
        return Array(n) { i ->
            DoubleArray(n) { j ->
                var s = 0.0
                for (k in 0 until n) s += tmp[i][k] * basis[j][k]
                s
            }
        }
    }

    /** Pack a bit array into a lowercase hex digest, most significant first. */
    private fun pack(bits: BooleanArray): String {
        val sb = StringBuilder(bits.size / 4)
        var i = 0
        while (i < bits.size) {
            var nibble = 0
            for (j in 0 until 4) {
                nibble = nibble shl 1
                if (i + j < bits.size && bits[i + j]) nibble = nibble or 1
            }
            sb.append(nibble.toString(16))
            i += 4
        }
        return sb.toString()
    }

    /**
     * Differing-bit count, or null when the digests are not comparable.
     * Callers must treat null as "unknown", never as "identical".
     */
    fun hamming(a: String?, b: String?): Int? {
        if (a.isNullOrBlank() || b.isNullOrBlank() || a.length != b.length) return null
        var d = 0
        for (i in a.indices) {
            val x = a[i].digitToIntOrNull(16) ?: return null
            val y = b[i].digitToIntOrNull(16) ?: return null
            d += Integer.bitCount(x xor y)
        }
        return d
    }

    /**
     * Map a Hamming distance to a 0-100 similarity.
     *
     * Linear in bits, which is honest about what this is: a distance measure,
     * not a probability. A distance of 10 or less is a likely match.
     */
    fun similarity(distance: Int?, bits: Int = BITS): Double? =
        distance?.let { ((1.0 - it.toDouble() / bits) * 100).coerceAtLeast(0.0) }
}
