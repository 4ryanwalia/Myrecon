package com.aryan.myrecon.ui.screens

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.SubcomposeAsyncImage
import com.aryan.myrecon.data.*
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.components.*
import com.aryan.myrecon.ui.pressScale
import com.aryan.myrecon.ui.theme.*

/**
 * Result renderers, one per lookup.
 *
 * The shared rule: measured values are monospace, interpretation is sans, and
 * anything with a confidence attached shows the band as colour *and* text so it
 * survives both colour-blindness and a glance.
 */

private fun Long.compact(): String = when {
    this >= 1_000_000_000 -> "%.1fB".format(this / 1e9)
    this >= 1_000_000 -> "%.1fM".format(this / 1e6)
    this >= 1_000 -> "%.1fK".format(this / 1e3)
    else -> toString()
}

// ── Username ─────────────────────────────────────────────────────

@Composable
fun UsernameView(r: UsernameResult) {
    val t = LocalReconTokens.current
    val uriHandler = LocalUriHandler.current
    val profiles = r.results.profiles

    if (profiles.isEmpty()) {
        StatePanel(
            "Nothing found",
            "No public accounts matched this handle. That is a genuinely good result " +
                "if you were checking your own footprint.",
        )
        return
    }

    val confirmed = profiles.filter { it.confidence != "unverified" }
    val unverified = profiles.filter { it.confidence == "unverified" }
    val high = confirmed.count { it.confidence == "high" }
    val byCategory = confirmed.groupBy { it.category.ifBlank { "Other" } }
        .toList().sortedByDescending { it.second.size }

    val (score, label, message) = exposureFor(confirmed.size, high, byCategory.size)

    ExposureGauge(score = score, label = label, message = message)

    Spacer(Modifier.height(14.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        StatTile("Accounts", "${confirmed.size}", Modifier.weight(1f))
        StatTile("High conf.", "$high", Modifier.weight(1f))
        StatTile("Categories", "${byCategory.size}", Modifier.weight(1f))
    }

    // Grouped by category so a long list reads as a shape rather than a wall.
    // Entrance is staggered but capped: past about a dozen the delay stops
    // feeling deliberate and starts feeling slow.
    var rank = 0
    byCategory.forEach { (category, items) ->
        CategoryHeader(category, items.size)
        items.forEach { p ->
            StaggeredIn(index = rank++) {
                ProfileCard(p) { uriHandler.openUri(p.url) }
            }
            Spacer(Modifier.height(8.dp))
        }
    }

    if (unverified.isNotEmpty()) {
        CategoryHeader("Unverified", unverified.size)
        Text(
            "These platforms return a page for any handle, so a result here is not " +
                "evidence the account exists. Shown because omitting them would understate " +
                "the footprint just as badly as counting them would overstate it.",
            style = MaterialTheme.typography.bodySmall,
            color = t.textMute,
            modifier = Modifier.padding(bottom = 10.dp),
        )
        unverified.forEach { p ->
            ProfileCard(p) { uriHandler.openUri(p.url) }
            Spacer(Modifier.height(8.dp))
        }
    }

    Spacer(Modifier.height(10.dp))
    Text(
        "Accounts sharing a handle are frequently unrelated people. Treat this as a set of " +
            "candidates rather than one confirmed identity.",
        style = MaterialTheme.typography.bodySmall,
        color = t.textMute,
    )
}

/** Fade-and-rise entrance, staggered by position in the list. */
@Composable
private fun StaggeredIn(index: Int, content: @Composable () -> Unit) {
    var shown by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        kotlinx.coroutines.delay((index.coerceAtMost(12) * 35).toLong())
        shown = true
    }
    val alpha by animateFloatAsState(if (shown) 1f else 0f, tween(220), label = "cardAlpha")
    val offset by animateFloatAsState(if (shown) 0f else 14f, tween(260), label = "cardOffset")
    Box(
        Modifier
            .graphicsLayer {
                this.alpha = alpha
                translationY = offset
            },
    ) { content() }
}

