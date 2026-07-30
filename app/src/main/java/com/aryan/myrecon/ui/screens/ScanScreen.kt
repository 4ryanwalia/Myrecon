package com.aryan.myrecon.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.annotation.OptIn
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.*
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.aryan.myrecon.data.LinkSafety
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.components.DataList
import com.aryan.myrecon.ui.components.SectionLabel
import com.aryan.myrecon.ui.components.StatePanel
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.MonoStyle
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.concurrent.Executors

sealed interface ScanState {
    data object Scanning : ScanState
    data object Analysing : ScanState
    data class Result(val report: LinkSafety.Report) : ScanState
}

class ScanViewModel : ViewModel() {
    private val _state = MutableStateFlow<ScanState>(ScanState.Scanning)
    val state = _state.asStateFlow()

    /** Guards against the analyser firing repeatedly while the code stays in frame. */
    private var busy = false

    fun onCode(raw: String) {
        if (busy || _state.value !is ScanState.Scanning) return
        busy = true
        viewModelScope.launch {
            _state.value = ScanState.Analysing
            val report = runCatching { LinkSafety.analyse(raw) }.getOrElse {
                LinkSafety.Report(
                    scanned = raw, finalUrl = null, host = null, redirectChain = emptyList(),
                    registered = null, ageDays = null, registrar = null,
                    signals = emptyList(), riskScore = 0,
                    verdict = LinkSafety.Verdict.Unknown, kind = LinkSafety.Kind.PlainText,
                    error = it.message,
                )
            }
            _state.value = ScanState.Result(report)
            busy = false
        }
    }

    fun rescan() {
        busy = false
        _state.value = ScanState.Scanning
    }
}

@Composable
fun ScanScreen(vm: ScanViewModel = viewModel()) {
    val context = LocalContext.current
    val state by vm.state.collectAsState()
    val haptics = LocalHaptics.current

    var granted by remember {
        mutableStateOf(
            context.checkSelfPermission(Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED
        )
    }
    val ask = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        granted = it
    }

    LaunchedEffect(state) {
        if (state is ScanState.Result) haptics.complete()
    }

    when {
        !granted -> CameraRationale { ask.launch(Manifest.permission.CAMERA) }
        state is ScanState.Result -> ScanResult((state as ScanState.Result).report) { vm.rescan() }
        else -> CameraViewfinder(
            analysing = state is ScanState.Analysing,
            onCode = { haptics.found(); vm.onCode(it) },
        )
    }
}

/**
 * Permission rationale.
 *
 * This is the app's first runtime prompt, so it explains what the camera is for
 * and — just as importantly — what it is not for, before the system dialog
 * appears. A bare prompt on a security tool invites a refusal.
 */
@Composable
private fun CameraRationale(onRequest: () -> Unit) {
    val t = LocalReconTokens.current
    Column(
        Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Scan a QR code", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(10.dp))
        Text(
            "MyRecon reads the code on your device and shows where the link actually goes " +
                "before you open it — including how recently the domain was registered, which " +
                "is the clearest sign of a scam.",
            style = MaterialTheme.typography.bodyMedium,
            color = t.textDim,
        )
        Spacer(Modifier.height(12.dp))
        Text(
            "Frames are analysed in memory and never recorded, stored or uploaded.",
            style = MaterialTheme.typography.bodySmall,
            color = t.textMute,
        )
        Spacer(Modifier.height(22.dp))
        Button(onClick = onRequest, shape = RoundedCornerShape(11.dp)) {
            Text("Allow camera")
        }
    }
}

