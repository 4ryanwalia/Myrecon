package com.aryan.myrecon.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AddPhotoAlternate
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import com.aryan.myrecon.data.GeoIntel
import com.aryan.myrecon.data.ImageForensics
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.components.ActionAdGateState
import com.aryan.myrecon.ui.components.AdActionButton
import com.aryan.myrecon.ui.components.DataList
import com.aryan.myrecon.ui.components.SectionLabel
import com.aryan.myrecon.ui.components.StatePanel
import com.aryan.myrecon.ui.components.rememberActionAdGate
import com.aryan.myrecon.ui.pressScale
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.MonoStyle
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface ImageState {
    data object Empty : ImageState
    data object Working : ImageState
    data class Done(
        val uri: Uri,
        val report: ImageForensics.Report,
        val geo: GeoIntel.Report?,
    ) : ImageState
    data class Failed(val message: String) : ImageState
}

class ImageViewModel : ViewModel() {
    private val _state = MutableStateFlow<ImageState>(ImageState.Empty)
    val state = _state.asStateFlow()

    fun analyse(context: android.content.Context, uri: Uri) {
        viewModelScope.launch {
            _state.value = ImageState.Working
            val result = ImageForensics.analyse(context, uri)
            _state.value = result.fold(
                onSuccess = { report ->
                    // Geo enrichment is additive: a failure there must not lose
                    // the forensics, which are already complete and local.
                    val gps = report.exif.gps
                    val geo = if (gps.present && GeoIntel.validCoords(gps.latitude, gps.longitude)) {
                        runCatching { GeoIntel.investigate(gps.latitude!!, gps.longitude!!) }.getOrNull()
                    } else null
                    ImageState.Done(uri, report, geo)
                },
                onFailure = { ImageState.Failed(it.message ?: "The image could not be read.") },
            )
        }
    }

    fun reset() { _state.value = ImageState.Empty }
}

@Composable
fun ImageScreen(vm: ImageViewModel = viewModel()) {
    val context = LocalContext.current
    val state by vm.state.collectAsState()
    val haptics = LocalHaptics.current
    val t = LocalReconTokens.current
    val adGate = rememberActionAdGate()

    // The photo picker needs no storage permission on any supported version —
    // the system UI hands back a single grant for the chosen item only.
    val picker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia()
    ) { uri -> uri?.let { haptics.tap(); vm.analyse(context, it) } }

    fun pick() = picker.launch(
        PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)
    )

    LaunchedEffect(state) {
        when (state) {
            is ImageState.Done -> haptics.complete()
            is ImageState.Failed -> haptics.error()
            else -> Unit
        }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
            .padding(bottom = 40.dp),
    ) {
        when (val s = state) {
            is ImageState.Empty -> {
                Spacer(Modifier.height(20.dp))
                Text("Image forensics", style = MaterialTheme.typography.headlineSmall)
                Spacer(Modifier.height(8.dp))
                Text(
                    "Reads what a photo reveals about itself: the camera that took it, when, " +
                        "and where. Everything is computed on this device from the file's own " +
                        "bytes — the picture is never uploaded.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = t.textDim,
                )
                Spacer(Modifier.height(20.dp))
                PickTile(onPick = ::pick)
            }

            is ImageState.Working -> {
                Spacer(Modifier.height(60.dp))
                Column(
                    Modifier.fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    CircularProgressIndicator(strokeWidth = 2.dp)
                    Spacer(Modifier.height(14.dp))
                    Text("Reading metadata…", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "Hashing locally, then resolving any location",
                        style = MaterialTheme.typography.bodySmall,
                        color = t.textMute,
                    )
                }
            }

            is ImageState.Failed -> {
                Spacer(Modifier.height(20.dp))
                StatePanel("Could not read that image", s.message, tint = t.danger)
                Spacer(Modifier.height(14.dp))
                PickTile(onPick = ::pick)
            }

            is ImageState.Done -> ForensicsReport(s, onPick = ::pick, gate = adGate)
        }
    }
}

@Composable
private fun PickTile(onPick: () -> Unit) {
    val t = LocalReconTokens.current
    val source = remember { MutableInteractionSource() }
    Column(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 150.dp)
            .pressScale(source)
            .clip(RoundedCornerShape(16.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, t.border, RoundedCornerShape(16.dp))
            .clickable(interactionSource = source, indication = null, onClick = onPick)
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(
            Icons.Filled.AddPhotoAlternate,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(34.dp),
        )
        Spacer(Modifier.height(10.dp))
        Text("Choose a photo", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(4.dp))
        Text(
            "Nothing leaves your device",
            style = MaterialTheme.typography.bodySmall,
            color = t.textMute,
        )
    }
}

