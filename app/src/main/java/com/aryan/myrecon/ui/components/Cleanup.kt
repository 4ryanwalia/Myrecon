package com.aryan.myrecon.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.data.AccountRemoval
import com.aryan.myrecon.data.ReconStore
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.Mono

/**
 * The cleanup control on one account.
 *
 * A sweep that finds eleven forgotten accounts hands the user a problem and no
 * way to work through it. Next time they open the app they get the same eleven
 * with no memory of which they already dealt with, so the second visit is worth
 * less than the first — which is a good description of an app people delete.
 *
 * Marking each one turns the result into a task list the app remembers. That is
 * the first thing here anyone would actually lose by uninstalling.
 *
 * Three states, and the third is the absence of a decision: anything not marked
 * is still to do. So an account discovered next month arrives as "needs looking
 * at" without any migration.
 */
@Composable
fun CleanupControl(
    state: ReconStore.Cleanup,
    onChange: (ReconStore.Cleanup) -> Unit,
    modifier: Modifier = Modifier,
) {
    val t = LocalReconTokens.current

    Row(modifier, horizontalArrangement = Arrangement.spacedBy(7.dp)) {
        CleanupChip(
            label = "Keeping",
            selected = state == ReconStore.Cleanup.Keeping,
            tint = t.ok,
            // Tapping the active one clears it, so a mis-tap is one tap to undo
            // rather than a state the user cannot get out of.
            onClick = {
                onChange(
                    if (state == ReconStore.Cleanup.Keeping) ReconStore.Cleanup.Todo
                    else ReconStore.Cleanup.Keeping
                )
            },
        )
        CleanupChip(
            label = "Deleted",
            selected = state == ReconStore.Cleanup.Deleted,
            tint = t.info,
            onClick = {
                onChange(
                    if (state == ReconStore.Cleanup.Deleted) ReconStore.Cleanup.Todo
                    else ReconStore.Cleanup.Deleted
                )
            },
        )
    }
}

@Composable
private fun CleanupChip(
    label: String,
    selected: Boolean,
    tint: Color,
    onClick: () -> Unit,
) {
    val t = LocalReconTokens.current
    val haptics = LocalHaptics.current

    Text(
        label,
        fontFamily = Mono,
        style = MaterialTheme.typography.labelSmall,
        color = if (selected) tint else t.textMute,
        modifier = Modifier
            .clip(RoundedCornerShape(99.dp))
            .background(if (selected) tint.copy(alpha = 0.14f) else Color.Transparent)
            .border(
                1.dp,
                if (selected) tint.copy(alpha = 0.5f) else t.border,
                RoundedCornerShape(99.dp),
            )
            .clickable { haptics.tap(); onClick() }
            // Comfortably past the 48dp minimum once the row height is counted,
            // and wide enough that the two are not easy to confuse by feel.
            .padding(horizontal = 12.dp, vertical = 7.dp),
    )
}

/**
 * Progress across the whole sweep.
 *
 * Shown above the list so the first thing a returning user sees is what they
 * have already done, not the full pile again.
 */
@Composable
fun CleanupProgress(total: Int, handled: Int, modifier: Modifier = Modifier) {
    if (total == 0) return
    val t = LocalReconTokens.current
    val done = handled.coerceAtMost(total)
    val fraction = if (total == 0) 0f else done.toFloat() / total

    Column(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, t.border, RoundedCornerShape(12.dp))
            .padding(14.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                if (done == total) "All $total accounts handled"
                else "$done of $total handled",
                style = MaterialTheme.typography.titleSmall,
            )
            Spacer(Modifier.weight(1f))
            Text(
                "${total - done} to go",
                fontFamily = Mono,
                style = MaterialTheme.typography.labelSmall,
                color = t.textMute,
            )
        }
        Spacer(Modifier.height(10.dp))
        Box(
            Modifier
                .fillMaxWidth()
                .height(6.dp)
                .clip(RoundedCornerShape(99.dp))
                .background(t.surface2),
        ) {
            Box(
                Modifier
                    .fillMaxWidth(fraction)
                    .height(6.dp)
                    .clip(RoundedCornerShape(99.dp))
                    .background(if (done == total) t.ok else MaterialTheme.colorScheme.primary),
            )
        }
        Spacer(Modifier.height(9.dp))
        Text(
            "Mark each account as kept or deleted and MyRecon remembers, so the next " +
                "scan shows you what is left rather than the whole list again.",
            style = MaterialTheme.typography.bodySmall,
            color = t.textMute,
        )
    }
}


