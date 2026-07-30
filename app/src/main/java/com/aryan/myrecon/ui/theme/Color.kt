package com.aryan.myrecon.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * MyRecon palette, carried over verbatim from the web design system
 * (frontend/assets/css/styles.css) so the app and site read as one product.
 */

// ── Dark (default) ───────────────────────────────────────────────
val DarkBg = Color(0xFF0A0F1A)
val DarkBgSoft = Color(0xFF0E1524)
val DarkSurface = Color(0xFF111A2B)
val DarkSurface2 = Color(0xFF16223A)
val DarkBorder = Color(0xFF1F2B42)
val DarkBorderStrong = Color(0xFF2C3C5A)
val DarkText = Color(0xFFE8EEF7)
val DarkTextDim = Color(0xFF9AABC4)
val DarkTextMute = Color(0xFF647089)
val DarkAccent = Color(0xFF3B82F6)
val DarkAccent2 = Color(0xFF2563EB)

// ── Light ────────────────────────────────────────────────────────
val LightBg = Color(0xFFF5F7FB)
val LightBgSoft = Color(0xFFEEF2F9)
val LightSurface = Color(0xFFFFFFFF)
val LightSurface2 = Color(0xFFF3F6FC)
val LightBorder = Color(0xFFE2E8F0)
val LightBorderStrong = Color(0xFFCBD5E1)
val LightText = Color(0xFF0F172A)
val LightTextDim = Color(0xFF475569)
val LightTextMute = Color(0xFF94A3B8)
val LightAccent = Color(0xFF2563EB)
val LightAccent2 = Color(0xFF1D4ED8)

/**
 * Confidence colours.
 *
 * Deliberately separate from the accent: the accent is brand, these encode
 * meaning. The light values are darkened rather than reused, because the dark
 * theme's amber (#FBBF24) measures roughly 1.5:1 on a white card — the same
 * contrast bug found and fixed on the web deep-search page, where the colour
 * carries the reading rather than decorating it.
 */
val OkDark = Color(0xFF34D399)
val WarnDark = Color(0xFFFBBF24)
val DangerDark = Color(0xFFFB7185)
val InfoDark = Color(0xFF38BDF8)

val OkLight = Color(0xFF047857)
val WarnLight = Color(0xFFA3480A)
val DangerLight = Color(0xFFBE123C)
val InfoLight = Color(0xFF0284C7)