/** Live camera with a reticle and a sweeping scan line. */
@OptIn(ExperimentalGetImage::class)
@Composable
private fun CameraViewfinder(analysing: Boolean, onCode: (String) -> Unit) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val t = LocalReconTokens.current
    val accent = MaterialTheme.colorScheme.primary

    // One background thread for analysis; ML Kit must not run on the main thread.
    val executor = remember { Executors.newSingleThreadExecutor() }
    DisposableEffect(Unit) { onDispose { executor.shutdown() } }

    val scanner = remember {
        BarcodeScanning.getClient(
            com.google.mlkit.vision.barcode.BarcodeScannerOptions.Builder()
                .setBarcodeFormats(Barcode.FORMAT_QR_CODE, Barcode.FORMAT_DATA_MATRIX)
                .build()
        )
    }
    DisposableEffect(Unit) { onDispose { scanner.close() } }

    Box(Modifier.fillMaxSize().background(Color.Black)) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { ctx ->
                val previewView = PreviewView(ctx).apply {
                    scaleType = PreviewView.ScaleType.FILL_CENTER
                }
                val providerFuture = ProcessCameraProvider.getInstance(ctx)
                providerFuture.addListener({
                    val provider = providerFuture.get()
                    val preview = Preview.Builder().build()
                        .also { it.surfaceProvider = previewView.surfaceProvider }

                    val analysis = ImageAnalysis.Builder()
                        // Dropping stale frames keeps the preview smooth; a QR
                        // code sits in frame for many frames, so missing some
                        // costs nothing.
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .build()

                    analysis.setAnalyzer(executor) { proxy ->
                        val media = proxy.image
                        if (media == null) {
                            proxy.close()
                            return@setAnalyzer
                        }
                        val image = InputImage.fromMediaImage(
                            media, proxy.imageInfo.rotationDegrees
                        )
                        scanner.process(image)
                            .addOnSuccessListener { codes ->
                                codes.firstOrNull()?.rawValue?.let(onCode)
                            }
                            // proxy.close() must run whatever happens, or the
                            // pipeline stalls after a single frame.
                            .addOnCompleteListener { proxy.close() }
                    }

                    runCatching {
                        provider.unbindAll()
                        provider.bindToLifecycle(
                            lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis,
                        )
                    }
                }, androidx.core.content.ContextCompat.getMainExecutor(ctx))
                previewView
            },
        )

        Reticle(accent = accent, active = !analysing)

        Column(
            Modifier
                .align(Alignment.BottomCenter)
                .padding(28.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            if (analysing) {
                CircularProgressIndicator(color = accent, strokeWidth = 2.dp, modifier = Modifier.size(22.dp))
                Spacer(Modifier.height(10.dp))
            }
            Text(
                if (analysing) "Checking the destination…" else "Point at a QR code",
                style = MaterialTheme.typography.titleMedium,
                color = Color.White,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                "Decoded on this device",
                style = MaterialTheme.typography.bodySmall,
                color = Color.White.copy(alpha = 0.65f),
            )
        }
    }
}

/** Corner brackets plus a sweeping line — the visual language of scanning. */
@Composable
private fun Reticle(accent: Color, active: Boolean) {
    val sweep = rememberInfiniteTransition(label = "reticle")
    val y by sweep.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1800, easing = LinearEasing), RepeatMode.Reverse),
        label = "scanLine",
    )

    Canvas(Modifier.fillMaxSize()) {
        val box = size.minDimension * 0.68f
        val left = (size.width - box) / 2
        val top = (size.height - box) / 2.3f
        val arm = box * 0.13f
        val stroke = 3.dp.toPx()

        // Dim everything outside the reticle so the eye goes to the box.
        val shade = Color.Black.copy(alpha = 0.45f)
        drawRect(shade, size = Size(size.width, top))
        drawRect(shade, topLeft = Offset(0f, top + box), size = Size(size.width, size.height - top - box))
        drawRect(shade, topLeft = Offset(0f, top), size = Size(left, box))
        drawRect(shade, topLeft = Offset(left + box, top), size = Size(size.width - left - box, box))

        listOf(
            Offset(left, top) to listOf(Offset(arm, 0f), Offset(0f, arm)),
            Offset(left + box, top) to listOf(Offset(-arm, 0f), Offset(0f, arm)),
            Offset(left, top + box) to listOf(Offset(arm, 0f), Offset(0f, -arm)),
            Offset(left + box, top + box) to listOf(Offset(-arm, 0f), Offset(0f, -arm)),
        ).forEach { (corner, arms) ->
            arms.forEach { d ->
                drawLine(accent, corner, Offset(corner.x + d.x, corner.y + d.y), stroke, StrokeCap.Round)
            }
        }

        if (active) {
            val lineY = top + box * y
            drawLine(
                accent.copy(alpha = 0.85f),
                Offset(left + stroke, lineY),
                Offset(left + box - stroke, lineY),
                2f,
            )
        }
    }
}

