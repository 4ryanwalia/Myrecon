package com.aryan.myrecon.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.data.*
import com.aryan.myrecon.ui.components.*
import com.aryan.myrecon.ui.screens.UsernameView
import com.aryan.myrecon.ui.theme.MyReconTheme

/**
 * Design previews.
 *
 * These render in Android Studio's preview pane without deploying to a device,
 * which is the fastest way to review layout and both themes side by side. They
 * use fabricated data on purpose — a preview must never depend on the network.
 */

private fun sampleProfiles(): List<Profile> = listOf(
    Profile(url = "https://github.com/torvalds", platform = "GitHub", category = "Developer", confidence = "high", exists = true),
    Profile(url = "https://gitlab.com/torvalds", platform = "GitLab", category = "Developer", confidence = "high", exists = true),
    Profile(url = "https://keybase.io/torvalds", platform = "Keybase", category = "Messaging", confidence = "high", exists = true),
    Profile(url = "https://stackoverflow.com/users/torvalds", platform = "StackOverflow", category = "Developer", confidence = "medium", exists = true),
    Profile(url = "https://www.flickr.com/people/torvalds/", platform = "Flickr", category = "Social", confidence = "medium", exists = true),
    Profile(url = "https://x.com/torvalds", platform = "Twitter / X", category = "Social", confidence = "medium", exists = true),
    Profile(url = "https://www.chess.com/member/torvalds", platform = "Chess.com", category = "Gaming", confidence = "medium", exists = true),
    Profile(url = "https://t.me/torvalds", platform = "Telegram", category = "Messaging", confidence = "unverified", exists = false),
)

private fun sampleResult() = UsernameResult(
    query = UsernameQuery("torvalds"),
    summary = UsernameSummary(total = 8, profiles = 7),
    results = UsernameBuckets(profiles = sampleProfiles()),
)

@Composable
private fun Frame(content: @Composable ColumnScope.() -> Unit) {
    Column(
        Modifier
            .background(MaterialTheme.colorScheme.background)
            .padding(16.dp)
            .verticalScroll(rememberScrollState()),
        content = content,
    )
}

// ── Full result screen ───────────────────────────────────────────

@Preview(name = "Results · dark", showBackground = true, heightDp = 1400)
@Composable
private fun PreviewResultsDark() {
    MyReconTheme(darkTheme = true) { Frame { UsernameView(sampleResult()) } }
}

@Preview(name = "Results · light", showBackground = true, heightDp = 1400)
@Composable
private fun PreviewResultsLight() {
    MyReconTheme(darkTheme = false) { Frame { UsernameView(sampleResult()) } }
}

// ── Exposure gauge, one per band ─────────────────────────────────

@Preview(name = "Gauge · low", showBackground = true, widthDp = 380)
@Composable
private fun PreviewGaugeLow() {
    MyReconTheme(darkTheme = true) {
        Frame {
            ExposureGauge(18, "Low exposure", "A small public footprint. Not much is easy to find from this handle.")
        }
    }
}

@Preview(name = "Gauge · moderate", showBackground = true, widthDp = 380)
@Composable
private fun PreviewGaugeModerate() {
    MyReconTheme(darkTheme = true) {
        Frame {
            ExposureGauge(52, "Moderate exposure", "A noticeable footprint. Worth reviewing old accounts you no longer use.")
        }
    }
}

@Preview(name = "Gauge · high (light)", showBackground = true, widthDp = 380)
@Composable
private fun PreviewGaugeHigh() {
    MyReconTheme(darkTheme = false) {
        Frame {
            ExposureGauge(84, "High exposure", "A large public footprint spanning several categories.")
        }
    }
}

// ── Radar ────────────────────────────────────────────────────────

@Preview(name = "Radar · mid-sweep", showBackground = true, widthDp = 380, heightDp = 340)
@Composable
private fun PreviewRadar() {
    MyReconTheme(darkTheme = true) {
        Frame {
            RadarScan(progress = 0.62f, found = 14, checked = 73, total = 117, currentTarget = "StackOverflow")
        }
    }
}

@Preview(name = "Radar · light", showBackground = true, widthDp = 380, heightDp = 340)
@Composable
private fun PreviewRadarLight() {
    MyReconTheme(darkTheme = false) {
        Frame {
            RadarScan(progress = 0.21f, found = 3, checked = 25, total = 117, currentTarget = "Instagram")
        }
    }
}

// ── Category tiles ───────────────────────────────────────────────

@Preview(name = "Platform tiles", showBackground = true, widthDp = 380)
@Composable
private fun PreviewTiles() {
    MyReconTheme(darkTheme = true) {
        Frame {
            listOf(
                "GitHub" to "Developer",
                "Twitter / X" to "Social",
                "Twitch" to "Video",
                "Chess.com" to "Gaming",
                "Medium" to "Blogging",
                "Etsy" to "Marketplace",
            ).chunked(3).forEach { row ->
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.padding(bottom = 10.dp)) {
                    row.forEach { (name, cat) -> PlatformTile(name, cat, size = 48) }
                }
            }
            CategoryHeader("Developer", 6)
            CategoryHeader("Social", 3)
        }
    }
}

// ── Empty and error states ───────────────────────────────────────

@Preview(name = "States", showBackground = true, widthDp = 380)
@Composable
private fun PreviewStates() {
    MyReconTheme(darkTheme = true) {
        Frame {
            StatePanel("Ready", "Pick a lookup, enter a target, and MyRecon will check public sources.")
            Spacer(Modifier.height(12.dp))
            StatePanel(
                "Nothing found",
                "No public accounts matched this handle. That is a genuinely good result if you were checking your own footprint.",
            )
        }
    }
}
