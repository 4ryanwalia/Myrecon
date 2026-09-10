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
import com.aryan.myrecon.data.CleanCopy
import com.aryan.myrecon.data.GeoIntel
import com.aryan.myrecon.data.ImageProvenance
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

/** The clean-copy action, which is separate from the report it sits under. */
sealed interface CleanState {
    data object Idle : CleanState
    data object Saving : CleanState
    data class Saved(val result: CleanCopy.Saved) : CleanState
    data class Failed(val message: String) : CleanState
}

class ImageViewModel : ViewModel() {
    private val _state = MutableStateFlow<ImageState>(ImageState.Empty)
    val state = _state.asStateFlow()

    private val _clean = MutableStateFlow<CleanState>(CleanState.Idle)
    val clean = _clean.asStateFlow()

    fun saveClean(context: android.content.Context, uri: Uri) {
        if (_clean.value is CleanState.Saving) return
        viewModelScope.launch {
            _clean.value = CleanState.Saving
            _clean.value = CleanCopy.save(context, uri).fold(
                onSuccess = { CleanState.Saved(it) },
                onFailure = { CleanState.Failed(it.message ?: "The copy could not be saved.") },
            )
        }
    }

    fun analyse(context: android.content.Context, uri: Uri) {
        viewModelScope.launch {
            _state.value = ImageState.Working
            // A saved-copy confirmation belongs to the photo it was made from.
            _clean.value = CleanState.Idle
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

    fun reset() {
        _state.value = ImageState.Empty
        _clean.value = CleanState.Idle
    }
}

@Composable
fun ImageScreen(vm: ImageViewModel = viewModel()) {
    val context = LocalContext.current
    val state by vm.state.collectAsState()
    val clean by vm.clean.collectAsState()
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
                Text("What's hidden in a photo", style = MaterialTheme.typography.headlineSmall)
                Spacer(Modifier.height(8.dp))
                Text(
                    "Every photo carries hidden details you cannot see by looking at it: the " +
                        "phone or camera that took it, the date, sometimes the exact spot on a " +
                        "map, and whether an AI made it. Pick a photo and MyRecon will show you " +
                        "what is in there — and offer to strip it out before you share it.\n\n" +
                        "It all happens on your phone. The photo is never sent anywhere.",
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
                    Text("Reading the photo…", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "Checking the hidden details, then looking up any location",
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

            is ImageState.Done -> ForensicsReport(
                s,
                onPick = ::pick,
                gate = adGate,
                clean = clean,
                onClean = { vm.saveClean(context, s.uri) },
            )
        }
    }
}

/**
 * What the file says about where it came from.
 *
 * Prominent only when there is something to say. A card reading "no AI marker
 * found" on every holiday photo would be noise, and worse, it would read as a
 * clean bill of health — which is exactly the claim the data cannot support.
 * When nothing is declared the answer is a quiet line that says so and says why
 * it proves nothing.
 */
@Composable
private fun OriginCard(p: ImageProvenance.Report) {
    val t = LocalReconTokens.current
    val declared = p.origin != ImageProvenance.Origin.Undeclared || p.contentCredentials

    if (!declared) {
        SectionLabel("Was this made by AI?")
        Column(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(14.dp))
                .background(MaterialTheme.colorScheme.surface)
                .border(1.dp, t.border, RoundedCornerShape(14.dp))
                .padding(14.dp),
        ) {
            Text("This photo does not say", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(5.dp))
            Text(
                "AI tools usually hide a small label inside the picture saying they made " +
                    "it. This one has no label.\n\n" +
                    "That does not mean it is real. The label is wiped whenever a picture " +
                    "is screenshotted, saved again, or posted on social media — so most " +
                    "genuine photos you see online have no label either.",
                style = MaterialTheme.typography.bodySmall,
                color = t.textDim,
            )
        }
        return
    }

    val (headline, tint) = when (p.origin) {
        ImageProvenance.Origin.DeclaredAiGenerated ->
            "Yes — the photo says so itself" to t.warn
        ImageProvenance.Origin.DeclaredAiEdited ->
            "Partly — AI was used on some of it" to t.warn
        ImageProvenance.Origin.DeclaredCapture ->
            "No — it says a camera took it" to t.ok
        ImageProvenance.Origin.Undeclared ->
            "It carries a record of how it was made" to t.info
    }

    SectionLabel("Was this made by AI?")
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(tint.copy(alpha = 0.10f))
            .border(1.dp, tint.copy(alpha = 0.4f), RoundedCornerShape(14.dp))
            .padding(16.dp),
    ) {
        Text(headline, style = MaterialTheme.typography.titleLarge, color = tint)
        p.generator?.let {
            Spacer(Modifier.height(4.dp))
            Text(it, style = MaterialTheme.typography.titleMedium)
        }

        Spacer(Modifier.height(10.dp))
        Text(
            "This comes from a hidden label inside the file. MyRecon is reading what the " +
                "photo says about itself — it is not guessing by looking at the picture.",
            style = MaterialTheme.typography.bodySmall,
            color = t.textDim,
        )

        if (p.markers.isNotEmpty()) {
            Spacer(Modifier.height(10.dp))
            DataList(p.markers.map { it.source to it.value })
        }

        if (p.contentCredentials) {
            Spacer(Modifier.height(10.dp))
            Text(
                // Presence is provable from the bytes; validity is not, and
                // saying "verified" here would be a claim this app cannot make.
                "This photo carries Content Credentials — a record of how it was made, " +
                    "added by the camera or app. MyRecon can see the record is there, but " +
                    "cannot check whether it is genuine, so treat it as a claim rather " +
                    "than proof.",
                style = MaterialTheme.typography.bodySmall,
                color = t.textMute,
            )
        }

        p.prompt?.let { prompt ->
            Spacer(Modifier.height(12.dp))
            Text("The words used to make it", style = MaterialTheme.typography.titleSmall)
            Spacer(Modifier.height(5.dp))
            Text(
                prompt,
                style = MonoStyle,
                color = t.textDim,
            )
        }
    }
}

