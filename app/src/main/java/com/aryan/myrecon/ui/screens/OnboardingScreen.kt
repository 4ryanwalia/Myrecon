package com.aryan.myrecon.ui.screens

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AlternateEmail
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Language
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.PersonSearch
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.components.GridBackdrop
import com.aryan.myrecon.ui.components.bracketFrame
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.Mono
import kotlinx.coroutines.launch

/**
 * The first-run intro.
 *
 * The app opened on a grid reading USERNAME / EMAIL / DOMAIN / DNS / IP / DEEP
 * SEARCH, which tells someone precisely what it queries and nothing at all
 * about why they would want it. Somebody who already knows what a DNS TXT
 * record is does not need the grid explained; everybody else bounces.
 *
 * So this is organised around jobs rather than tools. Every line on the middle
 * page is a situation a person actually finds themselves in — a stranger
 * messaged me, a QR code was stuck on a parking meter, a shop I used got
 * breached — and the tool is mentioned second, as the answer to it. The
 * mapping from job to tab is the thing worth teaching; the tabs can then be
 * named after what they query, because by that point the reader knows why.
 *
 * Three pages, skippable from the first, and reachable again afterwards from
 * the question mark in the app bar. A tutorial that can only ever be seen once
 * is a tutorial most people dismiss and then need.
 */
private data class UseCase(
    val icon: ImageVector,
    val situation: String,
    val answer: String,
    val where: String,
)

private val USE_CASES = listOf(
    UseCase(
        Icons.Filled.PersonSearch,
        "Someone messaged you and you are not sure they are real",
        "Search their name or @handle. You get the accounts that genuinely carry it, what a public record says about them, and where the story does not line up.",
        "Lookup › Deep Search",
    ),
    UseCase(
        Icons.Filled.AlternateEmail,
        "You want to know what is public about you",
        "Check your usual handle across 284 platforms and your email against known breaches. Most people find accounts they forgot they made.",
        "Lookup › Username, Email",
    ),
    UseCase(
        Icons.Filled.QrCodeScanner,
        "A QR code or link wants you to pay or sign in",
        "Scan it before you tap. You see where it really goes, how old the domain is, and whether it is impersonating something.",
        "Scan",
    ),
    UseCase(
        Icons.Filled.Lock,
        "You reuse a password and quietly know you should not",
        "Check it against 900M+ leaked credentials. It is hashed on your phone — only five characters of that hash ever leave.",
        "Password",
    ),
    UseCase(
        Icons.Filled.Language,
        "A shop, job offer or invoice looks slightly off",
        "Look up the domain. A site registered three weeks ago that cannot receive email is not the established company it claims to be.",
        "Lookup › Domain, DNS",
    ),
    UseCase(
        Icons.Filled.Image,
        "A photo might not be from where someone says",
        "Read its hidden data — camera, date, and GPS if it was left in. Runs entirely on your phone; the photo is never uploaded.",
        "Image",
    ),
)

