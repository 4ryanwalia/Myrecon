package com.aryan.myrecon.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.SubcomposeAsyncImage
import com.aryan.myrecon.data.DeepSearch
import com.aryan.myrecon.data.DorkPlan
import com.aryan.myrecon.data.PersonIntel
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.components.*
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.Mono
import com.aryan.myrecon.ui.theme.MonoStyle

/**
 * Deep Search results.
 *
 * The ordering is the argument the screen is making. Records that *name* the
 * subject come first — a Wikidata entry with a LinkedIn identifier on it, a
 * Keybase key that signed for two accounts — because those are published
 * claims by someone who curates them. Search hits come after, grouped by what
 * kind of page they are, so a LinkedIn profile and a forum thread that happens
 * to say the name never sit in the same list. The plan and the limits close
 * it out, so what was searched and what could not be searched are both on the
 * same screen as the findings.
 */
@Composable
fun DeepSearchView(r: DeepSearch.Result) {
    val t = LocalReconTokens.current

    Header(r)

    r.engineNote?.let {
        Spacer(Modifier.height(12.dp))
        NoteCard(it, tint = t.warn)
    }

    // ── Identity records ─────────────────────────────────────────

    r.identity?.let {
        Spacer(Modifier.height(16.dp))
        VerifiedIdentity(it)
    }

    if (r.people.isNotEmpty()) {
        SectionLabel("Identity records · ${r.people.size} candidate${plural(r.people.size)}")
        r.people.forEach { person ->
            PersonCard(person)
            Spacer(Modifier.height(8.dp))
        }
    }

    if (r.accounts.isNotEmpty()) {
        SectionLabel("Accounts named by a registry · ${r.accounts.size}")
        Text(
            "Each of these was published by a source that keeps records, not inferred " +
                "from a matching string.",
            style = MaterialTheme.typography.bodySmall,
            color = t.textMute,
            modifier = Modifier.padding(bottom = 8.dp),
        )
        r.accounts.forEach { a ->
            AccountCard(a)
            Spacer(Modifier.height(8.dp))
        }
    }

    // ── Web findings ─────────────────────────────────────────────

    if (r.sections.isEmpty()) {
        Spacer(Modifier.height(18.dp))
        StatePanel(
            "No indexed pages matched",
            if (r.engineNote != null) {
                "The keyless search engines would not answer this device for long enough " +
                    "to finish the plan. Every query is listed below — tap one to run it " +
                    "in your browser."
            } else {
                "${r.queriesRun} searches ran and none returned a page that satisfied its " +
                    "own query. Results that did not match were discarded rather than shown."
            },
        )
    }

    r.sections.forEach { section ->
        SectionLabel("${section.section.label} · ${section.hits.size}")
        Text(
            section.section.blurb,
            style = MaterialTheme.typography.bodySmall,
            color = t.textMute,
            modifier = Modifier.padding(bottom = 8.dp),
        )
        if (section.section == DorkPlan.Section.InstagramFootprint) {
            InstagramCaveat()
            Spacer(Modifier.height(8.dp))
        }
        section.hits.forEach { hit ->
            HitCard(hit)
            Spacer(Modifier.height(8.dp))
        }
    }

    // ── Method ───────────────────────────────────────────────────

    SearchPlan(r.plan)
    Limits(r.notes)
    Spacer(Modifier.height(16.dp))
}

private fun plural(n: Int) = if (n == 1) "" else "s"

// ── Header ───────────────────────────────────────────────────────

@Composable
private fun Header(r: DeepSearch.Result) {
    val t = LocalReconTokens.current
    val accent = MaterialTheme.colorScheme.primary
    val modeBlurb = when (r.mode) {
        DeepSearch.Mode.Name ->
            "Read as a person's name — identity registries first, then a " +
                "professional-first sweep of the indexed web."
        DeepSearch.Mode.Handle ->
            "Read as a handle — path-scoped queries for the account's own pages, " +
                "then mention-level queries across public discussion."
    }

    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(3.dp))
            .background(t.bgSoft)
            .bracketFrame(accent.copy(alpha = 0.7f))
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                r.mode.label.uppercase(),
                fontFamily = Mono,
                style = MaterialTheme.typography.labelSmall,
                color = accent,
                modifier = Modifier
                    .clip(RoundedCornerShape(3.dp))
                    .background(accent.copy(alpha = 0.14f))
                    .padding(horizontal = 7.dp, vertical = 3.dp),
            )
            Spacer(Modifier.width(10.dp))
            Text(
                r.subject,
                style = MaterialTheme.typography.titleLarge,
                maxLines = 1, overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
        }
        Spacer(Modifier.height(8.dp))
        Text(modeBlurb, style = MaterialTheme.typography.bodySmall, color = t.textDim)
        Spacer(Modifier.height(12.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            StatBox("Queries run", r.queriesRun.toString(), Modifier.weight(1f))
            StatBox("Pages found", r.hits.toString(), Modifier.weight(1f))
            StatBox(
                "Records",
                (r.people.size + r.accounts.size + (r.identity?.proofs?.size ?: 0)).toString(),
                Modifier.weight(1f),
            )
        }
    }
}