@Composable
private fun ProfileCard(p: Profile, onOpen: () -> Unit) {
    val t = LocalReconTokens.current
    val haptics = LocalHaptics.current
    val source = remember { MutableInteractionSource() }
    val stripe = when (p.confidence?.lowercase()) {
        "high" -> t.ok
        "medium" -> t.warn
        else -> t.textMute
    }
    ReconCard(
        stripe = stripe,
        modifier = Modifier
            .pressScale(source)
            .clickable(interactionSource = source, indication = null) {
                haptics.tap()
                onOpen()
            },
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Avatar(url = p.avatar, platform = p.platform, category = p.category.ifBlank { "Other" })
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    p.platform.ifBlank { "Unknown" },
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1, overflow = TextOverflow.Ellipsis,
                )
                // Prefer the name the platform displays; fall back to the URL.
                Text(
                    p.displayName?.takeIf { it.isNotBlank() }
                        ?: p.url.removePrefix("https://").removePrefix("www."),
                    style = MonoStyle, color = t.textDim,
                    maxLines = 1, overflow = TextOverflow.Ellipsis,
                )
            }
            Spacer(Modifier.width(8.dp))
            Icon(
                Icons.AutoMirrored.Filled.OpenInNew,
                contentDescription = "Open",
                tint = t.textMute,
                modifier = Modifier.size(16.dp),
            )
        }
        if (!p.bio.isNullOrBlank()) {
            Spacer(Modifier.height(8.dp))
            Text(p.bio, style = MaterialTheme.typography.bodySmall, color = t.textDim, maxLines = 3, overflow = TextOverflow.Ellipsis)
        }
    }
}

/**
 * Profile picture with a monogram fallback.
 *
 * Avatar URLs come from a platform's own og:image or API, so plenty of them
 * 404, hotlink-block, or return something that is not an image. Every one of
 * those paths has to land on the coloured tile rather than an empty square —
 * a blank hole in the list looks like the app broke, not like the platform
 * declined to serve a picture.
 */
@Composable
private fun Avatar(url: String?, platform: String, category: String) {
    if (url.isNullOrBlank()) {
        PlatformTile(platform, category)
        return
    }
    SubcomposeAsyncImage(
        model = url,
        contentDescription = null,
        contentScale = ContentScale.Crop,
        modifier = Modifier
            .size(40.dp)
            .clip(RoundedCornerShape(11.dp)),
        loading = { PlatformTile(platform, category) },
        error = { PlatformTile(platform, category) },
    )
}

@Composable
private fun StatTile(label: String, value: String, modifier: Modifier = Modifier) {
    val t = LocalReconTokens.current
    Column(
        modifier
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, t.border, RoundedCornerShape(12.dp))
            .padding(vertical = 12.dp, horizontal = 12.dp),
    ) {
        Text(value, style = MonoScore, color = MaterialTheme.colorScheme.onSurface)
        Text(label.uppercase(), style = MaterialTheme.typography.labelSmall, color = t.textMute)
    }
}

// ── Email ────────────────────────────────────────────────────────

