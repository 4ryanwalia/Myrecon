package com.aryan.myrecon.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.SubcomposeAsyncImage
import com.aryan.myrecon.data.BreachArticles
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.components.*
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.Mono
import com.aryan.myrecon.ui.theme.MonoStyle

/**
 * The Breach Files, read inside the app.
 *
 * The website generates these every six hours — severity, what each leaked
 * field means, the summary — and publishes the result as JSON. The app reads
 * that rather than re-deriving any of it, so the two can never disagree about
 * how bad something was.
 *
 * Tapping an entry opens a summary here rather than throwing the reader
 * straight at a browser. The feed carries enough to be genuinely useful on its
 * own, and the full write-up is one deliberate tap further on — which keeps the
 * reader in the app and still sends the traffic to the site when they want the
 * whole thing.
 */
@Composable
fun BreachesScreen() {
    var feed by remember { mutableStateOf<BreachArticles.Feed?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var selected by remember { mutableStateOf<BreachArticles.Article?>(null) }
    var reloads by remember { mutableStateOf(0) }

    LaunchedEffect(reloads) {
        error = null
        runCatching { BreachArticles.load(force = reloads > 0) }
            .onSuccess { feed = it }
            .onFailure { error = it.message ?: "Could not reach The Breach Files." }
    }

    val current = selected
    when {
        current != null -> ArticleDetail(current) { selected = null }
        error != null && feed == null -> LoadFailed(error!!) { reloads++ }
        feed == null -> Loading()
        else -> ArticleList(feed!!) { selected = it }
    }
}

/** Severity colour. Separate from `bandColor`, which maps confidence, not this. */
@Composable
private fun severityColour(band: String): Color {
    val t = LocalReconTokens.current
    return when (band.lowercase()) {
        "critical" -> t.danger
        "severe" -> t.warn
        "serious" -> MaterialTheme.colorScheme.primary
        else -> t.textDim
    }
}

private fun Long.compact(): String = when {
    this >= 1_000_000_000 -> "%.1fB".format(this / 1e9)
    this >= 1_000_000 -> "%.1fM".format(this / 1e6)
    this >= 1_000 -> "%.0fK".format(this / 1e3)
    else -> toString()
}

@Composable
private fun Loading() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator(strokeWidth = 2.dp)
    }
}

@Composable
private fun LoadFailed(message: String, onRetry: () -> Unit) {
    Column(
        Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        StatePanel("Not available", message)
        Spacer(Modifier.height(14.dp))
        Row {
            Spacer(Modifier.weight(1f))
            Button(onClick = onRetry, shape = RoundedCornerShape(11.dp)) { Text("Try again") }
            Spacer(Modifier.weight(1f))
        }
    }
}

