package com.aryan.myrecon.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.Mono

/**
 * Category colours.
 *
 * Fetching 117 real favicons would mean 117 extra requests and a licensing
 * question per logo, so identity comes from a coloured monogram instead. Hue is
 * derived from the platform's category rather than its name, which means the
 * result list reads as grouped even when scrolled past quickly.
 *
 * These sit apart from both the brand accent and the confidence scale — a
 * category colour must never be mistaken for a severity signal.
 */
private val CATEGORY_HUES = mapOf(
    "Social" to Color(0xFFEC4899),
    "Professional" to Color(0xFF0EA5E9),
    "Developer" to Color(0xFF8B5CF6),
    "Forums" to Color(0xFFF97316),
    "Video" to Color(0xFFEF4444),
    "Audio" to Color(0xFF14B8A6),
    "Gaming" to Color(0xFF22C55E),
    "Photo & Art" to Color(0xFFA855F7),
    "Blogging" to Color(0xFF6366F1),
    "Finance" to Color(0xFF10B981),
    "Messaging" to Color(0xFF3B82F6),
    "Academic" to Color(0xFF64748B),
    "Marketplace" to Color(0xFFF59E0B),
    "Paste" to Color(0xFF78716C),
    "Other" to Color(0xFF6B7280),
)

fun categoryColor(category: String): Color =
    CATEGORY_HUES[category] ?: CATEGORY_HUES.getValue("Other")

/**
 * Monogram tile for a platform.
 *
 * Two letters, because one collides constantly across 117 names ("Kick" and
 * "Kaggle" both start with K) and three stops fitting at this size.
 */
@Composable
fun PlatformTile(
    platform: String,
    category: String,
    size: Int = 40,
    modifier: Modifier = Modifier,
) {
    val hue = categoryColor(category)
    val initials = platform
        .filter { it.isLetterOrDigit() || it == ' ' }
        .split(' ')
        .filter { it.isNotBlank() }
        .let { parts ->
            when {
                parts.size >= 2 -> "${parts[0].first()}${parts[1].first()}"
                parts.isNotEmpty() -> parts[0].take(2)
                else -> "??"
            }
        }
        .uppercase()

    Box(
        modifier
            .size(size.dp)
            .clip(RoundedCornerShape((size * 0.28f).dp))
            .background(
                Brush.linearGradient(
                    listOf(hue.copy(alpha = 0.30f), hue.copy(alpha = 0.14f)),
                )
            )
            .border(1.dp, hue.copy(alpha = 0.45f), RoundedCornerShape((size * 0.28f).dp)),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            initials,
            fontFamily = Mono,
            fontWeight = FontWeight.Bold,
            fontSize = androidx.compose.ui.unit.TextUnit(
                size * 0.34f,
                androidx.compose.ui.unit.TextUnitType.Sp,
            ),
            color = hue,
        )
    }
}

/** Header for a group of results, with a count and the category's colour. */
@Composable
fun CategoryHeader(category: String, count: Int) {
    val t = LocalReconTokens.current
    val hue = categoryColor(category)
    Row(
        Modifier
            .fillMaxWidth()
            .padding(top = 18.dp, bottom = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .size(width = 3.dp, height = 14.dp)
                .clip(RoundedCornerShape(99.dp))
                .background(hue),
        )
        Spacer(Modifier.width(8.dp))
        Text(
            category.uppercase(),
            style = MaterialTheme.typography.labelSmall,
            color = hue,
        )
        Spacer(Modifier.weight(1f))
        Text(
            "$count",
            style = MaterialTheme.typography.labelSmall,
            color = t.textMute,
        )
    }
}
