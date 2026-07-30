package com.aryan.myrecon.ui.components

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.ui.animatedInt
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.MonoStyle
import kotlin.math.cos
import kotlin.math.sin

/**
 * The scanning hero.
 *
 * A 117-platform sweep takes about six seconds, which is exactly the awkward
 * length where a spinner feels broken and a progress bar feels slow. A radar
 * makes the wait legible: the arm sweeps, blips land where platforms answered,
 * and the count climbs. It reads as work happening rather than time passing.
 *
 * Everything is drawn on a Canvas rather than composed from layout nodes —
 * this repaints on every frame, and 117 animating composables would drop frames
 * on a mid-range phone.
 *
 * @param progress 0..1 through the sweep.
 * @param found how many accounts have been confirmed so far.
 * @param checked platforms probed so far.
 * @param total size of the catalogue.
 * @param currentTarget the platform being probed right now.
 */
@Composable
fun RadarScan(
    progress: Float,
    found: Int,
    checked: Int,
    total: Int,
    currentTarget: String,
    modifier: Modifier = Modifier,
) {
    val t = LocalReconTokens.current
    val accent = MaterialTheme.colorScheme.primary
    val reduceMotion = LocalConfiguration.current.fontScale > 0f && !animationsEnabled()

    val sweep = rememberInfiniteTransition(label = "radar")
    val angle by if (reduceMotion) {
        remember { mutableFloatStateOf(0f) }
    } else {
        sweep.animateFloat(
            initialValue = 0f,
            targetValue = 360f,
            animationSpec = infiniteRepeatable(tween(2200, easing = LinearEasing)),
            label = "sweepAngle",
        )
    }

    // Blips accumulate as hits arrive, at stable pseudo-random bearings so the
    // display does not reshuffle on every recomposition.
    val blips = remember { mutableStateListOf<Pair<Float, Float>>() }
    LaunchedEffect(found) {
        while (blips.size < found) {
            val i = blips.size
            // Deterministic scatter — golden-angle placement avoids clumping.
            val bearing = (i * 137.508f) % 360f
            val radius = 0.35f + ((i * 37) % 55) / 100f
            blips += bearing to radius
        }
    }

    Column(modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        Box(contentAlignment = Alignment.Center) {
            Canvas(Modifier.size(210.dp)) {
                val c = Offset(size.width / 2, size.height / 2)
                val r = size.minDimension / 2

                // Range rings
                listOf(0.33f, 0.66f, 1f).forEach { f ->
                    drawCircle(
                        color = t.border,
                        radius = r * f,
                        center = c,
                        style = Stroke(width = 1f),
                    )
                }
                // Cross hairs
                drawLine(t.border, Offset(c.x - r, c.y), Offset(c.x + r, c.y), 1f)
                drawLine(t.border, Offset(c.x, c.y - r), Offset(c.x, c.y + r), 1f)

                // Sweep arm with a trailing wedge
                rotate(angle, pivot = c) {
                    drawArc(
                        brush = Brush.sweepGradient(
                            0f to Color.Transparent,
                            0.12f to accent.copy(alpha = 0.28f),
                            0.16f to accent.copy(alpha = 0.55f),
                            0.17f to Color.Transparent,
                            1f to Color.Transparent,
                            center = c,
                        ),
                        startAngle = -90f,
                        sweepAngle = 360f,
                        useCenter = true,
                        topLeft = Offset(c.x - r, c.y - r),
                        size = Size(r * 2, r * 2),
                    )
                    drawLine(accent, c, Offset(c.x, c.y - r), 2f)
                }

                // Confirmed hits
                blips.forEach { (bearing, radiusFrac) ->
                    val rad = Math.toRadians(bearing.toDouble() - 90)
                    val p = Offset(
                        c.x + (r * radiusFrac * cos(rad)).toFloat(),
                        c.y + (r * radiusFrac * sin(rad)).toFloat(),
                    )
                    drawCircle(t.ok.copy(alpha = 0.22f), radius = 7f, center = p)
                    drawCircle(t.ok, radius = 3f, center = p)
                }

                // Progress ring on the outer edge
                drawArc(
                    color = accent,
                    startAngle = -90f,
                    sweepAngle = 360f * progress.coerceIn(0f, 1f),
                    useCenter = false,
                    topLeft = Offset(c.x - r, c.y - r),
                    size = Size(r * 2, r * 2),
                    style = Stroke(width = 3f),
                )
            }

            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                // Climbs rather than jumps: a counter that ticks upward reads as
                // discovery, where a replaced number reads as a data refresh.
                Text(
                    "${animatedInt(found, durationMillis = 260)}",
                    style = MaterialTheme.typography.headlineSmall.copy(fontSize = androidx.compose.ui.unit.TextUnit(38f, androidx.compose.ui.unit.TextUnitType.Sp)),
                    color = if (found > 0) t.ok else t.textMute,
                )
                Text(
                    if (found == 1) "ACCOUNT" else "ACCOUNTS",
                    style = MaterialTheme.typography.labelSmall,
                    color = t.textMute,
                )
            }
        }

        Spacer(Modifier.height(14.dp))
        Text(
            currentTarget.ifBlank { "Scanning…" },
            style = MonoStyle,
            color = MaterialTheme.colorScheme.primary,
            maxLines = 1,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(4.dp))
        Text(
            "$checked of $total platforms",
            style = MaterialTheme.typography.bodySmall,
            color = t.textMute,
        )
    }
}

/** Respects the system "remove animations" accessibility setting. */
@Composable
private fun animationsEnabled(): Boolean {
    val context = androidx.compose.ui.platform.LocalContext.current
    return remember {
        android.provider.Settings.Global.getFloat(
            context.contentResolver,
            android.provider.Settings.Global.ANIMATOR_DURATION_SCALE,
            1f,
        ) != 0f
    }
}
