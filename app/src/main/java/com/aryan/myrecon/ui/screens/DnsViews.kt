package com.aryan.myrecon.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.data.DnsIntel
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.components.*
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.Mono
import com.aryan.myrecon.ui.theme.MonoStyle

/**
 * The DNS report.
 *
 * Ordered by what a reader can act on. The spoofing verdict leads, because it
 * is the one thing on this screen with a consequence attached; the vendor
 * estate follows, because it is the most revealing; the raw records sit near
 * the bottom, where someone who wants them will look for them. A record dump
 * at the top would bury both of the findings underneath it.
 */
@Composable
fun DnsReportView(r: DnsIntel.Report) {
    val t = LocalReconTokens.current

    Header(r)
    Spacer(Modifier.height(6.dp))

    EmailSecurity(r.email)
    Vendors(r.stack)
    Addresses(r.addresses)
    Caa(r.caa)
    Records(r.records)
    Subdomains(r.subdomains, r.domain)

    SectionLabel("What this did not check")
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        // Only the caveats that change how a finding should be read. The
        // generic ones were true and unread.
        r.notes.take(2).forEach { NoteCard(it) }
    }
    Spacer(Modifier.height(16.dp))
}

/** Severity as colour, so the shape of the report is readable before the words. */
@Composable
private fun tint(s: DnsIntel.Severity): Color {
    val t = LocalReconTokens.current
    return when (s) {
        DnsIntel.Severity.Ok -> t.ok
        DnsIntel.Severity.Info -> t.info
        DnsIntel.Severity.Warn -> t.warn
        DnsIntel.Severity.Bad -> t.danger
    }
}

// ── Header ───────────────────────────────────────────────────────

@Composable
private fun Header(r: DnsIntel.Report) {
    val t = LocalReconTokens.current
    val accent = MaterialTheme.colorScheme.primary

    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(3.dp))
            .background(t.bgSoft)
            .bracketFrame(accent.copy(alpha = 0.7f))
            .padding(16.dp),
    ) {
        Text(
            r.domain,
            style = MaterialTheme.typography.titleLarge,
            maxLines = 1, overflow = TextOverflow.Ellipsis,
        )
        Spacer(Modifier.height(12.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Stat("Records", r.totalRecords.toString(), Modifier.weight(1f))
            Stat("Vendors", r.stack.size.toString(), Modifier.weight(1f))
            Stat(
                "Subdomains",
                r.subdomains.total.takeIf { it > 0 }?.toString() ?: "—",
                Modifier.weight(1f),
            )
        }
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Stat(
                "DNSSEC",
                if (r.dnssecValidated) "Validated" else if (r.dsPresent) "Signed" else "Off",
                Modifier.weight(1f),
            )
            Stat("Wildcard", if (r.wildcard) "Yes" else "No", Modifier.weight(1f))
            Stat(
                "TTL",
                r.minTtl?.let { min -> "${min}–${r.maxTtl}s" } ?: "—",
                Modifier.weight(1f),
            )
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
            .padding(vertical = 10.dp, horizontal = 10.dp),
    ) {
        Text(
            value, style = MonoStyle, color = MaterialTheme.colorScheme.onSurface,
            maxLines = 1, overflow = TextOverflow.Ellipsis,
        )
        Text(label.uppercase(), style = MaterialTheme.typography.labelSmall, color = t.textMute)
    }
}

// ── Email security ───────────────────────────────────────────────

/**
 * The spoofing verdict.
 *
 * Stated as a plain claim rather than a checklist of acronyms, because "SPF ✓
 * DKIM ✓ DMARC ✓" reads as safe even when the DMARC policy is `p=none` and
 * every forgery is delivered. The acronyms are underneath, for whoever wants
 * to check the reasoning.
 */
