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
import androidx.compose.foundation.text.KeyboardOptions
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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.data.ReconStore
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.work.BreachWatchWorker
import kotlinx.coroutines.launch

/**
 * Opt-in for breach alerts.
 *
 * The privacy claim is the whole pitch and it stays literally true for this
 * switch: the app downloads the public breach catalogue and compares it on the
 * device. No address is transmitted, there is no account, and nobody is told
 * what is being watched — the opposite of every hosted breach-alert service,
 * all of which require handing over the email first.
 *
 * [AddressWatchSection] below offers the stronger, per-address check, which
 * does transmit. It is a separate switch with its own disclosure precisely so
 * that this claim keeps meaning what it says.
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
                        "Watching. The public breach list is downloaded and compared on " +
                            "this device — nothing is sent anywhere for this check.",
                        style = MaterialTheme.typography.bodySmall,
                        color = t.ok,
                    )
                }

                Spacer(Modifier.height(12.dp))
                AddressWatchSection()
            }
        }
    }
}

/**
 * The second, separate opt-in: checking specific addresses.
 *
 * Deliberately its own switch rather than part of the card above. The
 * catalogue alert transmits nothing and that is the app's distinguishing
 * claim; this one sends the address to a third party. Folding them into one
 * toggle would buy the second with consent given for the first, and quietly
 * make the promise printed directly above it untrue.
 *
 * The disclosure is stated before the switch, not after, and names the service
 * rather than saying "a third party".
 */
@Composable
private fun AddressWatchSection() {
    val context = LocalContext.current
    val t = LocalReconTokens.current
    val haptics = LocalHaptics.current
    val scope = rememberCoroutineScope()
    val store = remember { ReconStore(context) }

    val monitoring by store.emailMonitoring.collectAsState(initial = false)
    val watched by store.watchedEmails.collectAsState(initial = emptySet())
    var draft by rememberSaveable { mutableStateOf("") }

    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Also check my address", style = MaterialTheme.typography.titleSmall)
                Text(
                    "Tells you when your address turns up, not just that a breach happened",
                    style = MaterialTheme.typography.bodySmall,
                    color = t.textMute,
                )
            }
            Switch(
                checked = monitoring,
                onCheckedChange = { want ->
                    haptics.tap()
                    scope.launch { store.setEmailMonitoring(want) }
                },
            )
        }

        Spacer(Modifier.height(8.dp))
        Text(
            "This one does send your address — to leakcheck.io, once a day, to ask which " +
                "breaches it appears in. That is the only way to answer the question. The " +
                "breach-list check above stays entirely on this device either way. Turning " +
                "this off deletes what was stored for each address.",
            style = MaterialTheme.typography.bodySmall,
            color = t.warn,
        )

        AnimatedVisibility(visible = monitoring) {
            Column {
                Spacer(Modifier.height(12.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = draft,
                        onValueChange = { draft = it },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                        label = { Text("Email address") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                    )
                    Spacer(Modifier.width(8.dp))
                    TextButton(
                        enabled = draft.trim().contains("@"),
                        onClick = {
                            haptics.tap()
                            val value = draft
                            draft = ""
                            scope.launch { store.watchEmail(value) }
                        },
                    ) { Text("Watch") }
                }

                if (watched.isEmpty()) {
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "No addresses yet. The first check records what is already known " +
                            "without alerting — you are told about what appears after that.",
                        style = MaterialTheme.typography.bodySmall,
                        color = t.textMute,
                    )
                } else {
                    watched.sorted().forEach { email ->
                        Row(
                            Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                email,
                                style = MaterialTheme.typography.bodyMedium,
                                modifier = Modifier.weight(1f),
                            )
                            TextButton(onClick = {
                                haptics.tap()
                                scope.launch { store.unwatchEmail(email) }
                            }) { Text("Stop") }
                        }
                    }
                }
            }
        }
    }
}
