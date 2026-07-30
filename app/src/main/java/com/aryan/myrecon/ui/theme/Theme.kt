package com.aryan.myrecon.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

/**
 * Tokens Material 3 has no slot for.
 *
 * MyRecon's design leans on a border colour, three text weights and a
 * confidence scale — none of which map cleanly onto M3's roles. Exposing them
 * through a CompositionLocal keeps call sites reading `theme.border` rather
 * than reaching for an approximate M3 role like `outlineVariant`.
 */
data class ReconTokens(
    val bgSoft: Color,
    val surface2: Color,
    val border: Color,
    val borderStrong: Color,
    val textDim: Color,
    val textMute: Color,
    val ok: Color,
    val warn: Color,
    val danger: Color,
    val info: Color,
)

val LocalReconTokens = staticCompositionLocalOf {
    ReconTokens(
        bgSoft = DarkBgSoft, surface2 = DarkSurface2,
        border = DarkBorder, borderStrong = DarkBorderStrong,
        textDim = DarkTextDim, textMute = DarkTextMute,
        ok = OkDark, warn = WarnDark, danger = DangerDark, info = InfoDark,
    )
}

/** Confidence band → colour. Mirrors `stripeFor()` in deep-search.js. */
@Composable
fun bandColor(band: String?): Color {
    val t = LocalReconTokens.current
    return when (band?.lowercase()) {
        "high" -> t.ok
        "medium" -> t.warn
        else -> t.textMute
    }
}

private val DarkScheme = darkColorScheme(
    primary = DarkAccent,
    onPrimary = Color.White,
    primaryContainer = DarkAccent2,
    background = DarkBg,
    onBackground = DarkText,
    surface = DarkSurface,
    onSurface = DarkText,
    surfaceVariant = DarkSurface2,
    onSurfaceVariant = DarkTextDim,
    outline = DarkBorderStrong,
    outlineVariant = DarkBorder,
    error = DangerDark,
)

private val LightScheme = lightColorScheme(
    primary = LightAccent,
    onPrimary = Color.White,
    primaryContainer = LightAccent2,
    background = LightBg,
    onBackground = LightText,
    surface = LightSurface,
    onSurface = LightText,
    surfaceVariant = LightSurface2,
    onSurfaceVariant = LightTextDim,
    outline = LightBorderStrong,
    outlineVariant = LightBorder,
    error = DangerLight,
)

@Composable
fun MyReconTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    // Dynamic colour is deliberately not used: MyRecon's blue is the brand, and
    // letting the wallpaper recolour a security tool would undercut the
    // confidence palette, which depends on green/amber/grey meaning one thing.
    val scheme = if (darkTheme) DarkScheme else LightScheme
    val tokens = if (darkTheme) {
        ReconTokens(
            DarkBgSoft, DarkSurface2, DarkBorder, DarkBorderStrong,
            DarkTextDim, DarkTextMute, OkDark, WarnDark, DangerDark, InfoDark,
        )
    } else {
        ReconTokens(
            LightBgSoft, LightSurface2, LightBorder, LightBorderStrong,
            LightTextDim, LightTextMute, OkLight, WarnLight, DangerLight, InfoLight,
        )
    }

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            WindowCompat.getInsetsController(window, view)
                .isAppearanceLightStatusBars = !darkTheme
        }
    }

    CompositionLocalProvider(LocalReconTokens provides tokens) {
        MaterialTheme(colorScheme = scheme, typography = ReconTypography, content = content)
    }
}