@Composable
private fun StatBox(label: String, value: String, modifier: Modifier = Modifier) {
    val t = LocalReconTokens.current
    Column(
        modifier
            .clip(RoundedCornerShape(3.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, t.border, RoundedCornerShape(3.dp))
            .padding(vertical = 10.dp, horizontal = 10.dp),
    ) {
        Text(value, style = MonoStyle, color = MaterialTheme.colorScheme.onSurface)
        Text(label.uppercase(), style = MaterialTheme.typography.labelSmall, color = t.textMute)
    }
}

// ── Identity records ─────────────────────────────────────────────

/**
 * A Wikidata person.
 *
 * The description is given the same prominence as the name on purpose. It is
 * the only thing that lets someone tell *this* Satya Nadella from another one,
 * and the card is explicitly a candidate rather than an answer.
 */
@Composable
private fun PersonCard(p: PersonIntel.Person) {
    val t = LocalReconTokens.current
    val uri = LocalUriHandler.current
    val haptics = LocalHaptics.current

    ReconCard(stripe = t.info) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (p.image != null) {
                SubcomposeAsyncImage(
                    model = p.image,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.size(48.dp).clip(RoundedCornerShape(12.dp)),
                    loading = { PlatformTile(p.name, "Social", size = 48) },
                    error = { PlatformTile(p.name, "Social", size = 48) },
                )
                Spacer(Modifier.width(12.dp))
            }
            Column(Modifier.weight(1f)) {
                Text(
                    p.name,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1, overflow = TextOverflow.Ellipsis,
                )
                if (p.description.isNotBlank()) {
                    Text(
                        p.description,
                        style = MaterialTheme.typography.bodySmall,
                        color = t.textDim,
                        maxLines = 3, overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }

        if (p.facts.isNotEmpty()) {
            Spacer(Modifier.height(12.dp))
            DataList(p.facts)
        }

        if (p.links.isNotEmpty()) {
            Spacer(Modifier.height(12.dp))
            Text("PROFILES ON RECORD", style = MaterialTheme.typography.labelSmall, color = t.textMute)
            Spacer(Modifier.height(4.dp))
            p.links.forEach { link ->
                Row(
                    Modifier
                        .fillMaxWidth()
                        .clickable { haptics.tap(); uri.openUri(link.url) }
                        .padding(vertical = 7.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        link.label,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    Spacer(Modifier.width(10.dp))
                    Text(
                        link.handle ?: link.url,
                        style = MonoStyle,
                        color = t.textDim,
                        maxLines = 1, overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f),
                    )
                    Icon(
                        Icons.AutoMirrored.Filled.OpenInNew,
                        contentDescription = null,
                        tint = t.textMute,
                        modifier = Modifier.size(14.dp),
                    )
                }
            }
        }

        Spacer(Modifier.height(10.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Chip("Wikidata ${p.wikidataId}")
            Spacer(Modifier.width(6.dp))
            Chip("candidate match")
        }
        if (p.wikipedia != null) {
            Spacer(Modifier.height(8.dp))
            Text(
                "Read the Wikipedia article",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.clickable { haptics.tap(); uri.openUri(p.wikipedia) },
            )
        }
    }
}

@Composable
private fun AccountCard(a: DeepSearch.Account) {
    val t = LocalReconTokens.current
    val uri = LocalUriHandler.current
    val haptics = LocalHaptics.current

    ReconCard {
        Row(
            Modifier.clickable { haptics.tap(); uri.openUri(a.url) },
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (a.avatar != null) {
                SubcomposeAsyncImage(
                    model = a.avatar,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.size(40.dp).clip(RoundedCornerShape(10.dp)),
                    loading = { PlatformTile(a.platform, "Developer", size = 40) },
                    error = { PlatformTile(a.platform, "Developer", size = 40) },
                )
            } else {
                PlatformTile(a.platform, "Professional", size = 40)
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    a.handle?.let { "${a.platform} · $it" } ?: a.platform,
                    style = MaterialTheme.typography.titleSmall,
                    maxLines = 1, overflow = TextOverflow.Ellipsis,
                )
                Text(
                    a.detail,
                    style = MaterialTheme.typography.bodySmall,
                    color = t.textDim,
                    maxLines = 2, overflow = TextOverflow.Ellipsis,
                )
            }
            Icon(
                Icons.AutoMirrored.Filled.OpenInNew,
                contentDescription = null,
                tint = t.textMute,
                modifier = Modifier.size(15.dp),
            )
        }
        Spacer(Modifier.height(8.dp))
        Chip(a.source)
    }
}

// ── Web findings ─────────────────────────────────────────────────

/**
 * One search result.
 *
 * The query that produced it is printed on the card. A dork result is only as
 * trustworthy as the query behind it, so the query is evidence and belongs
 * next to the finding rather than in a log the user never opens.
 */
@Composable
private fun HitCard(hit: com.aryan.myrecon.data.WebSearch.Hit) {
    val t = LocalReconTokens.current
    val uri = LocalUriHandler.current
    val haptics = LocalHaptics.current

    ReconCard {
        Column(Modifier.clickable { haptics.tap(); uri.openUri(hit.url) }) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    hit.title.ifBlank { hit.host },
                    style = MaterialTheme.typography.titleSmall,
                    maxLines = 2, overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(8.dp))
                Icon(
                    Icons.AutoMirrored.Filled.OpenInNew,
                    contentDescription = null,
                    tint = t.textMute,
                    modifier = Modifier.size(15.dp),
                )
            }
            Spacer(Modifier.height(3.dp))
            Text(
                hit.url,
                style = MonoStyle,
                color = MaterialTheme.colorScheme.primary,
                maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
            if (hit.snippet.isNotBlank()) {
                Spacer(Modifier.height(7.dp))
                Text(
                    hit.snippet,
                    style = MaterialTheme.typography.bodySmall,
                    color = t.textDim,
                    maxLines = 3, overflow = TextOverflow.Ellipsis,
                )
            }
        }
        Spacer(Modifier.height(9.dp))
        ChipRow(listOf(hit.query, "via ${hit.engine}"))
    }
}

