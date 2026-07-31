package com.aryan.myrecon.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * MyRecon palette, carried over verbatim from the web design system
 * (frontend/assets/css/styles.css) so the app and site read as one product.
 */

// ── Dark (default) ───────────────────────────────────────────────
//
// Pulled well below the web palette's navy toward near-black. A #0A0F1A ground
// reads as "dark theme"; #04070B reads as an instrument, and it is what makes
// a cyan accent look emitted rather than printed.
val DarkBg = Color(0xFF04070B)
val DarkBgSoft = Color(0xFF080C13)
val DarkSurface = Color(0xFF0B1119)
val DarkSurface2 = Color(0xFF121A25)
val DarkBorder = Color(0xFF1B2634)
val DarkBorderStrong = Color(0xFF2C3D50)
val DarkText = Color(0xFFDDE7F0)
val DarkTextDim = Color(0xFF8497A9)
val DarkTextMute = Color(0xFF4E5F72)

// Cyan, not blue. The logo already runs cyan-to-indigo, and cyan on near-black
// is the colour of a readout — blue on navy is the colour of a web page.
val DarkAccent = Color(0xFF22D3EE)
val DarkAccent2 = Color(0xFF06B6D4)

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