@Composable
private fun ForensicsReport(
    s: ImageState.Done,
    onPick: () -> Unit,
    gate: ActionAdGateState,
) {
    val t = LocalReconTokens.current
    val uriHandler = LocalUriHandler.current
    val r = s.report

    AsyncImage(
        model = s.uri,
        contentDescription = null,
        contentScale = ContentScale.Crop,
        modifier = Modifier
            .fillMaxWidth()
            .height(190.dp)
            .clip(RoundedCornerShape(16.dp))
            .background(t.surface2),
    )

    // ── Location leads: it is the finding people care about most ──
    s.geo?.let { geo ->
        if (geo.place.found) {
            SectionLabel("Where it was taken")
            Column(
                Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(14.dp))
                    .background(t.ok.copy(alpha = 0.10f))
                    .border(1.dp, t.ok.copy(alpha = 0.4f), RoundedCornerShape(14.dp))
                    .padding(16.dp),
            ) {
                Text(
                    geo.place.name ?: geo.place.city ?: "Located",
                    style = MaterialTheme.typography.titleLarge,
                    color = t.ok,
                )
                geo.place.displayName?.let {
                    Spacer(Modifier.height(4.dp))
                    Text(it, style = MaterialTheme.typography.bodySmall, color = t.textDim)
                }
                Spacer(Modifier.height(10.dp))
                Text(
                    "%.6f, %.6f".format(geo.latitude, geo.longitude),
                    style = MonoStyle,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Spacer(Modifier.height(10.dp))
                TextButton(onClick = { uriHandler.openUri(geo.mapsUrl) }) {
                    Text("Open in OpenStreetMap")
                }
            }

            geo.article?.let { a ->
                SectionLabel("About this place")
                Column(
                    Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(14.dp))
                        .background(MaterialTheme.colorScheme.surface)
                        .border(1.dp, t.border, RoundedCornerShape(14.dp))
                        .padding(14.dp),
                ) {
                    Text(a.title, style = MaterialTheme.typography.titleMedium)
                    a.description?.let {
                        Text(it, style = MaterialTheme.typography.bodySmall, color = t.textMute)
                    }
                    a.extract?.let {
                        Spacer(Modifier.height(8.dp))
                        Text(it, style = MaterialTheme.typography.bodySmall, color = t.textDim, maxLines = 6)
                    }
                    a.url?.let {
                        Spacer(Modifier.height(6.dp))
                        TextButton(onClick = { uriHandler.openUri(it) }) { Text("Read on Wikipedia") }
                    }
                }
            }

            if (geo.nearby.isNotEmpty()) {
                SectionLabel("Nearby · ${geo.nearby.size}")
                DataList(geo.nearby.map { it.title to "${it.distanceM.toInt()} m" })
            }
        }
    }

    // ── Camera ────────────────────────────────────────────────────
    if (r.exif.present) {
        SectionLabel("Camera")
        DataList(
            listOfNotNull(
                r.exif.make?.let { "Make" to it },
                r.exif.model?.let { "Model" to it },
                r.exif.lens?.let { "Lens" to it },
                r.exif.serial?.let { "Body serial" to it },
                r.exif.software?.let { "Software" to it },
                r.exif.capturedAt?.let { "Captured" to it },
                r.exif.iso?.let { "ISO" to it },
                r.exif.aperture?.let { "Aperture" to it },
                r.exif.exposure?.let { "Exposure" to it },
            ).ifEmpty { listOf("Camera" to "No camera tags") }
        )
    }

    // ── Signals ───────────────────────────────────────────────────
    if (r.signals.isNotEmpty()) {
        SectionLabel("What this tells us")
        r.signals.forEach { sig ->
            val c = when (sig.weight) {
                "high" -> t.info
                "medium" -> t.warn
                else -> t.textMute
            }
            Column(
                Modifier
                    .fillMaxWidth()
                    .padding(vertical = 5.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(MaterialTheme.colorScheme.surface)
                    .border(1.dp, t.border, RoundedCornerShape(12.dp))
                    .padding(13.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        Modifier
                            .size(7.dp)
                            .clip(RoundedCornerShape(99.dp))
                            .background(c),
                    )
                    Spacer(Modifier.width(9.dp))
                    Text(sig.label, style = MaterialTheme.typography.titleMedium)
                }
                Spacer(Modifier.height(5.dp))
                Text(sig.detail, style = MaterialTheme.typography.bodySmall, color = t.textDim)
            }
        }
    }

    // ── File ──────────────────────────────────────────────────────
    SectionLabel("File")
    DataList(
        listOfNotNull(
            r.file.name?.let { "Name" to it },
            "Type" to (r.file.mime ?: "unknown"),
            "Dimensions" to "${r.file.width} x ${r.file.height} (%.1f MP)".format(r.file.megapixels),
            "Size" to "%.2f MB".format(r.file.sizeBytes / 1e6),
            "SHA-256" to r.file.sha256,
        )
    )

    SectionLabel("Perceptual hashes")
    DataList(
        listOf(
            "aHash" to r.hashes.ahash,
            "dHash" to r.hashes.dhash,
            "pHash" to r.hashes.phash,
        )
    )
    Spacer(Modifier.height(8.dp))
    Text(
        "These survive re-compression and resizing, so the same photo re-uploaded elsewhere " +
            "produces near-identical values. Two images within about 10 differing bits are " +
            "very likely the same picture.",
        style = MaterialTheme.typography.bodySmall,
        color = t.textMute,
    )

    Spacer(Modifier.height(20.dp))
    // Gated: the report on screen was free, and this is the next one.
    AdActionButton(
        gate = gate,
        label = "Analyse another photo",
        onClick = onPick,
        modifier = Modifier.fillMaxWidth(),
    )
}