/**
 * Help actually getting rid of the account, next to the box that marks it gone.
 *
 * Two doors, because platforms answer to different ones. Most have a deletion
 * page — buried, on an odd subdomain, and hard to find deliberately — so a
 * direct link to it is most of the work. The rest, and anything a platform
 * keeps after the account is closed, needs a written request, which people have
 * a legal right to make and almost no idea how to word.
 *
 * Shown only once someone is thinking about removal, not on every row: the list
 * from a broad sweep can run to seventy accounts, and two extra buttons on each
 * would bury the results they came for.
 */
@Composable
fun RemovalHelp(
    platform: String,
    accountUrl: String?,
    handle: String?,
    modifier: Modifier = Modifier,
) {
    val t = LocalReconTokens.current
    val haptics = LocalHaptics.current
    val uriHandler = LocalUriHandler.current
    val context = LocalContext.current
    var open by remember { mutableStateOf(false) }

    val route = remember(platform) { AccountRemoval.routeFor(platform) }

    Column(modifier.fillMaxWidth()) {
        Text(
            if (open) "Hide removal help" else "How do I delete this?",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier
                .clip(RoundedCornerShape(6.dp))
                .clickable { haptics.tap(); open = !open }
                .padding(vertical = 6.dp),
        )

        if (!open) return@Column

        Column(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(MaterialTheme.colorScheme.surface)
                .border(1.dp, t.border, RoundedCornerShape(10.dp))
                .padding(12.dp),
        ) {
            if (route != null) {
                Text(
                    "$platform has a page for this",
                    style = MaterialTheme.typography.titleSmall,
                )
                route.note?.let {
                    Spacer(Modifier.height(4.dp))
                    Text(it, style = MaterialTheme.typography.bodySmall, color = t.textDim)
                }
                Spacer(Modifier.height(9.dp))
                Text(
                    "Open the delete page",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .border(
                            1.dp,
                            MaterialTheme.colorScheme.primary.copy(alpha = 0.5f),
                            RoundedCornerShape(8.dp),
                        )
                        .clickable {
                            haptics.tap()
                            runCatching { uriHandler.openUri(route.url) }
                        }
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                )
                Spacer(Modifier.height(12.dp))
            } else {
                Text(
                    "No delete page we can point you to",
                    style = MaterialTheme.typography.titleSmall,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    "We only link pages we have checked. A wrong link sends you somewhere " +
                        "that cannot help and makes it look like the account is stuck.",
                    style = MaterialTheme.typography.bodySmall,
                    color = t.textDim,
                )
                Spacer(Modifier.height(12.dp))
            }

            Text("Ask them in writing", style = MaterialTheme.typography.titleSmall)
            Spacer(Modifier.height(4.dp))
            Text(
                "You have a legal right to have your data deleted — in India under the " +
                    "Digital Personal Data Protection Act, in the UK and EU under the " +
                    "GDPR. This writes the request for you. Send it from the email you " +
                    "signed up with, and add your name at the bottom.",
                style = MaterialTheme.typography.bodySmall,
                color = t.textDim,
            )
            AccountRemoval.suggestedContact(
                accountUrl?.substringAfter("://")?.substringBefore('/')
            )?.let {
                Spacer(Modifier.height(6.dp))
                Text(
                    "Most companies read $it — check their privacy page to be sure.",
                    style = MaterialTheme.typography.bodySmall,
                    color = t.textMute,
                )
            }
            Spacer(Modifier.height(10.dp))
            ShareButton(
                subject = "Request to delete my account and personal data",
                body = AccountRemoval.deletionRequest(platform, accountUrl, handle),
                label = "Send the request",
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}