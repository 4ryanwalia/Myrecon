package com.aryan.myrecon.ui.components

import androidx.compose.animation.core.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.ui.theme.LocalReconTokens

/**
 * Depth.
 *
 * Flat surfaces on a flat ground are what make an interface read as a document
 * rather than an object. Three things fix that, and they are all here so the
 * vocabulary stays consistent instead of each screen inventing its own:
 *
 *   glass  — a translucent panel that lets the aurora through, so the layer
 *            beneath is visible and the panel has somewhere to sit.
 *   glow   — coloured bloom under an element, which reads as light emitted
 *            rather than a border drawn.
 *   sheen  — a one-pixel highlight along the top edge, the oldest trick for
 *            implying a light source above the screen.
 */

/**
 * Translucent panel.
 *
 * Alpha rather than a real blur: `RenderEffect` needs API 31 and costs an
 * offscreen pass per frame. Over a soft gradient the difference is not visible,
 * and this runs on anything.
 */
@Composable
fun GlassSurface(
    modifier: Modifier = Modifier,
    shape: Shape = RoundedCornerShape(16.dp),
    tint: Color? = null,
    elevation: Dp = 0.dp,
    content: @Composable ColumnScope.() -> Unit,
) {
    val t = LocalReconTokens.current
    val base = tint ?: MaterialTheme.colorScheme.surface

    Column(
        modifier
            .then(if (elevation > 0.dp) Modifier.shadow(elevation, shape, clip = false) else Modifier)
            .clip(shape)
            .background(
                Brush.verticalGradient(
                    listOf(base.copy(alpha = 0.92f), base.copy(alpha = 0.78f)),
                )
            )
            // Top-edge sheen: brighter where light would fall, fading to the
            // ordinary border by the bottom.
            .border(
                BorderStroke(
                    1.dp,
                    Brush.verticalGradient(
                        listOf(
                            Color.White.copy(alpha = 0.10f),
                            t.border.copy(alpha = 0.85f),
                        )
                    ),
                ),
                shape,
            ),
        content = content,
    )
}

/**
 * Coloured bloom beneath an element.
 *
 * Drawn behind rather than as a shadow so the colour survives — an elevation
 * shadow is always neutral, and neutral does not read as emitted light.
 */
fun Modifier.glow(
    colour: Color,
    radius: Dp = 22.dp,
    alpha: Float = 0.30f,
): Modifier = drawBehind {
    val spread = radius.toPx()
    drawCircle(
        brush = Brush.radialGradient(
            colors = listOf(colour.copy(alpha = alpha), Color.Transparent),
            center = Offset(size.width / 2, size.height / 2),
            radius = maxOf(size.width, size.height) / 2 + spread,
        ),
        radius = maxOf(size.width, size.height) / 2 + spread,
        center = Offset(size.width / 2, size.height / 2),
    )
}

/**
 * Slow breathing scale, for something that should look live rather than idle.
 * Used on the active scan indicator; too subtle to notice directly, obvious by
 * its absence.
 */
@Composable
fun rememberBreath(
    periodMs: Int = 2600,
    from: Float = 1f,
    to: Float = 1.04f,
): Float {
    val t = rememberInfiniteTransition(label = "breath")
    return t.animateFloat(
        initialValue = from,
        targetValue = to,
        animationSpec = infiniteRepeatable(
            tween(periodMs, easing = FastOutSlowInEasing),
            RepeatMode.Reverse,
        ),
        label = "breathScale",
    ).value
}

/**
 * Staggered entrance for a list of children.
 *
 * Capped at [maxStagger]: past roughly a dozen items the delay stops reading as
 * choreography and starts reading as lag.
 */
@Composable
fun EnterStaggered(
    index: Int,
    maxStagger: Int = 12,
    stepMs: Int = 38,
    content: @Composable () -> Unit,
) {
    var shown by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        kotlinx.coroutines.delay((index.coerceAtMost(maxStagger) * stepMs).toLong())
        shown = true
    }
    val alpha by animateFloatAsState(
        targetValue = if (shown) 1f else 0f,
        animationSpec = tween(240),
        label = "enterAlpha",
    )
    val rise by animateFloatAsState(
        targetValue = if (shown) 0f else 18f,
        animationSpec = spring(dampingRatio = 0.78f, stiffness = Spring.StiffnessLow),
        label = "enterRise",
    )
    Box(
        Modifier.graphicsLayer {
            this.alpha = alpha
            this.translationY = rise
        },
    ) { content() }
}
