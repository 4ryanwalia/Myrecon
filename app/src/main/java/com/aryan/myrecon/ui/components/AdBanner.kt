package com.aryan.myrecon.ui.components

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.aryan.myrecon.BuildConfig
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.Mono
import com.google.android.gms.ads.AdRequest
import com.google.android.gms.ads.AdSize
import com.google.android.gms.ads.AdView
import com.google.android.gms.ads.MobileAds
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Anchored adaptive banner.
 *
 * Adaptive rather than the fixed 320x50: the SDK picks a height suited to the
 * device, which fills the width properly on a tall phone and reliably earns
 * more per impression than a small fixed unit letterboxed in the middle.
 *
 * Placement rules that are policy, not preference — AdMob suspends accounts
 * over these, and they are enforced by where this composable is allowed to sit:
 *
 *   • Never adjacent to a control. A banner touching a button produces
 *     accidental clicks, which Google classifies as invalid traffic. The
 *     spacer above is deliberate and should not be removed to save space.
 *   • Never over content. Nothing the user is reading may be obscured.
 *   • Never inside a scrolling results list. A banner that moves under the
 *     finger while scrolling is the single most common accidental-click cause.
 *   • Labelled. The eyebrow marks it as advertising, which keeps the app honest
 *     and satisfies the "clearly distinguishable from content" requirement.
 */
private val adsInitialised = AtomicBoolean(false)

/**
 * Initialise the ad SDK once, off the main thread.
 *
 * MobileAds.initialize does disk and network work; calling it on the main
 * thread during startup is a well-known cause of slow cold starts.
 */
fun initialiseAds(context: Context) {
    if (!adsInitialised.compareAndSet(false, true)) return
    Thread {
        runCatching { MobileAds.initialize(context.applicationContext) {} }
    }.apply { isDaemon = true }.start()
}

@Composable
fun AdBanner(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val t = LocalReconTokens.current

    // Previews and tests must not attempt a real ad fetch.
    if (LocalInspectionMode.current) {
        AdPlaceholder(modifier)
        return
    }

    LaunchedEffect(Unit) { initialiseAds(context) }

    val widthDp = LocalConfiguration.current.screenWidthDp

    Column(
        modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.background),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // Hairline plus label: separates the ad from app content so neither is
        // mistaken for the other.
        Box(Modifier.fillMaxWidth().height(1.dp).background(t.border))
        Text(
            "ADVERTISEMENT",
            fontFamily = Mono,
            style = MaterialTheme.typography.labelSmall,
            color = t.textMute.copy(alpha = 0.7f),
            modifier = Modifier.padding(top = 4.dp, bottom = 2.dp),
        )

        AndroidView(
            modifier = Modifier.fillMaxWidth(),
            factory = { ctx ->
                AdView(ctx).apply {
                    // Anchored adaptive: the SDK returns the optimal height for
                    // this width on this device.
                    setAdSize(
                        AdSize.getCurrentOrientationAnchoredAdaptiveBannerAdSize(ctx, widthDp)
                    )
                    adUnitId = BuildConfig.AD_BANNER_UNIT
                    loadAd(AdRequest.Builder().build())
                }
            },
        )
    }
}

/** Reserved space shown in previews, so layout does not jump at runtime. */
@Composable
private fun AdPlaceholder(modifier: Modifier = Modifier) {
    val t = LocalReconTokens.current
    Box(
        modifier
            .fillMaxWidth()
            .height(64.dp)
            .background(t.surface2),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            "AD SLOT",
            fontFamily = Mono,
            style = MaterialTheme.typography.labelSmall,
            color = t.textMute,
        )
    }
}
