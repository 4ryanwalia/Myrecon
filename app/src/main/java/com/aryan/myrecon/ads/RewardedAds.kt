package com.aryan.myrecon.ads

import android.app.Activity
import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.aryan.myrecon.BuildConfig
import com.google.android.gms.ads.AdRequest
import com.google.android.gms.ads.FullScreenContentCallback
import com.google.android.gms.ads.LoadAdError
import com.google.android.gms.ads.rewarded.RewardedAd
import com.google.android.gms.ads.rewarded.RewardedAdLoadCallback

/**
 * Rewarded ads.
 *
 * The highest-earning format available here — typically several times a
 * banner's eCPM — because the viewer chose to watch. That choice is also what
 * makes it permissible: AdMob requires rewarded ads to be opt-in with a real
 * decline path, and the reward must be something extra rather than access to
 * what the user already has.
 *
 * So the reward is the *deep sweep*: more platforms, checked more thoroughly.
 * The ordinary scan always runs and always shows its results. Someone who
 * declines still gets a working app; someone who accepts gets more.
 *
 * Holding a completed result hostage would invert that. It converts a reward
 * into a toll, removes the choice the policy requires, and — because a user
 * who feels trapped taps whatever dismisses the ad fastest — produces exactly
 * the accidental clicks that get an account flagged for invalid traffic.
 */
class RewardedAdManager(
    private val appContext: Context,
    /** Which unit to fill from. The app runs two: one for revealing held-back
     *  results, one for the run-an-action gate. */
    private val unitId: String = BuildConfig.AD_REWARDED_UNIT,
) {

    private var ad: RewardedAd? = null
    private var loading = false

    /** True once an ad is in memory and can be shown immediately. */
    var isReady by mutableStateOf(false)
        private set

    /**
     * Fetch an ad ahead of time.
     *
     * Called when a screen that can offer a reward appears, so the ad is
     * already resident when the user opts in. Loading on demand means a
     * multi-second stall between tapping and anything happening, which reads
     * as the app having frozen.
     */
    fun preload() {
        if (loading || ad != null) return
        loading = true
        RewardedAd.load(
            appContext,
            unitId,
            AdRequest.Builder().build(),
            object : RewardedAdLoadCallback() {
                override fun onAdLoaded(loaded: RewardedAd) {
                    ad = loaded
                    loading = false
                    isReady = true
                }

                override fun onAdFailedToLoad(error: LoadAdError) {
                    // No fill, no network, or the unit is throttled. The
                    // feature must still work — see the caller, which proceeds
                    // without the reward rather than blocking on it.
                    ad = null
                    loading = false
                    isReady = false
                }
            },
        )
    }

    /**
     * Show the ad and report whether the reward was earned.
     *
     * [onResult] receives true only when the user actually watched to the
     * point Google considers earned. Dismissing early yields false, and the
     * caller must honour that — granting the reward anyway would train users
     * to skip, and collapse the format's value.
     *
     * If no ad is available, [onResult] receives false immediately. The caller
     * decides what that means; nothing here blocks.
     */
    fun show(activity: Activity, onResult: (earned: Boolean) -> Unit) {
        val current = ad
        if (current == null) {
            preload()
            onResult(false)
            return
        }

        var earned = false
        current.fullScreenContentCallback = object : FullScreenContentCallback() {
            override fun onAdDismissedFullScreenContent() {
                ad = null
                isReady = false
                // Fetch the next one now, so a second use is instant.
                preload()
                onResult(earned)
            }

            override fun onAdFailedToShowFullScreenContent(error: com.google.android.gms.ads.AdError) {
                ad = null
                isReady = false
                preload()
                onResult(false)
            }
        }

        current.show(activity) { earned = true }
    }
}