@Composable
private fun ArticleList(
    feed: BreachArticles.Feed,
    onOpen: (BreachArticles.Article) -> Unit,
) {
    val t = LocalReconTokens.current
    val haptics = LocalHaptics.current

    // Lazy, unlike the lookup screen. This list grows every time the site
    // publishes, so composing all of it up front would get slower forever.
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            Column {
                Text("The Breach Files", style = MaterialTheme.typography.titleLarge)
                Spacer(Modifier.height(6.dp))
                Text(
                    "Who was hit, what was taken, and what it means for you. " +
                        "Updated from myrecon.xyz.",
                    style = MaterialTheme.typography.bodySmall,
                    color = t.textMute,
                )
                Spacer(Modifier.height(14.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Stat("Accounts exposed", feed.totalAccounts.compact(), Modifier.weight(1f))
                    Stat("Breaches", feed.breaches.size.toString(), Modifier.weight(1f))
                }
                Spacer(Modifier.height(6.dp))
            }
        }

        items(feed.breaches, key = { it.slug }) { a ->
            ReconCard(stripe = severityColour(a.band)) {
                Row(
                    Modifier.clickable { haptics.tap(); onOpen(a) },
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    if (a.logo != null) {
                        SubcomposeAsyncImage(
                            model = a.logo,
                            contentDescription = null,
                            contentScale = ContentScale.Fit,
                            modifier = Modifier
                                .size(42.dp)
                                .clip(RoundedCornerShape(9.dp))
                                .background(Color.White)
                                .padding(4.dp),
                            loading = { PlatformTile(a.title, "Social", size = 42) },
                            error = { PlatformTile(a.title, "Social", size = 42) },
                        )
                    } else {
                        PlatformTile(a.title, "Developer", size = 42)
                    }
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            a.title,
                            style = MaterialTheme.typography.titleSmall,
                            maxLines = 1, overflow = TextOverflow.Ellipsis,
                        )
                        Text(
                            "${a.accounts.compact()} accounts · ${a.breachDate}",
                            style = MonoStyle, color = t.textDim,
                            maxLines = 1, overflow = TextOverflow.Ellipsis,
                        )
                    }
                    Spacer(Modifier.width(8.dp))
                    Column(horizontalAlignment = Alignment.End) {
                        Text(
                            a.severity.toString(),
                            style = MaterialTheme.typography.titleMedium,
                            color = severityColour(a.band),
                        )
                        Text(
                            a.band.uppercase(),
                            fontFamily = Mono,
                            style = MaterialTheme.typography.labelSmall,
                            color = t.textMute,
                        )
                    }
                }
                if (a.dataClasses.isNotEmpty()) {
                    Spacer(Modifier.height(9.dp))
                    ChipRow(
                        a.dataClasses.take(4),
                        dangerPredicate = {
                            it.contains("Password", true) || it.contains("Credit", true) ||
                                it.contains("Government", true) || it.contains("Social security", true)
                        },
                    )
                }
            }
        }

        item {
            Spacer(Modifier.height(6.dp))
            DetailedReportOffer()
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun Stat(label: String, value: String, modifier: Modifier = Modifier) {
    val t = LocalReconTokens.current
    Column(
        modifier
            .clip(RoundedCornerShape(3.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, t.border, RoundedCornerShape(3.dp))
            .padding(vertical = 10.dp, horizontal = 12.dp),
    ) {
        Text(value, style = MaterialTheme.typography.titleMedium)
        Text(
            label.uppercase(),
            fontFamily = Mono,
            style = MaterialTheme.typography.labelSmall,
            color = t.textMute,
        )
    }
}

@Composable
private fun ArticleDetail(a: BreachArticles.Article, onBack: () -> Unit) {
    val t = LocalReconTokens.current
    val uri = LocalUriHandler.current
    val haptics = LocalHaptics.current
    val colour = severityColour(a.band)

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Row(
            Modifier.clickable { haptics.tap(); onBack() }.padding(vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                Icons.AutoMirrored.Filled.ArrowBack,
                contentDescription = "Back",
                tint = t.textDim,
                modifier = Modifier.size(18.dp),
            )
            Spacer(Modifier.width(8.dp))
            Text("The Breach Files", style = MaterialTheme.typography.bodySmall, color = t.textDim)
        }

        Spacer(Modifier.height(14.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (a.logo != null) {
                SubcomposeAsyncImage(
                    model = a.logo,
                    contentDescription = null,
                    contentScale = ContentScale.Fit,
                    modifier = Modifier
                        .size(58.dp)
                        .clip(RoundedCornerShape(12.dp))
                        .background(Color.White)
                        .padding(7.dp),
                    loading = { PlatformTile(a.title, "Social", size = 58) },
                    error = { PlatformTile(a.title, "Social", size = 58) },
                )
                Spacer(Modifier.width(14.dp))
            }
            Column(Modifier.weight(1f)) {
                Text(a.title, style = MaterialTheme.typography.titleLarge)
                Text(
                    listOfNotNull(a.breachDate.takeIf { it.isNotBlank() }, a.domain)
                        .joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall,
                    color = t.textMute,
                )
            }
        }

        Spacer(Modifier.height(16.dp))
        DataList(
            buildList {
                add("Accounts exposed" to "%,d".format(a.accounts))
                add("Severity" to "${a.severity}/100 · ${a.band}")
                add("Confirmed" to if (a.verified) "Verified by HIBP" else "Unverified")
                if (a.stealerLog) {
                    add("Source" to "Malware on victims' own machines, not one company's servers")
                }
            }
        )

        if (a.summary.isNotBlank()) {
            SectionLabel("What happened")
            Text(a.summary, style = MaterialTheme.typography.bodyMedium, color = t.textDim)
        }

        if (a.dataClasses.isNotEmpty()) {
            SectionLabel("What was exposed · ${a.dataClasses.size}")
            ChipRow(
                a.dataClasses,
                dangerPredicate = {
                    it.contains("Password", true) || it.contains("Credit", true) ||
                        it.contains("Government", true) || it.contains("Social security", true)
                },
            )
        }

        Spacer(Modifier.height(20.dp))
        Button(
            onClick = { haptics.tap(); uri.openUri(a.url) },
            shape = RoundedCornerShape(11.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Read the full article")
            Spacer(Modifier.width(8.dp))
            Icon(
                Icons.AutoMirrored.Filled.OpenInNew,
                contentDescription = null,
                modifier = Modifier.size(16.dp),
            )
        }
        Spacer(Modifier.height(8.dp))
        Text(
            "The full write-up explains what each leaked field means for you and what to " +
                "do about it. Breach records from Have I Been Pwned, used under CC BY 4.0; " +
                "the severity score and analysis are MyRecon's.",
            style = MaterialTheme.typography.bodySmall,
            color = t.textMute,
        )

        Spacer(Modifier.height(22.dp))
        DetailedReportOffer()
        Spacer(Modifier.height(24.dp))
    }
}
