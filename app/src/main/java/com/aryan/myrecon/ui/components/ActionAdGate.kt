package com.aryan.myrecon.ui.components

import android.app.Activity
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayCircleOutline
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.BuildConfig
import com.aryan.myrecon.ads.RewardedAdManager
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.theme.LocalReconTokens

/**
 * Runs an action behind a rewarded ad, with the opt-in on the button itself.
 *
 * AdMob requires a rewarded ad to be chosen rather than sprung, and the usual
 * way to satisfy that is a confirmation sheet. A sheet is not the only way, and
 * here it is the worse one: it puts a second tap in front of every single
 * search for a decision the user already made. What the policy actually needs
 * is that nobody is surprised — so the *button* carries the play icon and the
 * line underneath says an ad runs first. The affordance declares itself before
 * it is touched, which is the same informed choice with none of the ceremony.
 *
 * The marker is not decoration, and this is the part worth getting right: it
 * appears **only when an ad is actually loaded**. If nothing filled, the button
 * is an ordinary button and the action runs immediately. So the icon is a
 * promise the app always keeps, in both directions — icon means an ad plays,
 * no icon means none does. A badge that lied half the time would train people
 * to ignore it, and that is precisely when a full-screen video becomes a
 * surprise again.
 *
 * Two rules the gate never breaks, both of which protect revenue rather than
 * limit it:
 *
 *   • **A missing ad never blocks the action.** No fill, offline, or a
 *     throttled unit means the lookup simply runs. An app that appears broken
 *     gets uninstalled, and an uninstalled app shows nobody any ads.
 *   • **Closing the ad early earns nothing.** Google reports the reward only
 *     when it was watched, and honouring that is what stops the format
 *     collapsing into a skip button. The SDK warns before an early close, so
 *     nobody loses a search without being told.
 */
@Stable
class ActionAdGateState internal constructor(
    internal val manager: RewardedAdManager,
) {
    /** True while an ad is on screen, so callers can disable their control. */
    var showing by mutableStateOf(false)
        internal set

    /**
     * True when tapping will actually play an ad.
     *
     * Drives the marker. False with ads disabled, or whenever nothing is
     * loaded — in both cases the action runs straight away.
     */
    val willShowAd: Boolean get() = BuildConfig.SHOW_ADS && manager.isReady

    /**
     * Play the ad if there is one, then run [action].
     *
     * Safe to call from any button: with no ad, no activity, or ads disabled,
     * this is a direct call.
     */
    fun run(activity: Activity?, onEarned: () -> Unit, action: () -> Unit) {
        if (!willShowAd || activity == null) {
            action()
            return
        }
        showing = true
        manager.show(activity) { earned ->
            showing = false
            if (earned) {
                onEarned()
                action()
            }
            // Not earned: the user closed it early after the SDK's warning.
            // Nothing runs, and the next tap offers the same trade again.
        }
    }
}

@Composable
fun rememberActionAdGate(
    unitId: String = BuildConfig.AD_REWARDED_ACTION_UNIT,
): ActionAdGateState {
    val context = LocalContext.current
    val state = remember(unitId) {
        ActionAdGateState(RewardedAdManager(context.applicationContext, unitId))
    }
    // Fetch ahead of the tap. Loading on demand puts a multi-second stall
    // between the button and anything happening, which reads as a freeze — and
    // an ad that arrives late is one the marker already promised.
    LaunchedEffect(state) { if (BuildConfig.SHOW_ADS) state.manager.preload() }
    return state
}

/**
 * The play icon that goes inside a gated button, ahead of its label.
 *
 * Rendered by the caller rather than injected, so a button keeps its own
 * colours and shape.
 */
@Composable
fun AdMarker(visible: Boolean, modifier: Modifier = Modifier) {
    if (!visible) return
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        Icon(
            Icons.Filled.PlayCircleOutline,
            contentDescription = "Plays a short ad first",
            modifier = Modifier.size(18.dp),
        )
        Spacer(Modifier.width(7.dp))
    }
}

/**
 * The line under a gated button.
 *
 * Says what the icon means, once, quietly. It animates in and out with
 * availability so it is never claiming something that is not true.
 */
@Composable
fun AdGateHint(gate: ActionAdGateState, modifier: Modifier = Modifier) {
    val t = LocalReconTokens.current
    AnimatedVisibility(visible = gate.willShowAd, modifier = modifier) {
        Text(
            "A short ad plays first — it keeps MyRecon free and unlimited.",
            style = MaterialTheme.typography.bodySmall,
            color = t.textMute,
            modifier = Modifier.padding(top = 8.dp),
        )
    }
}

/**
 * A whole gated button, for the plain cases.
 *
 * The lookup screen composes its own — it has a cancel state and bespoke
 * colours — but "Analyse another photo" and "Scan another" are ordinary
 * buttons and should not each reimplement this.
 */
@Composable
fun AdActionButton(
    gate: ActionAdGateState,
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val haptics = LocalHaptics.current

    Button(
        onClick = {
            haptics.tap()
            gate.run(
                activity = context as? Activity,
                onEarned = { haptics.complete() },
                action = onClick,
            )
        },
        enabled = !gate.showing,
        shape = RoundedCornerShape(11.dp),
        modifier = modifier,
    ) {
        AdMarker(visible = gate.willShowAd)
        Text(if (gate.showing) "Loading…" else label)
    }
    AdGateHint(gate)
    Spacer(Modifier.height(2.dp))
}