/**
 * The report turned round to face the person holding the phone.
 *
 * Everything above answers "what is this file". This answers "what does it say
 * about me", and pairs it with the only action on this screen — because a list
 * of things your photo leaks, with nothing to do about it, is just anxiety.
 */
@Composable
private fun ExposureSection(
    r: ImageForensics.Report,
    clean: CleanState,
    onClean: () -> Unit,
) {
    val t = LocalReconTokens.current
    if (r.leaks.isEmpty() && !r.cleanCopy.supported) return

    SectionLabel("What this photo gives away")

    if (r.leaks.isEmpty()) {
        Text(
            "Nothing identifying was found in this file. There is no location, no timestamp " +
                "and no camera identity to remove.",
            style = MaterialTheme.typography.bodySmall,
            color = t.textDim,
        )
    }

    r.leaks.forEach { leak ->
        val c = when (leak.severity) {
            "high" -> t.danger
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
                Text(leak.what, style = MaterialTheme.typography.titleMedium)
            }
            Spacer(Modifier.height(5.dp))
            Text(leak.detail, style = MaterialTheme.typography.bodySmall, color = t.textDim)
        }
    }

    Spacer(Modifier.height(14.dp))

    when (val c = clean) {
        is CleanState.Saved -> {
            Column(
                Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(14.dp))
                    .background(t.ok.copy(alpha = 0.10f))
                    .border(1.dp, t.ok.copy(alpha = 0.4f), RoundedCornerShape(14.dp))
                    .padding(15.dp),
            ) {
                Text("Clean copy saved", style = MaterialTheme.typography.titleMedium, color = t.ok)
                Spacer(Modifier.height(5.dp))
                Text(
                    "Pictures › MyRecon › ${c.result.displayName}",
                    style = MonoStyle,
                    color = t.textDim,
                )
                if (c.result.removed.isNotEmpty()) {
                    Spacer(Modifier.height(9.dp))
                    DataList(c.result.removed.map { "Removed" to it })
                }
                Spacer(Modifier.height(9.dp))
                Text(
                    if (c.result.recompressed) {
                        "This format could not be edited in place, so the copy was re-encoded " +
                            "as a JPEG. The picture is very slightly recompressed."
                    } else {
                        "The picture itself is untouched — only the metadata blocks were " +
                            "removed, so there is no quality loss."
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = t.textMute,
                )
            }
        }

        is CleanState.Failed -> StatePanel("Could not save a clean copy", c.message, tint = t.danger)

        else -> {
            Button(
                onClick = onClean,
                enabled = c !is CleanState.Saving,
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (c is CleanState.Saving) {
                    CircularProgressIndicator(
                        strokeWidth = 2.dp,
                        modifier = Modifier.size(16.dp),
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                    Spacer(Modifier.width(10.dp))
                    Text("Saving…")
                } else {
                    Text("Save a clean copy")
                }
            }
            Spacer(Modifier.height(8.dp))
            Text(
                if (r.cleanCopy.supported) {
                    "Writes a stripped copy to your gallery, ready to share. " +
                        "Removes ${r.cleanCopy.removes.joinToString(", ").ifBlank { "any metadata" }}" +
                        (if (r.cleanCopy.bytesSaved > 0)
                            " · %.0f KB smaller".format(r.cleanCopy.bytesSaved / 1024.0)
                        else "") +
                        ". The original is left exactly as it is."
                } else {
                    "This format cannot be edited in place, so the copy will be re-encoded as " +
                        "a JPEG. That removes everything, at the cost of a slight recompression."
                },
                style = MaterialTheme.typography.bodySmall,
                color = t.textMute,
            )
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
    clean: CleanState,
    onClean: () -> Unit,
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

    OriginCard(r.provenance)

    // ── Location leads: it is the finding people care about most ──
    s.geo?.let { geo ->
        if (geo.place.found) {
            SectionLabel("Where this photo was taken")
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
        SectionLabel("The camera that took it")
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
        SectionLabel("What this tells you")
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

    // ── What it gives away, and the fix ───────────────────────────
    ExposureSection(r, clean, onClean)

    // ── File ──────────────────────────────────────────────────────
    SectionLabel("About the file")
    DataList(
        listOfNotNull(
            r.file.name?.let { "Name" to it },
            "Type" to (r.file.mime ?: "unknown"),
            "Dimensions" to "${r.file.width} x ${r.file.height} (%.1f MP)".format(r.file.megapixels),
            "Size" to "%.2f MB".format(r.file.sizeBytes / 1e6),
            "Exact fingerprint" to r.file.sha256,
        )
    )

    SectionLabel("Picture fingerprint")
    DataList(
        listOf(
            "Fingerprint 1" to r.hashes.ahash,
            "Fingerprint 2" to r.hashes.dhash,
            "Fingerprint 3" to r.hashes.phash,
        )
    )
    Spacer(Modifier.height(8.dp))
    Text(
        "Three short codes worked out from what the picture looks like. Unlike the exact " +
            "fingerprint above, these barely change when a photo is resized or re-saved — so " +
            "the same picture posted somewhere else still produces almost the same codes. " +
            "That is how you tell a copy of a photo from a different photo.",
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