/** The verdict. */
@Composable
private fun ScanResult(r: LinkSafety.Report, onRescan: () -> Unit) {
    val t = LocalReconTokens.current
    val tint = when (r.verdict) {
        LinkSafety.Verdict.Safe -> t.ok
        LinkSafety.Verdict.Caution -> t.warn
        LinkSafety.Verdict.Dangerous -> t.danger
        LinkSafety.Verdict.Unknown -> t.textMute
    }
    val headline = when (r.verdict) {
        LinkSafety.Verdict.Safe -> "Looks legitimate"
        LinkSafety.Verdict.Caution -> "Be careful"
        LinkSafety.Verdict.Dangerous -> "Do not open this"
        LinkSafety.Verdict.Unknown -> "Could not verify"
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        AnimatedVisibility(
            visible = true,
            enter = fadeIn(tween(260)) + slideInVertically(tween(300)) { it / 6 },
        ) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(16.dp))
                    .background(tint.copy(alpha = 0.12f))
                    .border(1.dp, tint.copy(alpha = 0.45f), RoundedCornerShape(16.dp))
                    .padding(18.dp),
            ) {
                Text(headline, style = MaterialTheme.typography.headlineSmall, color = tint)
                Spacer(Modifier.height(8.dp))
                Text(
                    r.host ?: r.scanned.take(90),
                    style = MonoStyle,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                if (r.kind == LinkSafety.Kind.Url && r.ageDays != null) {
                    Spacer(Modifier.height(10.dp))
                    Text(
                        "Domain registered ${r.registered} · ${r.ageDays} days old",
                        style = MaterialTheme.typography.bodySmall,
                        color = t.textDim,
                    )
                }
            }
        }

        if (r.signals.isNotEmpty()) {
            SectionLabel("Why")
            r.signals.forEach { s ->
                val c = if (s.weight < 0) t.ok else if (s.weight >= 30) t.danger else t.warn
                Column(
                    Modifier
                        .fillMaxWidth()
                        .padding(vertical = 6.dp)
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
                        Text(s.label, style = MaterialTheme.typography.titleMedium)
                    }
                    Spacer(Modifier.height(5.dp))
                    Text(s.detail, style = MaterialTheme.typography.bodySmall, color = t.textDim)
                }
            }
        }

        if (r.redirectChain.size > 1) {
            SectionLabel("Redirect chain · ${r.redirectChain.size} hops")
            DataList(r.redirectChain.mapIndexed { i, u -> "${i + 1}" to u })
        }

        SectionLabel("Raw content")
        DataList(
            listOfNotNull(
                "Type" to r.kind.name,
                r.finalUrl?.let { "Destination" to it },
                r.registrar?.let { "Registrar" to it },
                "Scanned" to r.scanned,
            )
        )

        Spacer(Modifier.height(18.dp))
        Button(
            onClick = onRescan,
            shape = RoundedCornerShape(11.dp),
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Scan another") }

        Spacer(Modifier.height(10.dp))
        Text(
            "MyRecon does not open links for you. If you trust this one, copy it deliberately.",
            style = MaterialTheme.typography.bodySmall,
            color = t.textMute,
        )
    }
}
