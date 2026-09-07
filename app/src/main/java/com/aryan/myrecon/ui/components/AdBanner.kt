package com.aryan.myrecon.ui.components

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
import android.util.Log
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.aryan.myrecon.BuildConfig
import com.aryan.myrecon.ads.Ads
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.Mono
import com.google.android.gms.ads.AdRequest
import com.google.android.gms.ads.AdSize
import com.google.android.gms.ads.AdView
import com.google.android.gms.ads.AdListener
import com.google.android.gms.ads.LoadAdError

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
/** AdMob's recommended banner refresh interval. Below 30s breaches policy. */
private const val REFRESH_INTERVAL_MS = 60_000L

@Composable
fun AdBanner(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val t = LocalReconTokens.current

    // Disabled entirely in the screenshots variant, and nothing is drawn — not
    // even reserved space — so listing images show the app as users would see
    // it once the banner has loaded out of the way.
    if (!BuildConfig.SHOW_ADS) return

    // Previews and tests must not attempt a real ad fetch.
    if (LocalInspectionMode.current) {
        AdPlaceholder(modifier)
        return
    }

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

        // Held so the refresh loop can reload the same view rather than
        // recreating it, which would flash and lose the current impression.
        var adView by remember { mutableStateOf<AdView?>(null) }

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
                    // A failed banner used to fail silently, which made this
                    // indistinguishable from a layout bug. Now it says why.
                    adListener = object : AdListener() {
                        override fun onAdFailedToLoad(error: LoadAdError) {
                            Log.w(
                                "MyReconAds",
                                "banner load failed: ${Ads.describe(error.code)} — ${error.message}",
                            )
                        }

                        override fun onAdLoaded() {
                            Log.i("MyReconAds", "banner loaded")
                        }
                    }
                    // Deliberately no loadAd() here. The request is made below,
                    // once the SDK reports ready — requesting from the factory
                    // raced MobileAds.initialize and the request was discarded.
                    adView = this
                }
            },
        )

        // Refresh on a 60s cycle: more impressions per session, and 60s is
        // AdMob's own recommended interval. Faster is counter-productive — under
        // 30s breaches policy outright, and even 30-60s tends to lower eCPM
        // because advertisers see impressions nobody had time to read.
        //
        // This must be the ONLY refresh in play. If auto-refresh is also
        // enabled for this unit in the AdMob console, the two compound into a
        // faster effective rate than either intends, which is a policy problem.
        // Console auto-refresh should be set to Disabled for this unit.
        LaunchedEffect(adView) {
            val view = adView ?: return@LaunchedEffect
            Ads.awaitReady(context)
            runCatching { view.loadAd(AdRequest.Builder().build()) }
            while (true) {
                kotlinx.coroutines.delay(REFRESH_INTERVAL_MS)
                runCatching { view.loadAd(AdRequest.Builder().build()) }
            }
        }

        // Banners hold a live connection; pausing with the host stops them
        // burning battery and requesting impressions nobody can see.
        val lifecycle = LocalLifecycleOwner.current.lifecycle
        DisposableEffect(lifecycle, adView) {
            val observer = LifecycleEventObserver { _, event ->
                when (event) {
                    Lifecycle.Event.ON_RESUME -> adView?.resume()
                    Lifecycle.Event.ON_PAUSE -> adView?.pause()
                    else -> Unit
                }
            }
            lifecycle.addObserver(observer)
            onDispose {
                lifecycle.removeObserver(observer)
                adView?.destroy()
            }
        }
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
