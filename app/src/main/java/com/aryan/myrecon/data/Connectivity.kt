package com.aryan.myrecon.data

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.distinctUntilChanged

/**
 * Whether there is any point starting a lookup.
 *
 * Without this, a username sweep with no signal does not fail — it walks 284
 * platforms one connection timeout at a time, showing a progress bar that
 * crawls to an empty result. The person watching concludes the app is broken,
 * which is a worse outcome than the honest answer they could have had
 * immediately.
 *
 * Deliberately not consulted by everything. The image reader, the QR decoder
 * and the password check all do real work offline, and blocking those behind a
 * connectivity test would take away the parts that still function.
 */
object Connectivity {

    /**
     * VALIDATED, not merely connected.
     *
     * A café or hotel Wi-Fi that has not been signed into reports a perfectly
     * healthy transport while silently swallowing every request. Checking only
     * for a connection would call that online and land us back at the timeouts
     * this exists to avoid.
     */
    fun isOnline(context: Context): Boolean {
        val manager = context.getSystemService(ConnectivityManager::class.java) ?: return true
        val caps = manager.getNetworkCapabilities(manager.activeNetwork) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

    /**
     * Live state, so an offline panel clears itself the moment signal returns.
     *
     * Someone who put the phone down on a train and picked it up in the station
     * should not have to work out that the screen needs a manual retry.
     */
    fun flow(context: Context): Flow<Boolean> = callbackFlow {
        val manager = context.getSystemService(ConnectivityManager::class.java)
        if (manager == null) {
            // No manager to ask. Assuming online is the safer failure: it lets
            // the lookup run and report its own error, rather than refusing to
            // try on a device we could not interrogate.
            trySend(true)
            awaitClose { }
            return@callbackFlow
        }

        trySend(isOnline(context))
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                trySend(isOnline(context))
            }

            override fun onLost(network: Network) {
                trySend(isOnline(context))
            }

            override fun onCapabilitiesChanged(network: Network, caps: NetworkCapabilities) {
                // The one that fires when a captive portal is finally signed
                // into: the network was already available, it just became
                // useful.
                trySend(isOnline(context))
            }
        }
        manager.registerDefaultNetworkCallback(callback)
        awaitClose { runCatching { manager.unregisterNetworkCallback(callback) } }
    }.distinctUntilChanged()
}
