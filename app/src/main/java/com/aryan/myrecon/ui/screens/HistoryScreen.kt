package com.aryan.myrecon.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.data.HistoryEntry
import com.aryan.myrecon.data.ReconStore
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.components.ShareButton
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.MonoStyle
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Everything looked up on this phone, kept so it can be read again and sent on.
 *
 * Before this, a result existed only until the next search — someone could find
 * that a stranger's photo was taken outside their house, close the app, and
 * have nothing. The report is stored as finished text, so opening an old entry
 * costs no network and works with no signal.
 *
 * Local only. Nothing here is uploaded, and Clear all genuinely deletes it.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HistoryScreen(onClose: () -> Unit) {
    val context = LocalContext.current
    val t = LocalReconTokens.current
    val haptics = LocalHaptics.current
    val store = remember(context) { ReconStore(context.applicationContext) }
    val scope = rememberCoroutineScope()

    val entries by store.history.collectAsState(initial = emptyList())
    var open by rememberSaveable { mutableStateOf<String?>(null) }
    var confirmClear by remember { mutableStateOf(false) }

    val current = entries.firstOrNull { it.id == open }
    if (current != null) {
        HistoryDetail(current, onBack = { open = null })
        return
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Your past checks") },
                navigationIcon = {
                    IconButton(onClick = { haptics.tap(); onClose() }) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back",
                        )
                    }
                },
                actions = {
                    if (entries.isNotEmpty()) {
                        IconButton(onClick = { confirmClear = true }) {
                            Icon(
                                Icons.Filled.DeleteOutline,
                                contentDescription = "Delete every saved check",
                                tint = t.textDim,
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
            )
        },
    ) { inner ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(inner)
                .background(MaterialTheme.colorScheme.background)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
        ) {
            if (entries.isEmpty()) {
                Spacer(Modifier.height(40.dp))
                Text("Nothing saved yet", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                Text(
                    "Every search, photo and QR code you check gets kept here so you can " +
                        "read it again later or send it to someone. It stays on this phone — " +
                        "we never see it.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = t.textDim,
                )
                return@Column
            }

            Text(
                "Kept on this phone only. The last ${entries.size} checks.",
                style = MaterialTheme.typography.bodySmall,
                color = t.textMute,
            )
            Spacer(Modifier.height(12.dp))

            entries.forEach { e ->
                HistoryRow(
                    entry = e,
                    onOpen = { haptics.tap(); open = e.id },
                    onDelete = { scope.launch { store.deleteHistory(e.id) } },
                )
            }
        }
    }

    if (confirmClear) {
        AlertDialog(
            onDismissRequest = { confirmClear = false },
            title = { Text("Delete every saved check?") },
            text = {
                Text(
                    "All ${entries.size} saved reports will be removed from this phone. " +
                        "This cannot be undone."
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    confirmClear = false
                    scope.launch { store.clearHistory() }
                }) { Text("Delete all") }
            },
            dismissButton = {
                TextButton(onClick = { confirmClear = false }) { Text("Keep them") }
            },
        )
    }
}

@Composable
private fun HistoryRow(entry: HistoryEntry, onOpen: () -> Unit, onDelete: () -> Unit) {
    val t = LocalReconTokens.current
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 5.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, t.border, RoundedCornerShape(12.dp))
            .clickable(onClick = onOpen)
            .padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // Read as one item rather than four fragments.
        Column(Modifier.weight(1f).semantics(mergeDescendants = true) {}) {
            Text(
                entry.kind.uppercase(),
                style = MaterialTheme.typography.labelSmall,
                color = t.textMute,
            )
            Spacer(Modifier.height(3.dp))
            Text(
                entry.query,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.height(2.dp))
            Text(
                entry.headline,
                style = MaterialTheme.typography.bodySmall,
                color = t.textDim,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                SimpleDateFormat("d MMM, HH:mm", Locale.getDefault()).format(Date(entry.at)),
                style = MaterialTheme.typography.labelSmall,
                color = t.textMute,
            )
        }
        IconButton(onClick = onDelete) {
            Icon(
                Icons.Filled.DeleteOutline,
                contentDescription = "Delete this saved check",
                tint = t.textMute,
                modifier = Modifier.size(19.dp),
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HistoryDetail(entry: HistoryEntry, onBack: () -> Unit) {
    val t = LocalReconTokens.current
    val haptics = LocalHaptics.current
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(entry.query, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                navigationIcon = {
                    IconButton(onClick = { haptics.tap(); onBack() }) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back to the list",
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
            )
        },
    ) { inner ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(inner)
                .background(MaterialTheme.colorScheme.background)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
        ) {
            ShareButton(
                subject = "${entry.kind} check: ${entry.query}",
                body = entry.report,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(14.dp))
            // The stored text verbatim, in a monospaced block: this is exactly
            // what gets shared, so showing anything else would be a surprise.
            Text(
                entry.report,
                style = MonoStyle,
                color = t.textDim,
            )
            Spacer(Modifier.height(30.dp))
        }
    }
}
