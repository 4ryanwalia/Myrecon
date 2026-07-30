package com.aryan.myrecon.ui

import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.scale
import androidx.compose.ui.platform.LocalContext

/**
 * The feel layer.
 *
 * An app made only of static composables reads as a website in a wrapper. Two
 * things change that more than any amount of styling: touches that answer back
 * physically, and state changes that are animated rather than swapped. Both
 * live here so the vocabulary stays consistent instead of each screen inventing
 * its own timings.
 */

// ── Haptics ──────────────────────────────────────────────────────

/**
 * Purpose-named haptics.
 *
 * Compose's own HapticFeedback exposes only two generic types, which is not
 * enough to distinguish "found something" from "finished". The platform
 * Vibrator's predefined effects are tuned per device by the manufacturer, so
 * they feel native rather than like a raw buzz.
 */
class Haptics(private val vibrator: Vibrator?) {

    private fun play(effectId: Int) {
        val v = vibrator ?: return
        if (!v.hasVibrator()) return
        runCatching { v.vibrate(VibrationEffect.createPredefined(effectId)) }
    }

    /** A tool was selected, a card pressed. The lightest available tap. */
    fun tap() = play(VibrationEffect.EFFECT_TICK)

    /** One account confirmed mid-scan. Deliberately the same as tap: fired up
     *  to seventy times in six seconds, anything heavier becomes a drone. */
    fun found() = play(VibrationEffect.EFFECT_TICK)

    /** The scan finished. One firmer thump to mark the transition. */
    fun complete() = play(VibrationEffect.EFFECT_HEAVY_CLICK)

    /** Something went wrong. */
    fun error() = play(VibrationEffect.EFFECT_DOUBLE_CLICK)
}

val LocalHaptics = staticCompositionLocalOf { Haptics(null) }

@Composable
fun rememberHaptics(): Haptics {
    val context = LocalContext.current
    return remember(context) { Haptics(systemVibrator(context)) }
}

private fun systemVibrator(context: Context): Vibrator? =
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        (context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager)?.defaultVibrator
    } else {
        @Suppress("DEPRECATION")
        context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
    }

// ── Press response ───────────────────────────────────────────────

/**
 * Shrinks slightly while held.
 *
 * The effect people read as "premium" on iOS is almost entirely this: a surface
 * that acknowledges the finger before the action resolves. A spring rather than
 * a tween, so release overshoots a fraction and feels elastic instead of
 * mechanical.
 *
 * @param source share the same MutableInteractionSource with the clickable so
 *   the scale tracks real press state rather than a duplicate.
 */
fun Modifier.pressScale(
    source: MutableInteractionSource,
    pressed: Float = 0.972f,
): Modifier = composed {
    val isPressed by source.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (isPressed) pressed else 1f,
        animationSpec = spring(
            dampingRatio = Spring.DampingRatioMediumBouncy,
            stiffness = Spring.StiffnessMedium,
        ),
        label = "pressScale",
    )
    scale(scale)
}

// ── Numbers that move ────────────────────────────────────────────

/**
 * Animates toward a target integer.
 *
 * A counter that jumps reads as data being replaced; one that climbs reads as
 * data being discovered. Used for the live found-count and the exposure score.
 */
@Composable
fun animatedInt(target: Int, durationMillis: Int = 420): Int {
    val v by animateFloatAsState(
        targetValue = target.toFloat(),
        animationSpec = tween(durationMillis),
        label = "animatedInt",
    )
    return v.toInt()
}
