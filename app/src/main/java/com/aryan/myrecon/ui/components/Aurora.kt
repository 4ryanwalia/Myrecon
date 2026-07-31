package com.aryan.myrecon.ui.components

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlin.math.cos
import kotlin.math.sin

/**
 * Ambient background.
 *
 * A Compose app reads as flat mainly because nothing moves unless the user
 * moves it. Three large, low-opacity colour fields drifting on slow independent
 * orbits fix that without competing for attention.
 *
 * PERFORMANCE, which dictates the shape of this code:
 *
 * The obvious implementation — animating inside a full-screen Canvas — re-runs
 * the draw every frame for as long as the screen is open. That was measurably
 * too expensive: on a software-rendered emulator it starved SystemUI badly
 * enough to trigger an ANR, and on real hardware it would be steady GPU load
 * and battery drain for pure decoration.
 *
 * Instead each field is a fixed Box whose background brush is built once and
 * cached. Only `graphicsLayer` translation is animated, which the render thread
 * applies to an existing layer without re-executing any draw commands. The
 * motion is identical; the per-frame cost is close to nothing.
 *
 * Orbit periods (23s / 31s / 19s) share no common factor, so the three never
 * resynchronise into a visible loop.
 */
@Composable
fun AuroraBackground(
    modifier: Modifier = Modifier,
    intensity: Float = 1f,
) {
    val dark = isSystemInDarkTheme()
    val context = LocalContext.current

    // Someone who has switched system animations off has asked for stillness,
    // and a drifting background ignores that more visibly than most effects.
    val animate = remember {
        android.provider.Settings.Global.getFloat(
            context.contentResolver,
            android.provider.Settings.Global.ANIMATOR_DURATION_SCALE,
            1f,
        ) != 0f
    }

    val transition = rememberInfiniteTransition(label = "aurora")

    @Composable
    fun orbit(periodMs: Int, label: String): Float =
        if (!animate) 0f else transition.animateFloat(
            initialValue = 0f,
            targetValue = (2 * Math.PI).toFloat(),
            animationSpec = infiniteRepeatable(
                tween(periodMs, easing = LinearEasing),
                RepeatMode.Restart,
            ),
            label = label,
        ).value

    // The logo's own cyan-to-indigo range, so the ambience reads as the brand
    // rather than decoration bolted on afterwards.
    val cyan = Color(0xFF22D3EE)
    val blue = Color(0xFF3B82F6)
    val indigo = Color(0xFF6366F1)

    // Light mode needs far less: the same alpha over white becomes haze and
    // costs text contrast.
    val alpha = (if (dark) 0.22f else 0.10f) * intensity.coerceIn(0f, 1f)

    BoxWithConstraints(modifier.fillMaxSize()) {
        val w = maxWidth
        val h = maxHeight
        val field = (if (w > h) w else h) * 1.15f

        @Composable
        fun Field(colour: Color, baseX: Float, baseY: Float, ampX: Float, ampY: Float, angle: Float) {
            // Brush is remembered on colour+alpha only, so it survives every
            // animation frame instead of being rebuilt 60 times a second.
            val brush = remember(colour, alpha) {
                Brush.radialGradient(
                    colors = listOf(colour.copy(alpha = alpha), Color.Transparent),
                )
            }
            val px = with(androidx.compose.ui.platform.LocalDensity.current) { w.toPx() }
            val py = with(androidx.compose.ui.platform.LocalDensity.current) { h.toPx() }
            val fieldPx = with(androidx.compose.ui.platform.LocalDensity.current) { field.toPx() }

            Box(
                Modifier
                    .size(field)
                    .graphicsLayer {
                        translationX = px * baseX - fieldPx / 2 + px * ampX * cos(angle)
                        translationY = py * baseY - fieldPx / 2 + py * ampY * sin(angle)
                    }
                    .background(brush)
            )
        }

        Field(cyan, 0.22f, 0.16f, 0.16f, 0.10f, orbit(23_000, "a"))
        Field(indigo, 0.84f, 0.32f, 0.14f, 0.12f, orbit(31_000, "b"))
        Field(blue, 0.50f, 0.86f, 0.20f, 0.08f, orbit(19_000, "c"))
    }
}
