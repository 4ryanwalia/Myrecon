package com.aryan.myrecon.ui.components

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
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
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.TextUnitType
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.MonoStyle
import kotlin.math.roundToInt

/**
 * Exposure score, 0-100.
 *
 * This is the screen people screenshot, so it is the one place the app spends
 * real motion: the arc fills and the number counts up over three quarters of a
 * second. Fast enough not to annoy, slow enough to register as a reveal.
 *
 * The arc is a 270-degree dial rather than a full circle — a gap at the bottom
 * reads as a gauge with a floor and a ceiling, where a closed ring reads as a
 * loading spinner.
 */
@Composable
fun ExposureGauge(
    score: Int,
    label: String,
    message: String,
    modifier: Modifier = Modifier,
) {
    val t = LocalReconTokens.current
    val tint = when {
        score >= 61 -> t.danger
        score >= 31 -> t.warn
        else -> t.ok
    }

    var play by remember { mutableStateOf(false) }
    LaunchedEffect(score) { play = true }
    val animated by animateFloatAsState(
        targetValue = if (play) score.coerceIn(0, 100) / 100f else 0f,
        animationSpec = tween(durationMillis = 750),
        label = "gaugeFill",
    )

    Row(modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Box(contentAlignment = Alignment.Center) {
            Canvas(Modifier.size(116.dp)) {
                val stroke = 11.dp.toPx()
                val inset = stroke / 2
                val arcSize = Size(size.width - stroke, size.height - stroke)
                val topLeft = Offset(inset, inset)
                val start = 135f
                val total = 270f

                drawArc(
                    color = t.surface2,
                    startAngle = start,
                    sweepAngle = total,
                    useCenter = false,
                    topLeft = topLeft,
                    size = arcSize,
                    style = Stroke(width = stroke, cap = StrokeCap.Round),
                )
                drawArc(
                    brush = Brush.sweepGradient(listOf(tint.copy(alpha = 0.55f), tint)),
                    startAngle = start,
                    sweepAngle = total * animated,
                    useCenter = false,
                    topLeft = topLeft,
                    size = arcSize,
                    style = Stroke(width = stroke, cap = StrokeCap.Round),
                )
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    "${(animated * 100).roundToInt()}",
                    style = MaterialTheme.typography.headlineSmall.copy(
                        fontSize = TextUnit(32f, TextUnitType.Sp),
                    ),
                    color = tint,
                )
                Text("/ 100", style = MaterialTheme.typography.labelSmall, color = t.textMute)
            }
        }

        Spacer(Modifier.width(16.dp))

        Column(Modifier.weight(1f)) {
            Text(
                "DIGITAL EXPOSURE",
                style = MaterialTheme.typography.labelSmall,
                color = t.textMute,
            )
            Spacer(Modifier.height(2.dp))
            Text(label, style = MaterialTheme.typography.titleLarge, color = tint)
            Spacer(Modifier.height(6.dp))
            Text(
                message,
                style = MaterialTheme.typography.bodySmall,
                color = t.textDim,
            )
        }
    }
}

/** A single factor behind the score, shown beneath the gauge. */
@Composable
fun FactorRow(label: String, value: String) {
    val t = LocalReconTokens.current
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = t.textDim, modifier = Modifier.weight(1f))
        Text(value, style = MonoStyle, color = MaterialTheme.colorScheme.onSurface)
    }
}

/**
 * Exposure scoring for a username sweep.
 *
 * Weighted so a handful of confirmed, corroborated accounts outweighs a long
 * tail of weak matches — the same principle as the graph engine's confidence
 * model, which exists so volume alone cannot manufacture a high score.
 */
fun exposureFor(profiles: Int, highConfidence: Int, categories: Int): Triple<Int, String, String> {
    val raw = profiles * 3 + highConfidence * 7 + categories * 4
    val score = raw.coerceIn(0, 100)
    return when {
        score <= 30 -> Triple(
            score, "Low exposure",
            "A small public footprint. Not much is easy to find from this handle.",
        )
        score <= 60 -> Triple(
            score, "Moderate exposure",
            "A noticeable footprint. Worth reviewing old accounts you no longer use.",
        )
        else -> Triple(
            score, "High exposure",
            "A large public footprint spanning several categories. Consider tightening privacy on accounts you have stopped using.",
        )
    }
}