@Composable
fun EmailView(r: EmailResult) {
    val t = LocalReconTokens.current
    val s = r.summary
    val dw = r.darkweb

    val tint = if (s.breached) t.danger else t.ok
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(tint.copy(alpha = 0.10f))
            .border(1.dp, tint.copy(alpha = 0.4f), RoundedCornerShape(14.dp))
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                if (s.breached) "Breach exposure detected" else "No breaches found",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.weight(1f),
            )
            Text(
                if (s.breached) "${s.breachCount} breaches" else "clean",
                style = MonoStyle, color = tint,
            )
        }
        if (s.breached) {
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (s.riskLabel.isNotBlank()) MetricTile("Risk", s.riskLabel, Modifier.weight(1f))
                if (dw.recordsExposed > 0) MetricTile("Records", dw.recordsExposed.compact(), Modifier.weight(1f))
                if (s.recordsFound > 0) MetricTile("Rows", s.recordsFound.toString(), Modifier.weight(1f))
            }
        }
    }

    if (dw.exposedData.isNotEmpty()) {
        SectionLabel("What leaked")
        val max = dw.exposedData.first().count.coerceAtLeast(1)
        dw.exposedData.take(8).forEach { d ->
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 4.dp)) {
                Text(d.name, style = MaterialTheme.typography.bodySmall, color = t.textDim, modifier = Modifier.weight(0.4f), maxLines = 1, overflow = TextOverflow.Ellipsis)
                Box(
                    Modifier
                        .weight(0.45f)
                        .height(8.dp)
                        .clip(RoundedCornerShape(99.dp))
                        .background(t.surface2),
                ) {
                    Box(
                        Modifier
                            .fillMaxWidth(d.count.toFloat() / max)
                            .fillMaxHeight()
                            .clip(RoundedCornerShape(99.dp))
                            .background(MaterialTheme.colorScheme.primary),
                    )
                }
                Spacer(Modifier.width(8.dp))
                Text("${d.count}", style = MonoStyle, color = t.textMute)
            }
        }
    }

    if (dw.breaches.isNotEmpty()) {
        SectionLabel("Breaches naming this address · ${dw.breaches.size} of ${s.breachCount}")
        dw.breaches.take(12).forEach { b ->
            ReconCard(stripe = if (b.passwordRisk == "plaintext") t.danger else t.textMute) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(b.name, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                    Text(b.date, style = MonoStyle, color = t.textMute)
                }
                if (b.records > 0) {
                    Text("${b.records.compact()} records", style = MonoStyle, color = t.textDim)
                }
                if (b.exposed.isNotEmpty()) {
                    Spacer(Modifier.height(8.dp))
                    ChipRow(
                        b.exposed.take(6),
                        dangerPredicate = { it.contains("password", true) || it.contains("phone", true) },
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
        }
    }

    SectionLabel("Address analysis")
    DataList(
        listOf(
            "Provider" to "${r.analysis.provider} (${r.analysis.providerType})",
            "Deliverable" to if (r.analysis.deliverable) "Yes — mail server present" else "No MX record",
            "Disposable" to if (r.analysis.disposable) "Yes (flagged)" else "No",
            "MX hosts" to r.analysis.mxHosts.joinToString("\n"),
        )
    )

    if (s.linkedAccounts.isNotEmpty()) {
        SectionLabel("Linked accounts")
        ChipRow(s.linkedAccounts, strongPredicate = { true })
    }
}

@Composable
private fun MetricTile(label: String, value: String, modifier: Modifier = Modifier) {
    val t = LocalReconTokens.current
    Column(
        modifier
            .clip(RoundedCornerShape(10.dp))
            .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.7f))
            .border(1.dp, t.border, RoundedCornerShape(10.dp))
            .padding(10.dp),
    ) {
        Text(label.uppercase(), style = MaterialTheme.typography.labelSmall, color = t.textMute)
        Text(value, style = MonoStyle, color = MaterialTheme.colorScheme.onSurface)
    }
}

// ── Domain / DNS / IP ────────────────────────────────────────────

@Composable
fun DomainView(r: DomainResult) {
    if (!r.found) {
        StatePanel("Nothing found", r.error ?: "No registration data for this domain.")
        return
    }
    SectionLabel("Registration")
    DataList(
        listOf(
            "Registrar" to (r.whois.registrar ?: "—"),
            "Created" to (r.whois.created ?: "—"),
            "Expires" to (r.whois.expires ?: "—"),
            "Updated" to (r.whois.updated ?: "—"),
            "Nameservers" to r.whois.nameservers.joinToString("\n"),
            "Status" to r.whois.status.joinToString("\n"),
        )
    )
    if (r.primaryIp != null) {
        SectionLabel("Resolved host")
        DataList(listOf("Primary IP" to r.primaryIp))
    }
}

