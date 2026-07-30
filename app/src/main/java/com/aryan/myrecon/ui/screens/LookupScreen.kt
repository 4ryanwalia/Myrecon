package com.aryan.myrecon.ui.screens

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.*
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
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.aryan.myrecon.data.*
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.components.*
import com.aryan.myrecon.ui.pressScale
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.MonoStyle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LookupScreen(vm: LookupViewModel = viewModel()) {
    val tool by vm.tool.collectAsState()
    val query by vm.query.collectAsState()
    val deep by vm.deep.collectAsState()
    val state by vm.state.collectAsState()
    val t = LocalReconTokens.current
    val keyboard = LocalSoftwareKeyboardController.current
    val haptics = LocalHaptics.current

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

    Column(
        Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .verticalScroll(rememberScrollState())
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
            placeholder = { Text(tool.placeholder, style = MonoStyle, color = t.textMute) },
            singleLine = true,
            textStyle = MonoStyle.copy(color = MaterialTheme.colorScheme.onSurface),
            keyboardOptions = KeyboardOptions(
                // Autocapitalising a handle or a domain produces a value that
                // silently fails to match, so it is off for every lookup.
                capitalization = KeyboardCapitalization.None,
                autoCorrectEnabled = false,
                imeAction = ImeAction.Search,
            ),
            keyboardActions = KeyboardActions(onSearch = { keyboard?.hide(); vm.run() }),
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth(),
        )

        Spacer(Modifier.height(10.dp))

        Row(verticalAlignment = Alignment.CenterVertically) {
            if (tool.streams) {
                Switch(checked = deep, onCheckedChange = { vm.toggleDeep() })
                Spacer(Modifier.width(8.dp))
                Text("Deep sweep", style = MaterialTheme.typography.bodySmall, color = t.textDim)
            }
            Spacer(Modifier.weight(1f))
            val running = state is LookupState.Running
            Button(
                onClick = { keyboard?.hide(); if (running) vm.cancel() else vm.run() },
                enabled = running || query.isNotBlank(),
                shape = RoundedCornerShape(11.dp),
                colors = if (running) {
                    ButtonDefaults.buttonColors(containerColor = t.surface2, contentColor = t.textDim)
                } else ButtonDefaults.buttonColors(),
            ) {
                Text(if (running) "Cancel" else "Investigate")
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
                is SweepResult -> SweepView(r)
                is UsernameResult -> UsernameView(r)
                is EmailResult -> EmailView(r)
                is DomainResult -> DomainView(r)
                is DnsResult -> DnsView(r)
                is IpResult -> IpView(r)
                is InvestigationResult -> InvestigationView(r)
                else -> StatePanel("Unsupported result", "Nothing to display.")
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
                    Column(
                        Modifier
                            .weight(1f)
                            .heightIn(min = 74.dp)
                            .pressScale(source)
                            .clip(RoundedCornerShape(13.dp))
                            .background(bg)
                            .border(if (isSel) 1.5.dp else 1.dp, edge, RoundedCornerShape(13.dp))
                            .clickable(interactionSource = source, indication = null) {
                                haptics.tap()
                                onSelect(item)
                            }
                            .padding(vertical = 11.dp, horizontal = 8.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center,
                    ) {
                        Icon(
                            item.icon,
                            contentDescription = null,
                            tint = if (isSel) MaterialTheme.colorScheme.primary else t.textMute,
                            modifier = Modifier.size(20.dp),
                        )
                        Spacer(Modifier.height(6.dp))
                        Text(
                            item.label,
                            style = MaterialTheme.typography.labelLarge,
                            color = if (isSel) MaterialTheme.colorScheme.onSurface else t.textDim,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Spacer(Modifier.height(4.dp))
                        Box(
                            Modifier
                                .size(5.dp)
                                .clip(RoundedCornerShape(99.dp))
                                .background(if (item.runs == Runs.OnDevice) t.ok else t.info),
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

    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(t.bgSoft)
            .border(1.dp, t.border, RoundedCornerShape(14.dp)),
    ) {
        Row(
            Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surface)
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            PulsingDot()
            Spacer(Modifier.width(10.dp))
            Text(
                s.phase,
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.weight(1f),
                maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
            Text("${s.percent}%", style = MonoStyle, color = t.textMute)
        }

        LinearProgressIndicator(
            progress = { pct },
            modifier = Modifier.fillMaxWidth().height(2.dp),
            color = MaterialTheme.colorScheme.primary,
            trackColor = t.surface2,
            drawStopIndicator = {},
        )

        Column(Modifier.padding(vertical = 4.dp)) {
            s.log.take(12).forEach { line ->
                Text(
                    line,
                    style = MonoStyle,
                    color = t.textDim,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp, vertical = 4.dp),
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
