package com.aryan.myrecon.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.sp

/**
 * Two roles, one rule, carried over from the web build:
 *
 *   monospace = a machine-verified fact  (handles, hashes, scores, timestamps)
 *   sans      = human interpretation     (headings, prose, guidance)
 *
 * Keeping that split consistent is what makes results read as forensic rather
 * than merely styled. Uses the platform faces — bundling Inter and JetBrains
 * Mono would add roughly 1 MB to the APK for a difference few would notice on
 * a phone screen.
 */
val Mono = FontFamily.Monospace
private val Sans = FontFamily.SansSerif

val ReconTypography = Typography(
    headlineSmall = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.ExtraBold,
        fontSize = 24.sp, lineHeight = 30.sp, letterSpacing = (-0.4).sp,
    ),
    titleLarge = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.Bold,
        fontSize = 19.sp, lineHeight = 25.sp, letterSpacing = (-0.2).sp,
    ),
    titleMedium = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.SemiBold,
        fontSize = 15.sp, lineHeight = 20.sp,
    ),
    bodyLarge = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.Normal,
        fontSize = 15.sp, lineHeight = 23.sp,
    ),
    bodyMedium = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.Normal,
        fontSize = 13.5.sp, lineHeight = 20.sp,
    ),
    bodySmall = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.Normal,
        fontSize = 12.sp, lineHeight = 17.sp,
    ),
    labelLarge = TextStyle(
        fontFamily = Sans, fontWeight = FontWeight.SemiBold,
        fontSize = 14.sp, letterSpacing = 0.1.sp,
    ),
    // Uppercase section eyebrows — the web build's .section-label.
    labelSmall = TextStyle(
        fontFamily = Mono, fontWeight = FontWeight.Medium,
        fontSize = 10.sp, letterSpacing = 1.4.sp,
    ),
)

/** Evidence: anything the machine measured. Tabular so digits align in columns. */
val MonoStyle = TextStyle(
    fontFamily = Mono, fontWeight = FontWeight.Medium,
    fontSize = 12.5.sp, lineHeight = 18.sp,
)

val MonoScore = TextStyle(
    fontFamily = Mono, fontWeight = FontWeight.Bold,
    fontSize = 17.sp, textAlign = TextAlign.End,
)
