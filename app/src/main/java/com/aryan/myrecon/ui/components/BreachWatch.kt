package com.aryan.myrecon.ui.components

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.work.BreachWatchWorker

/**
 * Opt-in for breach alerts.
 *
 * The privacy claim is the whole pitch and it is literally true: the app
 * downloads the public breach catalogue and compares it on the device. No
 * address is transmitted, there is no account, and nobody is told what is being
 * watched — which is the opposite of every hosted breach-alert service, all of
 * which require handing over the email first.
 *
 * Notification permission is requested here, at the moment the user asks for
 * alerts, rather than at launch where it reads as a demand.
 */
@Composable
fun BreachWatchCard(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val t = LocalReconTokens.current
    val haptics = LocalHaptics.current

    var enabled by rememberSaveable { mutableStateOf(false) }
    var granted by remember {
        mutableStateOf(
            Build.VERSION.SDK_INT < 33 ||
                context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) ==
                PackageManager.PERMISSION_GRANTED
        )
    }

    val ask = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { ok ->
        granted = ok
        if (ok) {
            enabled = true
            BreachWatchWorker.ensureChannel(context)
            BreachWatchWorker.schedule(context)
            BreachWatchWorker.runNow(context)
        }
    }

    Column(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, if (enabled) t.ok.copy(alpha = 0.45f) else t.border, RoundedCornerShape(14.dp))
            .padding(15.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                Icons.Filled.NotificationsActive,
                contentDescription = null,
                tint = if (enabled) t.ok else MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(20.dp),
            )
            Spacer(Modifier.width(11.dp))
            Column(Modifier.weight(1f)) {
                Text("Tell me about new breaches", style = MaterialTheme.typography.titleMedium)
                Text(
                    "Checked daily on this device",
                    style = MaterialTheme.typography.bodySmall,
                    color = t.textMute,
                )
            }
            Switch(
                checked = enabled,
                onCheckedChange = { want ->
                    haptics.tap()
                    if (!want) {
                        enabled = false
                        return@Switch
                    }
                    if (granted) {
                        enabled = true
                        BreachWatchWorker.ensureChannel(context)
                        BreachWatchWorker.schedule(context)
                        BreachWatchWorker.runNow(context)
                    } else {
                        ask.launch(Manifest.permission.POST_NOTIFICATIONS)
                    }
                },
            )
        }

        Spacer(Modifier.height(10.dp))
        Text(
            "When a breach is published, MyRecon tells you it happened and how many accounts " +
                "were exposed, so you can check whether yours was one of them.",
            style = MaterialTheme.typography.bodySmall,
            color = t.textDim,
        )

        AnimatedVisibility(visible = enabled) {
            Column {
                Spacer(Modifier.height(11.dp))
                Row(
                    Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(9.dp))
                        .background(t.ok.copy(alpha = 0.10f))
                        .padding(horizontal = 10.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(
                        Modifier
                            .size(6.dp)
                            .clip(RoundedCornerShape(99.dp))
                            .background(t.ok),
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "Watching. Your email address is never sent anywhere — the public " +
                            "breach list is downloaded and compared here.",
                        style = MaterialTheme.typography.bodySmall,
                        color = t.ok,
                    )
                }
            }
        }
    }
}