@Composable
fun OnboardingScreen(onDone: () -> Unit) {
    val t = LocalReconTokens.current
    val haptics = LocalHaptics.current
    val pages = 3
    val pager = rememberPagerState(pageCount = { pages })
    val scope = rememberCoroutineScope()

    // A Surface, not a Box. MaterialTheme does not set LocalContentColor — a
    // Surface does — and this screen renders outside the Scaffold that normally
    // provides it, so every Text without an explicit colour was falling back to
    // black on a black background. The body copy looked fine only because it
    // sets its own colour; the headlines did not, and vanished.
    Surface(
        color = MaterialTheme.colorScheme.background,
        contentColor = MaterialTheme.colorScheme.onBackground,
        modifier = Modifier.fillMaxSize(),
    ) {
        GridBackdrop(sweep = true)

        // Edge-to-edge is on for the activity, and the Scaffold that usually
        // insets around the status bar is not in play here.
        Column(
            Modifier
                .fillMaxSize()
                .systemBarsPadding()
                .padding(horizontal = 22.dp),
        ) {
            // Skip stays available from the first page. Trapping someone in a
            // tutorial to make sure they read it is how you guarantee they do
            // not — and it is reachable again from the app bar afterwards.
            Row(Modifier.fillMaxWidth().padding(top = 14.dp)) {
                Spacer(Modifier.weight(1f))
                TextButton(onClick = { haptics.tap(); onDone() }) {
                    Text("Skip", fontFamily = Mono, color = t.textDim)
                }
            }

            HorizontalPager(
                state = pager,
                modifier = Modifier.weight(1f),
                pageSpacing = 22.dp,
            ) { page ->
                when (page) {
                    0 -> WelcomePage()
                    1 -> UseCasePage()
                    else -> PrivacyPage()
                }
            }

            // ── dots + action ────────────────────────────────────
            Row(
                Modifier.fillMaxWidth().padding(bottom = 26.dp, top = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                repeat(pages) { i ->
                    val active = pager.currentPage == i
                    val w by animateFloatAsState(if (active) 22f else 7f, label = "dot")
                    Box(
                        Modifier
                            .padding(end = 6.dp)
                            .height(4.dp)
                            .width(w.dp)
                            .clip(RoundedCornerShape(99.dp))
                            .background(
                                if (active) MaterialTheme.colorScheme.primary
                                else t.border
                            ),
                    )
                }
                Spacer(Modifier.weight(1f))
                Button(
                    onClick = {
                        haptics.tap()
                        if (pager.currentPage < pages - 1) {
                            scope.launch { pager.animateScrollToPage(pager.currentPage + 1) }
                        } else {
                            onDone()
                        }
                    },
                    shape = RoundedCornerShape(11.dp),
                ) {
                    Text(if (pager.currentPage < pages - 1) "Next" else "Start")
                }
            }
        }
    }
}

@Composable
private fun WelcomePage() {
    val t = LocalReconTokens.current
    Column(
        Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(
            Icons.Filled.Search,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(44.dp),
        )
        Spacer(Modifier.height(20.dp))
        Text(
            "Find out what the internet already knows",
            style = MaterialTheme.typography.headlineMedium,
        )
        Spacer(Modifier.height(14.dp))
        Text(
            "MyRecon looks up people, accounts, links and websites in public " +
                "records — the same sources anyone could check by hand, gathered " +
                "in one place and read for what they actually mean.",
            style = MaterialTheme.typography.bodyLarge,
            color = t.textDim,
        )
        Spacer(Modifier.height(20.dp))
        Text(
            "It finds what is already public. It does not break into anything, " +
                "and there is nothing here you could not look up yourself with " +
                "enough time.",
            style = MaterialTheme.typography.bodyMedium,
            color = t.textMute,
        )
    }
}

@Composable
private fun UseCasePage() {
    val t = LocalReconTokens.current
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        Spacer(Modifier.height(6.dp))
        Text("What people use it for", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(6.dp))
        Text(
            "Six situations, and where each one lives.",
            style = MaterialTheme.typography.bodyMedium,
            color = t.textMute,
        )
        Spacer(Modifier.height(16.dp))

        USE_CASES.forEach { c ->
            Row(Modifier.fillMaxWidth().padding(bottom = 18.dp)) {
                Icon(
                    c.icon,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(top = 2.dp).size(20.dp),
                )
                Spacer(Modifier.width(14.dp))
                Column {
                    Text(c.situation, style = MaterialTheme.typography.titleSmall)
                    Spacer(Modifier.height(3.dp))
                    Text(
                        c.answer,
                        style = MaterialTheme.typography.bodySmall,
                        color = t.textDim,
                    )
                    Spacer(Modifier.height(5.dp))
                    Text(
                        c.where.uppercase(),
                        fontFamily = Mono,
                        style = MaterialTheme.typography.labelSmall,
                        color = t.textMute,
                    )
                }
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun PrivacyPage() {
    val t = LocalReconTokens.current
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(
            Icons.Filled.Shield,
            contentDescription = null,
            tint = t.ok,
            modifier = Modifier.size(40.dp),
        )
        Spacer(Modifier.height(18.dp))
        Text("Most of it never leaves your phone", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(14.dp))

        // Each claim is specific and checkable. A vague privacy promise is
        // worth nothing on a tool like this, and a precise one is the whole
        // reason to trust it over a website that logs what you searched.
        listOf(
            "Username, email, domain, DNS and IP lookups run from this device, straight to the public source.",
            "Photos are read on the phone. The image is never uploaded anywhere.",
            "Passwords are hashed locally — only the first five characters of the hash are sent, so nobody learns what you typed.",
            "Nothing you search is stored on a MyRecon server, because for these lookups there is no MyRecon server involved.",
        ).forEach { line ->
            Row(Modifier.fillMaxWidth().padding(bottom = 12.dp)) {
                Box(
                    Modifier
                        .padding(top = 7.dp)
                        .size(5.dp)
                        .clip(RoundedCornerShape(99.dp))
                        .background(t.ok),
                )
                Spacer(Modifier.width(12.dp))
                Text(line, style = MaterialTheme.typography.bodyMedium, color = t.textDim)
            }
        }

        Spacer(Modifier.height(14.dp))
        Column(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(3.dp))
                .background(t.bgSoft)
                .bracketFrame(t.warn.copy(alpha = 0.6f))
                .padding(15.dp),
        ) {
            Text("Use it on people, carefully", style = MaterialTheme.typography.titleSmall)
            Spacer(Modifier.height(6.dp))
            Text(
                "Accounts sharing a handle often belong to different people, and a " +
                    "match is evidence rather than proof. MyRecon shows you how " +
                    "confident it is and why — read that before you conclude anything " +
                    "about a real person.",
                style = MaterialTheme.typography.bodySmall,
                color = t.textDim,
                textAlign = TextAlign.Start,
            )
        }
        Spacer(Modifier.height(10.dp))
    }
}