@Composable
private fun EmailSecurity(e: DnsIntel.EmailSecurity) {
    val t = LocalReconTokens.current
    val colour = tint(e.severity)

    SectionLabel("Email spoofing")
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(colour.copy(alpha = 0.09f))
            .border(1.dp, colour.copy(alpha = 0.4f), RoundedCornerShape(14.dp))
            .padding(16.dp),
    ) {
        Text(e.verdict, style = MaterialTheme.typography.titleMedium, color = colour)
        Spacer(Modifier.height(10.dp))
        ChipRow(
            buildList {
                add(e.spf?.let { "SPF ${it.policy}" } ?: "no SPF")
                add(e.dmarc?.let { "DMARC p=${it.policy}" } ?: "no DMARC")
                add(if (e.dkimSelectors.isEmpty()) "no DKIM found" else "DKIM ${e.dkimSelectors.size}")
                if (e.mtaSts) add("MTA-STS")
                if (e.tlsRpt) add("TLS-RPT")
                if (e.bimi) add("BIMI")
                add(if (e.acceptsMail) "receives mail" else "no MX")
            },
            strongPredicate = { it.contains("reject") || it.startsWith("SPF fail") || it == "MTA-STS" },
            dangerPredicate = { it.startsWith("no ") || it.contains("p=none") },
        )
    }

    Spacer(Modifier.height(10.dp))
    e.findings.forEach { f ->
        Row(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
            Box(
                Modifier
                    .padding(top = 5.dp)
                    .size(7.dp)
                    .clip(RoundedCornerShape(99.dp))
                    .background(tint(f.severity)),
            )
            Spacer(Modifier.width(10.dp))
            Text(f.text, style = MaterialTheme.typography.bodySmall, color = t.textDim)
        }
    }

    // The raw SPF and DMARC strings used to be printed here. They were the
    // longest thing on the screen and said nothing the findings above had not
    // already said in words — the includes are named individually under
    // Technology & vendors, and the DKIM selectors are in a finding. Only the
    // reporting address survives: it is a real contact and appears nowhere else.
    e.dmarc?.aggregateReports?.takeIf { it.isNotEmpty() }?.let {
        Spacer(Modifier.height(10.dp))
        DataList(listOf("DMARC reports to" to it.joinToString(", ")))
    }
}

// ── Vendors ──────────────────────────────────────────────────────

/**
 * The organisation's stack, as its own DNS describes it.
 *
 * Grouped by how the evidence was obtained — who runs the mail, who runs the
 * DNS, who it has proved ownership to, who may send on its behalf — because
 * those are four different strengths of claim.
 */
