package com.aryan.myrecon.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.theme.LocalReconTokens

private const val SERVICES_URL = "https://www.myrecon.xyz/services.html"

/**
 * The offer of a hand-done report, shown under a finished result.
 *
 * Placed after the findings rather than before them, and only once a scan has
 * actually run. Someone who has just seen eleven forgotten accounts is a
 * person with a live question; the same card on an empty screen is an advert.
 *
 * The copy is bounded on purpose. The service page already promises discovery,
 * a written report and removal, so this says the same thing in one breath and
 * links there — it does not invent a second, slightly different promise, and it
 * does not imply the automated scan was deliberately holding anything back.
 * It also says "paid" out loud, because finding that out after clicking is the
 * kind of small dishonesty people remember about a security tool.
 */
@Composable
fun DetailedReportOffer(modifier: Modifier = Modifier) {
    val t = LocalReconTokens.current
    val uri = LocalUriHandler.current
    val haptics = LocalHaptics.current
    val accent = MaterialTheme.colorScheme.primary

    Column(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(3.dp))
            .background(MaterialTheme.colorScheme.surface)
            .bracketFrame(accent.copy(alpha = 0.55f))
            .clickable { haptics.tap(); uri.openUri(SERVICES_URL) }
            .padding(16.dp),
    ) {
        Text("Want the full picture?", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(7.dp))
        // Deliberately not about handles. This card sits under every result
        // type, so copy that said "the handle you searched" was simply wrong
        // beneath a DNS or IP report.
        Text(
            "MyRecon checks what is publicly indexed. A personal report goes further: " +
                "we search by hand across sources the app cannot reach, confirm which " +
                "results are genuinely yours, and work through getting them removed — " +
                "including the data-broker listings you never created.",
            style = MaterialTheme.typography.bodySmall,
            color = t.textDim,
        )
        Spacer(Modifier.height(10.dp))
        Text(
            "A paid service, and only ever on identifiers you own and can verify.",
            style = MaterialTheme.typography.bodySmall,
            color = t.textMute,
        )
        Spacer(Modifier.height(12.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "See what's included",
                style = MaterialTheme.typography.labelLarge,
                color = accent,
            )
            Spacer(Modifier.width(7.dp))
            Icon(
                Icons.AutoMirrored.Filled.OpenInNew,
                contentDescription = null,
                tint = accent,
                modifier = Modifier.size(15.dp),
            )
        }
    }
}
