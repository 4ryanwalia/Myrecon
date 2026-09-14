package com.aryan.myrecon.data

import kotlin.math.abs

/**
 * The eight-pixel grid JPEG compression leaves behind in the pixels.
 *
 * JPEG works on 8×8 blocks and quantises each one on its own, so neighbouring
 * blocks end up very slightly out of step. The eye does not see it, but the
 * average brightness step across a block boundary is measurably larger than
 * the step one pixel to either side. That residue is not metadata: it is the
 * picture itself, so it survives every strip, rename and re-container that
 * wipes everything [ImageProvenance] reads.
 *
 * Two questions come out of one measurement, and they are different questions:
 *
 *  • **A grid in a PNG.** PNG compression is lossless and creates no grid of
 *    its own, so finding one means the picture was a JPEG earlier in its life
 *    and was re-saved. A file claiming to be an untouched original is not one.
 *
 *  • **A grid in a JPEG that is off-centre.** A JPEG written from scratch puts
 *    its first block at the top-left corner, so the boundaries land on
 *    multiples of eight. If the strongest boundaries land somewhere else, the
 *    picture carries an older grid from a *previous* compression, offset
 *    because the frame was cropped in between — it was opened, trimmed and
 *    saved again.
 *
 * The measurement is a ratio rather than an absolute, which is what keeps it
 * honest across wildly different pictures: a busy photo has large steps
 * everywhere and a smooth one has small steps everywhere, but only a
 * compressed picture has systematically larger steps every eighth column.
 *
 * Pure Kotlin over a luma grid so the arithmetic can be tested against
 * synthetic images whose answer is known in advance.
 */
object BlockGrid {

    /**
     * @param phaseX column offset of the strongest vertical boundaries, 0–7.
     * @param phaseY row offset of the strongest horizontal boundaries, 0–7.
     * @param strength how much stronger those boundaries are than their
     *   neighbours. 1.0 means no grid at all.
     */
    data class Result(val phaseX: Int, val phaseY: Int, val strength: Double) {
        /** Blocks start at the top-left corner, as a freshly written JPEG does. */
        val aligned: Boolean get() = phaseX == 0 && phaseY == 0
    }

    /**
     * Below this a grid is indistinguishable from ordinary picture detail.
     *
     * Measured rather than guessed. Put through a real encoder, an untouched
     * picture comes back at 1.01 and a compressed one at 1.34 (quality 70)
     * rising to 2.05 (quality 20), so there is a wide empty band to sit in and
     * this sits near the bottom of it. `BlockGridTest` holds those numbers.
     *
     * The method has one honest limit: above about quality 85 the encoder
     * keeps enough detail that no step survives at all, and such a file
     * measures 1.00 like an untouched one. The failure is silence rather than
     * a wrong answer, which is the right way round.
     */
    const val PRESENT = 1.22

    /**
     * A grid in a format that cannot produce one. Held higher than [PRESENT]
     * because the claim is stronger and the cost of being wrong is telling
     * someone their untouched screenshot has been through an editor. A
     * compressed picture re-saved as a PNG measures 1.67.
     */
    const val CONVERTED = 1.35

    /**
     * Measure the grid, or return null when the picture cannot answer.
     *
     * Null is returned rather than a weak result whenever the input is too
     * small to hold enough blocks to average over, or so flat that the
     * denominator would be noise — a gradient, a solid colour, a mostly-white
     * document scan. Those produce spectacular ratios out of rounding dust,
     * and a threshold cannot save a measurement whose basis is empty.
     */
    fun analyse(luma: IntArray, width: Int, height: Int): Result? {
        if (width < MIN_SIDE || height < MIN_SIDE) return null
        if (luma.size < width * height) return null

        val columns = DoubleArray(width)
        val columnCounts = IntArray(width)
        val rows = DoubleArray(height)
        val rowCounts = IntArray(height)

        for (y in 0 until height) {
            val base = y * width
            for (x in 1 until width) {
                val d = abs(luma[base + x] - luma[base + x - 1]).toDouble()
                columns[x] += d
                columnCounts[x]++
            }
        }
        for (y in 1 until height) {
            val base = y * width
            val above = base - width
            for (x in 0 until width) {
                val d = abs(luma[base + x] - luma[above + x]).toDouble()
                rows[y] += d
                rowCounts[y]++
            }
        }

        val x = bestPhase(columns, columnCounts) ?: return null
        val y = bestPhase(rows, rowCounts) ?: return null

        // Both axes must agree that there is a grid. A single strong axis is
        // what a picket fence, a window blind or a table of text produces, and
        // compression does not pick a direction.
        return Result(x.first, y.first, minOf(x.second, y.second))
    }

    /**
     * Which of the eight offsets carries the strongest boundaries, and by how
     * much it beats the lines that are not on it.
     */
    private fun bestPhase(sums: DoubleArray, counts: IntArray): Pair<Int, Double>? {
        val means = DoubleArray(sums.size) { if (counts[it] > 0) sums[it] / counts[it] else -1.0 }

        var bestPhase = -1
        var bestRatio = 0.0
        for (phase in 0 until 8) {
            var onSum = 0.0
            var onCount = 0
            var offSum = 0.0
            var offCount = 0
            // The first line of the picture has no neighbour on one side and
            // the last block is usually partial, so both ends are skipped.
            for (i in 8 until means.size - 8) {
                if (means[i] < 0) continue
                if (i % 8 == phase) {
                    onSum += means[i]; onCount++
                } else {
                    offSum += means[i]; offCount++
                }
            }
            if (onCount < 4 || offCount < 4) return null
            val off = offSum / offCount
            // A picture with almost no detail gives a denominator made of
            // rounding, which turns any difference at all into a huge ratio.
            if (off < MIN_DETAIL) return null
            val ratio = (onSum / onCount) / off
            if (ratio > bestRatio) {
                bestRatio = ratio
                bestPhase = phase
            }
        }
        return if (bestPhase < 0) null else bestPhase to bestRatio
    }

    /** Smaller than this and there are too few blocks for the average to mean anything. */
    private const val MIN_SIDE = 128

    /** Mean step between neighbouring pixels, on a 0–255 scale. */
    private const val MIN_DETAIL = 0.75
}