@Composable
private fun Vendors(stack: List<DnsIntel.Vendor>) {
    if (stack.isEmpty()) return
    val t = LocalReconTokens.current

    SectionLabel("Technology & vendors · ${stack.size}")
    Text(
        "Read from the domain's own records — MX names the mail host, NS the DNS host, " +
            "and each verification token is the organisation proving ownership to a vendor.",
        style = MaterialTheme.typography.bodySmall,
        color = t.textMute,
        modifier = Modifier.padding(bottom = 8.dp),
    )

    // One row per vendor, not one card. A well-instrumented domain names
    // twenty-odd services, and at a card each the section becomes a scroll
    // with no shape to it — the list is the finding, not any single entry.
    stack.groupBy { it.category }.forEach { (category, items) ->
        Text(
            "${category.uppercase()} · ${items.size}",
            fontFamily = Mono,
            style = MaterialTheme.typography.labelSmall,
            color = t.textMute,
            modifier = Modifier.padding(top = 12.dp, bottom = 5.dp),
        )
        Column(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .background(MaterialTheme.colorScheme.surface)
                .border(1.dp, t.border, RoundedCornerShape(12.dp))
                .padding(horizontal = 13.dp, vertical = 3.dp),
        ) {
            items.forEachIndexed { i, v ->
                if (i > 0) HorizontalDivider(color = t.border.copy(alpha = 0.5f))
                Column(Modifier.fillMaxWidth().padding(vertical = 9.dp)) {
                    Text(v.name, style = MaterialTheme.typography.bodyMedium)
                    Text(
                        v.evidence,
                        style = MonoStyle, color = t.textMute,
                        maxLines = 1, overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}

// ── Addresses ────────────────────────────────────────────────────

@Composable
private fun Addresses(addresses: List<DnsIntel.Address>) {
    if (addresses.isEmpty()) return
    SectionLabel("Where it resolves · ${addresses.size}")
    addresses.forEach { a ->
        ReconCard {
            Text(a.ip, style = MonoStyle, color = MaterialTheme.colorScheme.onSurface)
            // Only rows that actually carry a value. An em dash for every
            // field a source did not return is three lines of nothing.
            val rows = buildList {
                a.reverse?.let { add("Reverse DNS" to it) }
                listOfNotNull(a.asn, a.org).joinToString(" · ")
                    .takeIf { it.isNotBlank() }?.let { add("Network" to it) }
                listOfNotNull(a.city, a.country).joinToString(", ")
                    .takeIf { it.isNotBlank() }?.let { add("Location" to it) }
            }
            if (rows.isNotEmpty()) DataList(rows)
        }
        Spacer(Modifier.height(8.dp))
    }
}

// ── Structure ────────────────────────────────────────────────────

/**
 * Certificate authorities.
 *
 * All that is left of what used to be a "Zone" block. DNSSEC, the wildcard and
 * the TTL range are already three of the six tiles in the header, and printing
 * them again underneath was the same facts twice.
 */
@Composable
private fun Caa(caa: List<DnsIntel.Caa>) {
    if (caa.isEmpty()) return
    val t = LocalReconTokens.current
    SectionLabel("Certificate authorities")
    Text(
        "CAA restricts who may issue certificates for this domain.",
        style = MaterialTheme.typography.bodySmall,
        color = t.textMute,
        modifier = Modifier.padding(bottom = 8.dp),
    )
    ChipRow(caa.map { "${it.tag}: ${it.value}" })
}

// ── Records ──────────────────────────────────────────────────────

/**
 * The raw records, behind one tap.
 *
 * They used to open expanded, and for a well-instrumented domain that meant
 * forty rows — most of them TXT verification tokens already decoded into named
 * vendors further up. The records are evidence worth keeping, not the finding,
 * so they now sit closed with their shape summarised on the line.
 */
@Composable
private fun Records(records: Map<String, List<com.aryan.myrecon.data.DnsRecord>>) {
    if (records.isEmpty()) return
    val t = LocalReconTokens.current
    val haptics = LocalHaptics.current
    var open by remember { mutableStateOf(false) }

    val total = records.values.sumOf { it.size }
    SectionLabel("Raw records · $total")

    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, t.border, RoundedCornerShape(12.dp))
            .clickable { haptics.tap(); open = !open }
            .padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            records.entries.joinToString("  ") { "${it.key} ${it.value.size}" },
            style = MonoStyle, color = t.textDim,
            maxLines = 2, overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f),
        )
        Spacer(Modifier.width(10.dp))
        Text(
            if (open) "Hide" else "Show",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.primary,
        )
    }

    AnimatedVisibility(visible = open) {
        Column {
            records.forEach { (type, recs) ->
                Text(
                    "$type · ${recs.size}",
                    fontFamily = Mono,
                    style = MaterialTheme.typography.labelSmall,
                    color = t.textMute,
                    modifier = Modifier.padding(top = 12.dp, bottom = 4.dp),
                )
                DataList(recs.map { (it.ttl?.let { s -> "TTL ${s}s" } ?: "record") to it.value })
            }
        }
    }
}

// ── Subdomains ───────────────────────────────────────────────────

/**
 * Names found in Certificate Transparency.
 *
 * Shown shallowest-first: `api.example.com` says more about how an
 * organisation is structured than the fourth level of a build artefact's
 * hostname, and sorting by depth puts the informative ones on screen.
 */
@Composable
private fun Subdomains(s: DnsIntel.Subdomains, domain: String) {
    val t = LocalReconTokens.current
    val haptics = LocalHaptics.current
    var expanded by remember { mutableStateOf(false) }

    if (s.error != null) {
        SectionLabel("Subdomains")
        NoteCard(s.error, tint = t.warn)
        return
    }
    if (s.names.isEmpty()) {
        SectionLabel("Subdomains")
        NoteCard(
            "No certificates naming a subdomain of $domain were found in the " +
                "Certificate Transparency logs.",
        )
        return
    }

    SectionLabel("Subdomains · ${s.total}")
    Text(
        "From Certificate Transparency (${s.sources.joinToString(", ")}) — every hostname " +
            "a public certificate was issued for.",
        style = MaterialTheme.typography.bodySmall,
        color = t.textMute,
        modifier = Modifier.padding(bottom = 8.dp),
    )

    val shown = if (expanded) s.names else s.names.take(15)
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, t.border, RoundedCornerShape(12.dp))
            .padding(horizontal = 12.dp, vertical = 4.dp),
    ) {
        shown.forEachIndexed { i, name ->
            if (i > 0) HorizontalDivider(color = t.border.copy(alpha = 0.5f))
            Text(
                name,
                style = MonoStyle,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 1, overflow = TextOverflow.Ellipsis,
                modifier = Modifier.fillMaxWidth().padding(vertical = 9.dp),
            )
        }
    }

    AnimatedVisibility(visible = !expanded && s.names.size > shown.size) {
        Text(
            "Show all ${s.names.size} names" +
                if (s.total > s.names.size) " (of ${s.total} found)" else "",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier
                .padding(top = 10.dp)
                .clickable { haptics.tap(); expanded = true },
        )
    }
}
