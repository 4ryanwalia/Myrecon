package com.aryan.myrecon.ads

import android.content.Context
import android.util.Log
import com.google.android.gms.ads.AdRequest
import com.google.android.gms.ads.MobileAds
import com.google.android.gms.ads.RequestConfiguration
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.concurrent.atomic.AtomicBoolean

/**
 * One place that starts the ad SDK, and one thing to await before loading.
 *
 * This exists because of a real bug. Initialisation used to be kicked off from
 * inside the banner composable, on a bare background thread, with nothing to
 * wait on — and then both the banner's `loadAd` and the rewarded pre-load fired
 * immediately afterwards. Every ad request in the app was racing
 * `MobileAds.initialize`, and a request that wins that race is simply lost. It
 * happened to work on a fast emulator and not on a handset, which is exactly
 * how a race behaves.
 *
 * So: the Application starts it once, and every ad path suspends on [awaitReady]
 * first. Nothing requests an ad until the SDK says it is ready.
 */
object Ads {

    private const val TAG = "MyReconAds"

    private val started = AtomicBoolean(false)
    private val ready = CompletableDeferred<Unit>()

    /**
     * Devices that must never generate a billable impression.
     *
     * The live ad unit is used in every build, debug included, so the only
     * protection is listing the device here — Google then serves it test
     * creatives. The unit is exercised end to end, nothing is billed, and
     * nothing counts as invalid traffic, which is the usual reason an AdMob
     * account gets suspended.
     *
     * To add a handset, run the app and look for this line in logcat:
     *
     *   Use RequestConfiguration.Builder().setTestDeviceIds(Arrays.asList("33BE…"))
     *
     * EMULATOR covers the emulator. A physical phone is NOT protected until its
     * hash is added below, and will request live ads.
     */
    private val TEST_DEVICE_IDS = listOf(
        AdRequest.DEVICE_ID_EMULATOR,
        // TODO: add the hash this device logs on first run — see above.
    )

    /** Start the SDK. Safe to call more than once; only the first call works. */
    fun start(context: Context) {
        if (!started.compareAndSet(false, true)) return
        val app = context.applicationContext

        MobileAds.setRequestConfiguration(
            RequestConfiguration.Builder()
                .setTestDeviceIds(TEST_DEVICE_IDS)
                // A general-purpose security tool, not directed at children.
                // Declaring it explicitly keeps serving compliant rather than
                // leaving it unspecified.
                .setTagForChildDirectedTreatment(
                    RequestConfiguration.TAG_FOR_CHILD_DIRECTED_TREATMENT_FALSE
                )
                .setMaxAdContentRating(RequestConfiguration.MAX_AD_CONTENT_RATING_T)
                .build()
        )

        // initialize() does disk and network work but hands off internally; the
        // callback is what actually says the SDK is usable.
        MobileAds.initialize(app) { status ->
            status.adapterStatusMap.forEach { (adapter, state) ->
                Log.i(TAG, "adapter $adapter: ${state.initializationState} (${state.description})")
            }
            ready.complete(Unit)
        }
    }

    /**
     * Suspend until the SDK is ready to take a request.
     *
     * Callers that reach this before [start] has run — a composable racing
     * Application.onCreate on a cold start — trigger it themselves rather than
     * waiting forever.
     */
    suspend fun awaitReady(context: Context) {
        start(context)
        if (!ready.isCompleted) withContext(Dispatchers.Default) { ready.await() }
    }

    /** True once the SDK has reported ready, without suspending. */
    val isReady: Boolean get() = ready.isCompleted

    /** Human-readable AdMob error codes, so a failure says what went wrong. */
    fun describe(code: Int): String = when (code) {
        0 -> "internal error"
        1 -> "invalid request — check the ad unit ID belongs to this app"
        2 -> "network error"
        3 -> "no fill — no advertiser bid for this request"
        8 -> "app ID missing or wrong in the manifest"
        9 -> "mediation returned no fill"
        else -> "error code $code"
    }
}
