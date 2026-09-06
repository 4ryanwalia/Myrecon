package com.aryan.myrecon.ui.components

import android.app.Activity
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayCircleOutline
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.BuildConfig
import com.aryan.myrecon.ads.RewardedAdManager
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.pressScale
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.Mono

/**
 * Offers the remaining results in exchange for watching a rewarded ad.
 *
 * One account per category is shown up front; the rest are revealed on opt-in.
 * That is the ordinary preview-and-unlock pattern rewarded ads exist for, and
 * it stays inside AdMob policy for three specific reasons, each of which is
 * load-bearing:
 *
 *   • Something useful is already visible. The user can see what was found and
 *     in which categories before deciding.
 *   • Declining is a plainly-labelled option that leaves the preview intact.
 *     An offer with no way out is not an offer, and policy requires the choice.
 *   • A failed or unavailable ad unlocks everything anyway (see [onGranted]
 *     callers). Nobody is ever stuck behind an ad that will not load — which
 *     also matters commercially, because a trapped user taps whatever closes
 *     the screen fastest and that is exactly the accidental-click pattern that
 *     gets an account flagged for invalid traffic.
 *
 * @param hiddenCount how many results remain, stated plainly so the trade is
 *   clear before the user commits to watching anything.
 */
@Composable
fun UnlockResultsOffer(
    manager: RewardedAdManager,
    hiddenCount: Int,
    onGranted: () -> Unit,
    onDeclined: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val t = LocalReconTokens.current
    val haptics = LocalHaptics.current
    val accent = MaterialTheme.colorScheme.primary
    val source = remember { MutableInteractionSource() }

    // With ads off (screenshots variant) there is nothing to trade, so
    // everything is simply unlocked rather than gated behind an offer that
    // cannot be accepted.
    LaunchedEffect(Unit) {
        if (!BuildConfig.SHOW_ADS) onGranted()
    }
    if (!BuildConfig.SHOW_ADS) return

    var showing by remember { mutableStateOf(false) }

    // Fetch ahead of the tap so opting in is instant rather than a stall that
    // reads as the app freezing.
    LaunchedEffect(Unit) { manager.preload() }

    Column(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(3.dp))
            .background(MaterialTheme.colorScheme.surface)
            .bracketFrame(accent.copy(alpha = 0.6f))
            .padding(15.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                Icons.Filled.PlayCircleOutline,
                contentDescription = null,
                tint = accent,
                modifier = Modifier.size(22.dp),
            )
            Spacer(Modifier.width(11.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    "$hiddenCount more account${if (hiddenCount == 1) "" else "s"} found",
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    "Watch this ad to see all of them",
                    style = MaterialTheme.typography.bodySmall,
                    color = t.textMute,
                )
            }
        }

        Spacer(Modifier.height(13.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
            Button(
                onClick = {
                    haptics.tap()
                    val activity = context as? Activity
                    if (activity == null) {
                        // No activity to present on — unlock rather than leave
                        // the user staring at a button that does nothing.
                        onGranted()
                        return@Button
                    }
                    showing = true
                    if (!manager.isReady) {
                        // Nothing loaded: no fill, offline, or the unit is
                        // throttled. Unlock instead of blocking. Ad revenue is
                        // worth less than a user who thinks the app is broken.
                        showing = false
                        onGranted()
                        return@Button
                    }
                    manager.show(activity) { earned ->
                        showing = false
                        // Watched in full: reveal. Dismissed early: the offer
                        // stays, so skipping is not a shortcut to the reward.
                        if (earned) {
                            haptics.complete()
                            onGranted()
                        }
                    }
                },
                enabled = !showing,
                shape = RoundedCornerShape(3.dp),
                modifier = Modifier
                    .weight(1f)
                    .pressScale(source),
            ) {
                Text(
                    if (showing) "Loading…" else "Watch ad · reveal all",
                    fontFamily = Mono,
                    style = MaterialTheme.typography.labelLarge,
                )
            }

            // The decline path. Required by policy, and deliberately not buried
            // — the preview stays exactly as it is.
            TextButton(
                onClick = { haptics.tap(); onDeclined() },
                shape = RoundedCornerShape(3.dp),
            ) {
                Text("Not now", fontFamily = Mono, color = t.textDim)
            }
        }

        Spacer(Modifier.height(9.dp))
        Text(
            "One account per category is shown below. Nothing is sent anywhere " +
                "either way — the scan already ran on this device.",
            style = MaterialTheme.typography.bodySmall,
            color = t.textMute,
        )
    }
}
