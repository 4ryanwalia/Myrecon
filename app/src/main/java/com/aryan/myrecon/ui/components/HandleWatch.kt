package com.aryan.myrecon.ui.components

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Radar
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.data.ReconStore
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.work.BreachWatchWorker
import com.aryan.myrecon.work.HandleWatchWorker
import kotlinx.coroutines.launch

/**
 * Offers to keep watching a handle after a sweep has run.
 *
 * This is the only alert in the app about *change* rather than about news. A
 * breach feed can tell you a company was hacked; nothing anywhere tells you
 * that a new account has appeared under the handle you have used for fifteen
 * years — someone registering it, or an old profile of yours resurfacing.
 *
 * Offered after the results, because the trade only makes sense once the user
 * has seen what the sweep found: watching means "tell me when *this* changes",
 * and the list on screen is what it would be changing from.
 */
@Composable
fun HandleWatchCard(handle: String, modifier: Modifier = Modifier) {
    if (handle.isBlank()) return

    val context = LocalContext.current
    val t = LocalReconTokens.current
    val haptics = LocalHaptics.current
    val store = remember(context) { ReconStore(context.applicationContext) }
    val scope = rememberCoroutineScope()

    val watched by store.watchedHandles.collectAsState(initial = emptySet())
    val clean = handle.trim().removePrefix("@").lowercase()
    val on = clean in watched

    var granted by remember {
        mutableStateOf(
            Build.VERSION.SDK_INT < 33 ||
                context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) ==
                PackageManager.PERMISSION_GRANTED
        )
    }

    fun start() {
        scope.launch { store.watchHandle(clean) }
        BreachWatchWorker.ensureChannel(context)
        HandleWatchWorker.schedule(context)
    }

    val ask = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { ok ->
        granted = ok
        // Watch anyway if permission is refused. The comparison still runs and
        // the result is still there next time the app is opened — declining a
        // notification is not the same as declining the feature.
        start()
    }

    Column(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(
                1.dp,
                if (on) t.ok.copy(alpha = 0.45f) else t.border,
                RoundedCornerShape(14.dp),
            )
            .padding(15.dp),
    ) {
        Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            Icon(
                Icons.Filled.Radar,
                contentDescription = null,
                tint = if (on) t.ok else MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(20.dp),
            )
            Spacer(Modifier.width(11.dp))
            Column(Modifier.weight(1f)) {
                Text("Watch @$clean", style = MaterialTheme.typography.titleMedium)
                Text(
                    if (on) "Re-checked weekly on this device"
                    else "Tell me if a new account appears",
                    style = MaterialTheme.typography.bodySmall,
                    color = t.textMute,
                )
            }
            Switch(
                checked = on,
                onCheckedChange = { want ->
                    haptics.tap()
                    if (!want) {
                        scope.launch { store.unwatchHandle(clean) }
                    } else if (granted) {
                        start()
                    } else {
                        ask.launch(Manifest.permission.POST_NOTIFICATIONS)
                    }
                },
            )
        }

        Spacer(Modifier.height(10.dp))
        Text(
            "MyRecon re-runs this sweep once a week, on Wi-Fi, and tells you only when " +
                "something appears that is not in the list above. The check runs on this " +
                "device against the same public pages — the handle is not sent to us.",
            style = MaterialTheme.typography.bodySmall,
            color = t.textDim,
        )
    }
}
