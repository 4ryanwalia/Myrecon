package com.aryan.myrecon.ui.screens

import android.app.Activity
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.compose.ui.platform.LocalContext
import com.aryan.myrecon.ads.RewardedAdManager
import com.aryan.myrecon.data.*
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.components.*
import com.aryan.myrecon.ui.pressScale
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.Mono
import com.aryan.myrecon.ui.theme.MonoStyle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LookupScreen(vm: LookupViewModel = viewModel()) {
    val tool by vm.tool.collectAsState()
    val query by vm.query.collectAsState()
    val state by vm.state.collectAsState()
    val t = LocalReconTokens.current
    val keyboard = LocalSoftwareKeyboardController.current
    val haptics = LocalHaptics.current
    val context = LocalContext.current
    // One manager per screen; it caches a loaded ad between offers.
    val rewarded = remember(context) { RewardedAdManager(context.applicationContext) }

    // Separate unit, separate manager: this one gates running a lookup, the one
    // above reveals results already found.
    val adGate = rememberActionAdGate()

    // Reset for every new result, so each scan is its own unlock rather than
    // one ad buying every future search.
    var resultsUnlocked by remember { mutableStateOf(false) }
    LaunchedEffect(state) {
        if (state is LookupState.Running) resultsUnlocked = false
    }

    // The scan's physical soundtrack: a tick as each account lands, one firmer
    // thump when the sweep resolves. Keyed on the values themselves so a
    // recomposition for any other reason does not re-fire them.
    val running = state as? LookupState.Running
    LaunchedEffect(running?.found) {
        if ((running?.found ?: 0) > 0) haptics.found()
    }
    LaunchedEffect(state::class, (state as? LookupState.Done)?.result) {
        when (state) {
            is LookupState.Done -> haptics.complete()
            is LookupState.Failed -> haptics.error()
            else -> Unit
        }
    }

    val scroll = rememberScrollState()

    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        // Instrument ground: ruled grid, one pool of light, a slow sweep. The
        // sweep stops once results are on screen — ambient motion under data
        // someone is reading is a distraction, not atmosphere.
        GridBackdrop(sweep = state !is LookupState.Done)

        Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(scroll)
                .padding(horizontal = 16.dp)
                .padding(bottom = 40.dp),
        ) {
        Spacer(Modifier.height(12.dp))

        // ── tool selector ────────────────────────────────────────
        // A 3x2 grid rather than a horizontal strip: six tools would not fit
        // across a phone, so the strip clipped the last two off-screen with no
        // affordance that they existed. A grid shows every option at once and
        // gives each a target comfortably above the 48dp minimum.
        ToolGrid(selected = tool, onSelect = vm::selectTool)

        Spacer(Modifier.height(14.dp))
        Text(tool.hint, style = MaterialTheme.typography.bodySmall, color = t.textMute)
        Spacer(Modifier.height(8.dp))
        RunsBadge(tool.runs)
        Spacer(Modifier.height(12.dp))

        // ── query field ──────────────────────────────────────────
        OutlinedTextField(
            value = query,
            onValueChange = vm::setQuery,
            // A prompt marker, so the field reads as a command line rather than
            // a web form input.
            leadingIcon = {
                Text(
                    "›",
                    fontFamily = Mono,
                    color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.titleLarge,
                )
            },
            placeholder = { Text(tool.placeholder, style = MonoStyle, color = t.textMute) },
            singleLine = true,
            shape = RoundedCornerShape(3.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = MaterialTheme.colorScheme.primary,
                unfocusedBorderColor = t.border,
                focusedContainerColor = MaterialTheme.colorScheme.surface,
                unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                cursorColor = MaterialTheme.colorScheme.primary,
            ),
            textStyle = MonoStyle.copy(color = MaterialTheme.colorScheme.onSurface),
            keyboardOptions = KeyboardOptions(
                // Autocapitalising a handle or a domain produces a value that
                // silently fails to match, so it is off for every lookup.
                capitalization = KeyboardCapitalization.None,
                autoCorrectEnabled = false,
                imeAction = ImeAction.Search,
            ),
            // Routed through the gate as well. The keyboard's search key is the
            // same action as the button and must not be a way around it — but
            // it carries no marker, so it only plays an ad once the button has
            // already advertised one.
            keyboardActions = KeyboardActions(
                onSearch = {
                    keyboard?.hide()
                    adGate.run(
                        activity = context as? Activity,
                        onEarned = { haptics.complete() },
                        action = { vm.run() },
                    )
                },
            ),
            modifier = Modifier.fillMaxWidth(),
        )

        Spacer(Modifier.height(10.dp))

        Row(verticalAlignment = Alignment.CenterVertically) {
            Spacer(Modifier.weight(1f))
            val running = state is LookupState.Running
            Button(
                // Every lookup goes through the gate — one button serves all
                // six tools. Cancelling never does: charging someone an ad to
                // stop something they already started is not a trade.
                onClick = {
                    keyboard?.hide()
                    if (running) {
                        vm.cancel()
                    } else {
                        haptics.tap()
                        adGate.run(
                            activity = context as? Activity,
                            onEarned = { haptics.complete() },
                            action = { vm.run() },
                        )
                    }
                },
                enabled = (running || query.isNotBlank()) && !adGate.showing,
                shape = RoundedCornerShape(11.dp),
                colors = if (running) {
                    ButtonDefaults.buttonColors(containerColor = t.surface2, contentColor = t.textDim)
                } else ButtonDefaults.buttonColors(),
            ) {
                // The marker only appears when an ad is genuinely loaded, so
                // the button never promises a video it cannot play — and never
                // plays one it did not advertise.
                AdMarker(visible = !running && adGate.willShowAd)
                Text(
                    when {
                        running -> "Cancel"
                        adGate.showing -> "Loading…"
                        else -> "Investigate"
                    }
                )
            }
        }
        if (state !is LookupState.Running) {
            Row {
                Spacer(Modifier.weight(1f))
                AdGateHint(adGate)
            }
        }

        Spacer(Modifier.height(16.dp))

        when (val s = state) {
            is LookupState.Idle -> StatePanel(
                "Ready",
                "Pick a lookup, enter a target, and MyRecon will check public sources and " +
                    "show what it found — with the evidence behind every result.",
            )

            // The radar only makes sense when there is a population to sweep.
            // Other lookups are one request and get the plain console.
            is LookupState.Running ->
                if (s.total > 0) {
                    Column(Modifier.fillMaxWidth()) {
                        Spacer(Modifier.height(10.dp))
                        RadarScan(
                            progress = s.checked.toFloat() / s.total,
                            found = s.found,
                            checked = s.checked,
                            total = s.total,
                            currentTarget = s.detail,
                        )
                        Spacer(Modifier.height(18.dp))
                        ScanConsole(s)
                    }
                } else {
                    ScanConsole(s)
                }

            is LookupState.Failed -> StatePanel("Lookup failed", s.message, tint = t.danger)

            is LookupState.Done -> when (val r = s.result) {
                is SweepResult -> SweepView(
                    s = r,
                    unlocked = resultsUnlocked,
                    offer = { hidden ->
                        UnlockResultsOffer(
                            manager = rewarded,
                            hiddenCount = hidden,
                            onGranted = { resultsUnlocked = true },
                            // Declining leaves the preview as-is. The offer
                            // stays available rather than vanishing, so it is a
                            // deferral rather than a one-shot the user can lose
                            // by mistapping.
                            onDeclined = { },
                        )
                    },
                )
                is UsernameResult -> UsernameView(r)
                is EmailResult -> EmailView(r)
                is DomainResult -> DomainView(r)
                is DnsIntel.Report -> DnsReportView(r)
                is DnsResult -> DnsView(r)
                is IpResult -> IpView(r)
                is DeepSearch.Result -> DeepSearchView(r)
                else -> StatePanel("Unsupported result", "Nothing to display.")
            }
        }
        }
    }
}

