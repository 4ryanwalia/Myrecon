package com.aryan.myrecon.ads

import android.app.Activity
import android.content.Context
import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.aryan.myrecon.BuildConfig
import com.google.android.gms.ads.AdRequest
import com.google.android.gms.ads.FullScreenContentCallback
import com.google.android.gms.ads.LoadAdError
import com.google.android.gms.ads.rewarded.RewardedAd
import com.google.android.gms.ads.rewarded.RewardedAdLoadCallback
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Rewarded ads.
 *
 * The highest-earning format available here — typically several times a
 * banner's eCPM — because the viewer chose to watch. That choice is also what
 * makes it permissible: AdMob requires rewarded ads to be opt-in with a real
 * decline path, and the reward must be something the user agreed to trade for.
 *
 * Holding a completed result hostage would invert that. It converts a reward
 * into a toll, removes the choice the policy requires, and — because a user who
 * feels trapped taps whatever dismisses the ad fastest — produces exactly the
 * accidental clicks that get an account flagged for invalid traffic.
 *
 * Two things here were bugs, and both had the same symptom of "ads just never
 * appear":
 *
 *   • **Loading before the SDK was ready.** `preload()` fired the moment a
 *     screen composed, racing `MobileAds.initialize`. A request that loses that
 *     race is discarded. It now waits on [Ads.awaitReady] first.
 *   • **Never retrying.** One failed load left `isReady` false for the rest of
 *     the session, so the gate silently stopped offering ads. A no-fill is
 *     normal and temporary — especially on a new ad unit — so it now retries
 *     with backoff instead of giving up permanently.
 */
class RewardedAdManager(
    private val appContext: Context,
    /** Which unit to fill from. The app runs two: one for revealing held-back
     *  results, one for the run-an-action gate. */
    private val unitId: String = BuildConfig.AD_REWARDED_UNIT,
) {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    private var ad: RewardedAd? = null
    private var loading = false
    private var attempts = 0

    /** True once an ad is in memory and can be shown immediately. */
    var isReady by mutableStateOf(false)
        private set

    /**
     * Fetch an ad ahead of time.
     *
     * Called when a screen that can offer a reward appears, so the ad is
     * already resident when the user opts in. Loading on demand means a
     * multi-second stall between tapping and anything happening, which reads as
     * the app having frozen.
     */
    fun preload() {
        if (loading || ad != null) return
        loading = true
        scope.launch {
            // The whole point: never request before the SDK can serve.
            Ads.awaitReady(appContext)
            load()
        }
    }

    private fun load() {
        RewardedAd.load(
            appContext,
            unitId,
            AdRequest.Builder().build(),
            object : RewardedAdLoadCallback() {
                override fun onAdLoaded(loaded: RewardedAd) {
                    ad = loaded
                    loading = false
                    attempts = 0
                    isReady = true
                    Log.i(TAG, "rewarded ad ready ($unitId)")
                }

                override fun onAdFailedToLoad(error: LoadAdError) {
                    ad = null
                    isReady = false
                    Log.w(
                        TAG,
                        "rewarded load failed ($unitId): ${Ads.describe(error.code)} — ${error.message}",
                    )
                    // No fill, no network, or a unit that has not started
                    // serving yet. All three recover on their own, so back off
                    // and try again rather than disabling the feature for the
                    // session. Capped so a genuinely dead unit is not hammered.
                    if (attempts < MAX_ATTEMPTS) {
                        attempts += 1
                        val backoff = RETRY_BASE_MS * (1L shl (attempts - 1))
                        scope.launch {
                            delay(backoff)
                            load()
                        }
                    } else {
                        loading = false
                        Log.w(TAG, "rewarded gave up after $attempts attempts ($unitId)")
                    }
                }
            },
        )
    }

    /**
     * Show the ad and report whether the reward was earned.
     *
     * [onResult] receives true only when the user actually watched to the point
     * Google considers earned. Dismissing early yields false, and the caller
     * must honour that — granting the reward anyway would train users to skip
     * and collapse the format's value.
     *
     * If no ad is available, [onResult] receives false immediately. The caller
     * decides what that means; nothing here blocks.
     */
    fun show(activity: Activity, onResult: (earned: Boolean) -> Unit) {
        val current = ad
        if (current == null) {
            attempts = 0
            preload()
            onResult(false)
            return
        }

        var earned = false
        current.fullScreenContentCallback = object : FullScreenContentCallback() {
            override fun onAdDismissedFullScreenContent() {
                ad = null
                isReady = false
                loading = false
                attempts = 0
                // Fetch the next one now, so a second use is instant.
                preload()
                onResult(earned)
            }

            override fun onAdFailedToShowFullScreenContent(error: com.google.android.gms.ads.AdError) {
                Log.w(TAG, "rewarded failed to show: ${error.message}")
                ad = null
                isReady = false
                loading = false
                attempts = 0
                preload()
                onResult(false)
            }
        }

        current.show(activity) { earned = true }
    }

    private companion object {
        const val TAG = "MyReconAds"
        const val MAX_ATTEMPTS = 4
        const val RETRY_BASE_MS = 4_000L
    }
}