@Composable
fun DnsView(r: DnsResult) {
    if (r.records.isEmpty()) {
        StatePanel("No records", "No DNS records were returned for this domain.")
        return
    }
    r.records.forEach { (type, recs) ->
        if (recs.isEmpty()) return@forEach
        SectionLabel("$type · ${recs.size}")
        DataList(recs.map { (it.ttl?.let { t -> "TTL ${t}s" } ?: "record") to it.value })
    }
}

@Composable
fun IpView(r: IpResult) {
    if (!r.found) {
        StatePanel("Nothing found", r.error ?: "No data available for this IP.")
        return
    }
    SectionLabel("Location")
    DataList(
        listOf(
            "City" to (r.geo.city ?: "—"),
            "Region" to (r.geo.region ?: "—"),
            "Country" to (r.geo.country ?: "—"),
            "Timezone" to (r.geo.timezone ?: "—"),
        )
    )
    SectionLabel("Network")
    DataList(
        listOf(
            "ASN" to (r.network.asn ?: "—"),
            "Organisation" to (r.network.org ?: "—"),
            "ISP" to (r.network.isp ?: "—"),
            "Hosting" to when (r.network.hosting) {
                true -> "Yes — datacentre range"
                false -> "No — likely residential"
                null -> "—"
            },
            "Reverse DNS" to (r.reverseDns ?: "—"),
        )
    )
}

// ── Deep search ──────────────────────────────────────────────────

@Composable
fun InvestigationView(r: InvestigationResult) {
    val t = LocalReconTokens.current
    val a = r.assessment
    val tint = bandColor(a.confidence.band)

    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(tint.copy(alpha = 0.09f))
            .border(1.dp, tint.copy(alpha = 0.38f), RoundedCornerShape(14.dp))
            .padding(16.dp),
    ) {
        Text(
            "Assessment — ${a.confidence.band} confidence (${a.confidence.score}/100)",
            style = MaterialTheme.typography.titleMedium,
        )
        Spacer(Modifier.height(7.dp))
        Text(a.text, style = MaterialTheme.typography.bodySmall, color = t.textDim)
        if (a.generatedBy.isNotBlank()) {
            Spacer(Modifier.height(8.dp))
            Text("Summary ${a.generatedBy}.", style = MaterialTheme.typography.bodySmall, color = t.textMute)
        }
    }

    val profiles = r.graph.nodes.filter { it.type == "social_profile" }
    if (profiles.isNotEmpty()) {
        SectionLabel("Accounts · ${profiles.size}")
        profiles.forEach { n ->
            val stripe = bandColor(n.confidence.band)
            ReconCard(stripe = stripe) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            n.attrs.platform ?: n.label,
                            style = MaterialTheme.typography.titleMedium,
                            maxLines = 1, overflow = TextOverflow.Ellipsis,
                        )
                        Text(
                            n.attrs.url ?: n.value,
                            style = MonoStyle, color = t.textDim,
                            maxLines = 1, overflow = TextOverflow.Ellipsis,
                        )
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        Text("${n.confidence.score}", style = MonoScore, color = stripe)
                        Text(n.confidence.band.uppercase(), style = MaterialTheme.typography.labelSmall, color = t.textMute)
                    }
                }
                if (n.confidence.factors.isNotEmpty()) {
                    Spacer(Modifier.height(8.dp))
                    ChipRow(
                        n.confidence.factors.take(3).map { it.name.replace('_', ' ') },
                        strongPredicate = { it.contains("verified") || it.contains("multiple") },
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
        }
    }

    if (r.graph.clusters.isNotEmpty()) {
        SectionLabel("Clusters")
        r.graph.clusters.forEach { c ->
            ReconCard(stripe = bandColor(c.confidence.band)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(c.label, style = MonoStyle, modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text("${c.confidence.score}/100", style = MonoStyle, color = bandColor(c.confidence.band))
                }
                Text("${c.size} entities · ${c.types.joinToString(", ")}", style = MaterialTheme.typography.bodySmall, color = t.textMute)
            }
            Spacer(Modifier.height(8.dp))
        }
    }
}
