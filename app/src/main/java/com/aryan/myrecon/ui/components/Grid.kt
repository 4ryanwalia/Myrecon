package com.aryan.myrecon.ui.components

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp

/**
 * Technical grid backdrop.
 *
 * The reference is a drafting sheet or an instrument readout, not a web page:
 * a fine ruled grid on near-black, with a single soft pool of light where the
 * eye should start. It is what makes the app read as apparatus rather than an
 * app with a dark theme.
 *
 * Drawn once per size change, not per frame. The grid is static — the only
 * animated element is a slow horizontal sweep, and that is a single translated
 * line rather than a redraw of the lattice.
 */
@Composable
fun GridBackdrop(
    modifier: Modifier = Modifier,
    cell: Int = 28,
    sweep: Boolean = true,
) {
    val dark = isSystemInDarkTheme()
    val context = LocalContext.current

    val animate = remember {
        android.provider.Settings.Global.getFloat(
            context.contentResolver,
            android.provider.Settings.Global.ANIMATOR_DURATION_SCALE,
            1f,
        ) != 0f
    } && sweep

    val t = rememberInfiniteTransition(label = "grid")
    // 9s is slow enough to register as ambient rather than as something
    // demanding to be watched.
    val pass = if (!animate) -1f else t.animateFloat(
        initialValue = -0.2f,
        targetValue = 1.2f,
        animationSpec = infiniteRepeatable(tween(9_000, easing = LinearEasing), RepeatMode.Restart),
        label = "sweepPass",
    ).value

    val line = if (dark) Color(0xFF16202C) else Color(0xFFE3E9F0)
    val major = if (dark) Color(0xFF1D2A38) else Color(0xFFD5DEE8)
    val glowCyan = Color(0xFF22D3EE)

    Canvas(modifier.fillMaxSize()) {
        val step = cell.dp.toPx()

        // A pool of light behind the top-left, where reading starts. Low alpha
        // so it lifts the corner without tinting the content above it.
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(
                    glowCyan.copy(alpha = if (dark) 0.10f else 0.05f),
                    Color.Transparent,
                ),
                center = Offset(size.width * 0.18f, size.height * 0.06f),
                radius = size.width * 0.95f,
            ),
            radius = size.width * 0.95f,
            center = Offset(size.width * 0.18f, size.height * 0.06f),
        )

        // Minor rules, with every fourth drawn brighter — the same convention
        // as graph paper, and it stops the lattice reading as flat texture.
        var x = 0f
        var i = 0
        while (x <= size.width) {
            drawLine(
                color = if (i % 4 == 0) major else line,
                start = Offset(x, 0f),
                end = Offset(x, size.height),
                strokeWidth = 1f,
            )
            x += step; i++
        }
        var y = 0f
        i = 0
        while (y <= size.height) {
            drawLine(
                color = if (i % 4 == 0) major else line,
                start = Offset(0f, y),
                end = Offset(size.width, y),
                strokeWidth = 1f,
            )
            y += step; i++
        }

        // The sweep: a soft band travelling down the screen, brightest at its
        // leading edge. One gradient rect, no lattice redraw.
        if (pass >= 0f) {
            val bandHeight = size.height * 0.22f
            val top = size.height * pass - bandHeight
            drawRect(
                brush = Brush.verticalGradient(
                    colors = listOf(
                        Color.Transparent,
                        glowCyan.copy(alpha = if (dark) 0.055f else 0.025f),
                        Color.Transparent,
                    ),
                    startY = top,
                    endY = top + bandHeight,
                ),
                topLeft = Offset(0f, top),
                size = androidx.compose.ui.geometry.Size(size.width, bandHeight),
            )
        }
    }
}
