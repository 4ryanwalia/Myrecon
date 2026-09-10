package com.aryan.myrecon.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.data.Connectivity
import com.aryan.myrecon.ui.theme.LocalReconTokens
import kotlinx.coroutines.flow.Flow

/**
 * Live connectivity, for screens that need to react rather than just check once.
 *
 * Remembered per context so the callback is registered once and torn down with
 * the composition.
 */
@Composable
fun rememberOnline(): Boolean {
    val context = LocalContext.current
    val flow: Flow<Boolean> = remember(context) { Connectivity.flow(context.applicationContext) }
    val online by flow.collectAsState(initial = Connectivity.isOnline(context))
    return online
}

/**
 * Says the connection is gone, and what still works without it.
 *
 * The second half matters more than the first. "You're offline" on its own
 * reads as "the app is dead"; naming the three tools that are entirely local
 * turns a dead end into a redirect, and those tools are genuinely useful — the
 * photo reader and the password check never touch the network at all.
 */
@Composable
fun OfflineNotice(
    body: String = "MyRecon needs a connection to check public sources. " +
        "Nothing was searched, so nothing was missed — try again once you are back on.",
    onRetry: (() -> Unit)? = null,
    modifier: Modifier = Modifier,
) {
    val t = LocalReconTokens.current
    Column(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, t.warn.copy(alpha = 0.45f), RoundedCornerShape(14.dp))
            .padding(20.dp)
            // Announced by a screen reader when it appears, rather than sitting
            // silently on a screen someone cannot see.
            .semantics { liveRegion = LiveRegionMode.Polite },
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            Icons.Filled.CloudOff,
            contentDescription = null,
            tint = t.warn,
            modifier = Modifier.size(28.dp),
        )
        Spacer(Modifier.height(12.dp))
        Text("You are offline", style = MaterialTheme.typography.titleMedium, color = t.warn)
        Spacer(Modifier.height(6.dp))
        Text(
            body,
            style = MaterialTheme.typography.bodySmall,
            color = t.textDim,
        )
        Spacer(Modifier.height(12.dp))
        Text(
            "Still works with no signal: reading a photo, decoding a QR code, " +
                "and checking a password.",
            style = MaterialTheme.typography.bodySmall,
            color = t.textMute,
        )

        if (onRetry != null) {
            Spacer(Modifier.height(14.dp))
            Button(onClick = onRetry, shape = RoundedCornerShape(11.dp)) {
                Text("Try again")
            }
        }
    }
}
