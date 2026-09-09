package com.aryan.myrecon.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
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