@Composable
private fun InstagramCaveat() {
    NoteCard(
        "Instagram comment text is not in any public search index — reading it needs a " +
            "signed-in session. These are the Instagram pages a search engine has indexed: " +
            "the profile, posts and reels whose caption or mentions carry the handle, and " +
            "pages elsewhere that link to it.",
        tint = LocalReconTokens.current.info,
    )
}

// ── Method ───────────────────────────────────────────────────────

/**
 * Every query in the plan, tappable.
 *
 * The app can only reach the two engines that answer without a key, and both
 * rate-limit. Google answers all of these and is one tap away in a browser, so
 * the plan is a first-class part of the result rather than debug output — it is
 * what makes the tool still useful on the run where the engines refuse.
 */
@Composable
private fun SearchPlan(plan: List<DorkPlan.Query>) {
    if (plan.isEmpty()) return
    val t = LocalReconTokens.current
    val uri = LocalUriHandler.current
    val haptics = LocalHaptics.current
    var expanded by remember { mutableStateOf(false) }

    SectionLabel("Search plan · ${plan.size} queries")
    Text(
        "${plan.count { it.executed }} ran in the app. Tap any query to run it in your " +
            "browser, where Google will answer it.",
        style = MaterialTheme.typography.bodySmall,
        color = t.textMute,
        modifier = Modifier.padding(bottom = 8.dp),
    )

    val shown = if (expanded) plan else plan.filter { it.executed }

    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, t.border, RoundedCornerShape(12.dp))
            .padding(horizontal = 12.dp, vertical = 4.dp),
    ) {
        shown.forEachIndexed { i, q ->
            if (i > 0) HorizontalDivider(color = t.border.copy(alpha = 0.5f))
            Row(
                Modifier
                    .fillMaxWidth()
                    .clickable { haptics.tap(); uri.openUri(q.google) }
                    .padding(vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                // A filled marker ran in the app; a hollow one is offered only
                // as a link. Without it an empty section is ambiguous between
                // "searched, nothing there" and "never searched".
                Box(
                    Modifier
                        .size(6.dp)
                        .clip(RoundedCornerShape(99.dp))
                        .background(if (q.executed) MaterialTheme.colorScheme.primary else t.border),
                )
                Spacer(Modifier.width(10.dp))
                Text(
                    q.text,
                    style = MonoStyle,
                    color = if (q.executed) MaterialTheme.colorScheme.onSurface else t.textDim,
                    maxLines = 2, overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(8.dp))
                Icon(
                    Icons.AutoMirrored.Filled.OpenInNew,
                    contentDescription = null,
                    tint = t.textMute,
                    modifier = Modifier.size(14.dp),
                )
            }
        }
    }

    AnimatedVisibility(visible = !expanded) {
        Text(
            "Show all ${plan.size} queries",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier
                .padding(top = 10.dp)
                .clickable { haptics.tap(); expanded = true },
        )
    }
}

@Composable
private fun Limits(notes: List<String>) {
    if (notes.isEmpty()) return
    SectionLabel("What this did not check")
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        notes.forEach { NoteCard(it) }
    }
}