/**
 * Tool picker.
 *
 * Each cell carries an icon, the name, and a dot marking whether it runs on the
 * device — so the choice and its privacy implication are visible together
 * rather than the latter only appearing after selection.
 */
@Composable
private fun ToolGrid(selected: Tool, onSelect: (Tool) -> Unit) {
    val t = LocalReconTokens.current
    val haptics = LocalHaptics.current
    val rows = Tool.entries.chunked(3)

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        rows.forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                row.forEach { item ->
                    val isSel = item == selected
                    val bg by animateColorAsState(
                        if (isSel) MaterialTheme.colorScheme.primary.copy(alpha = 0.14f)
                        else MaterialTheme.colorScheme.surface,
                        label = "toolBg",
                    )
                    val edge by animateColorAsState(
                        if (isSel) MaterialTheme.colorScheme.primary else t.border,
                        label = "toolEdge",
                    )
                    val source = remember { MutableInteractionSource() }
                    val accent = MaterialTheme.colorScheme.primary
                    val lift by animateFloatAsState(
                        if (isSel) 1f else 0f,
                        spring(dampingRatio = 0.7f, stiffness = Spring.StiffnessLow),
                        label = "toolLift",
                    )
                    // Selected cells wear brackets and emit; unselected are a
                    // plain hairline. Registration marks rather than cards.
                    val frame = lerp(t.border, accent, lift)
                    Column(
                        Modifier
                            .weight(1f)
                            .heightIn(min = 80.dp)
                            .pressScale(source)
                            .then(if (isSel) Modifier.glow(accent, 20.dp, 0.20f * lift) else Modifier)
                            .clip(RoundedCornerShape(3.dp))
                            .background(if (isSel) t.surface2 else MaterialTheme.colorScheme.surface)
                            .bracketFrame(frame, armLength = 11.dp, stroke = if (isSel) 1.6.dp else 1.dp)
                            .clickable(interactionSource = source, indication = null) {
                                haptics.tap()
                                onSelect(item)
                            }
                            .padding(vertical = 13.dp, horizontal = 6.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center,
                    ) {
                        Icon(
                            item.icon,
                            contentDescription = null,
                            tint = lerp(t.textMute, accent, lift),
                            modifier = Modifier.size(20.dp),
                        )
                        Spacer(Modifier.height(7.dp))
                        Text(
                            item.label.uppercase(),
                            fontFamily = Mono,
                            style = MaterialTheme.typography.labelSmall,
                            color = lerp(t.textDim, MaterialTheme.colorScheme.onSurface, lift),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Spacer(Modifier.height(6.dp))
                        val dot = if (item.runs == Runs.OnDevice) t.ok else t.info
                        Box(
                            Modifier
                                .size(width = 14.dp, height = 2.dp)
                                .then(if (isSel) Modifier.glow(dot, 5.dp, 0.55f) else Modifier)
                                .background(dot.copy(alpha = if (isSel) 1f else 0.55f)),
                        )
                    }
                }
                // Keep the last row aligned when it is not full.
                repeat(3 - row.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

/**
 * Says where the lookup runs.
 *
 * "Nothing left your phone" is a claim worth making only if the app is
 * specific about when it holds — so the badge names the actual sources for
 * on-device lookups, and admits the server for the ones that need it.
 */
@Composable
private fun RunsBadge(runs: Runs) {
    val t = LocalReconTokens.current
    val onDevice = runs == Runs.OnDevice
    val tint = if (onDevice) t.ok else t.info
    Row(
        Modifier
            .clip(RoundedCornerShape(7.dp))
            .background(tint.copy(alpha = 0.10f))
            .border(1.dp, tint.copy(alpha = 0.35f), RoundedCornerShape(7.dp))
            .padding(horizontal = 9.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .size(6.dp)
                .clip(RoundedCornerShape(99.dp))
                .background(tint),
        )
        Spacer(Modifier.width(7.dp))
        Text(
            if (onDevice) "Runs on this device · public sources, no MyRecon server"
            else "Runs on the MyRecon server",
            style = MaterialTheme.typography.labelSmall,
            color = tint,
        )
    }
}

/**
 * Live scan telemetry.
 *
 * Watching the sweep work is the difference between a 20-second wait feeling
 * like progress and feeling like a hang, so the per-platform detail is shown
 * rather than a spinner.
 */
@Composable
private fun ScanConsole(s: LookupState.Running) {
    val t = LocalReconTokens.current
    val pct by animateFloatAsState(s.percent / 100f, label = "scanProgress")

    val accent = MaterialTheme.colorScheme.primary
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(3.dp))
            .background(t.bgSoft)
            .bracketFrame(accent.copy(alpha = 0.7f)),
    ) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            PulsingDot()
            Spacer(Modifier.width(10.dp))
            Text(
                s.phase.uppercase(),
                fontFamily = Mono,
                style = MaterialTheme.typography.labelSmall,
                color = accent,
                modifier = Modifier.weight(1f),
                maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
            Text("${s.percent}%".padStart(4), style = MonoStyle, color = t.textDim)
        }

        LinearProgressIndicator(
            progress = { pct },
            modifier = Modifier.fillMaxWidth().height(2.dp),
            color = accent,
            trackColor = t.surface2,
            drawStopIndicator = {},
        )

        // Reads as a log: newest at the top, older lines fading out, so the
        // eye stays on the current line without the list feeling truncated.
        Column(Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
            s.log.take(10).forEachIndexed { i, line ->
                val fade = 1f - (i * 0.085f)
                TerminalLine(
                    text = line,
                    prefix = if (i == 0) "›" else " ",
                    colour = t.textDim.copy(alpha = fade.coerceAtLeast(0.25f)),
                )
            }
        }
    }
}

@Composable
private fun PulsingDot() {
    val transition = rememberInfiniteTransition(label = "pulse")
    val alpha by transition.animateFloat(
        initialValue = 1f,
        targetValue = 0.3f,
        animationSpec = infiniteRepeatable(tween(700), RepeatMode.Reverse),
        label = "pulseAlpha",
    )
    Box(
        Modifier
            .size(8.dp)
            .clip(RoundedCornerShape(99.dp))
            .background(MaterialTheme.colorScheme.primary.copy(alpha = alpha)),
    )
}
