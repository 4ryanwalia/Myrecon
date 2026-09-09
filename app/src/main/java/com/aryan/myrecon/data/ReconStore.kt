package com.aryan.myrecon.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * Local persistence.
 *
 * DataStore rather than Room: this is three small lists, and Room would mean a
 * KSP compiler plugin and a schema for what fits comfortably in JSON.
 *
 * Two jobs. First, remembering which breaches have already been reported, so a
 * notification only ever fires for something genuinely new. Second, keeping the
 * last scan, which is what stops a result disappearing when the app is
 * backgrounded — that survives process death too, where holding it in a
 * ViewModel would not.
 */
private val Context.dataStore by preferencesDataStore("myrecon")

@Serializable
data class SavedScan(
    val handle: String,
    val at: Long,
    val profiles: List<SavedProfile>,
)

@Serializable
data class SavedProfile(
    val platform: String,
    val category: String,
    val url: String,
    val confidence: String,
    val avatar: String? = null,
    val displayName: String? = null,
)

class ReconStore(private val context: Context) {

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    private object Keys {
        val SEEN_BREACHES = stringSetPreferencesKey("seen_breaches")
        val WATCHED_EMAILS = stringSetPreferencesKey("watched_emails")
        val WATCHED_HANDLES = stringSetPreferencesKey("watched_handles")
        val LAST_SCAN = stringPreferencesKey("last_scan")
        val LAST_CHECK = stringPreferencesKey("last_breach_check")

        /**
         * Consent to send watched addresses to the lookup service.
         *
         * Separate from the watchlist itself, and required on top of it. The
         * catalogue check transmits nothing; per-address checking does, and one
         * switch must never silently buy the other.
         */
        val EMAIL_MONITORING = stringPreferencesKey("email_monitoring_consent")

        /** Corpora already reported for one address, so alerts stay novel. */
        fun seenSources(email: String) = stringSetPreferencesKey("seen_sources_$email")

        /**
         * Whether breach alerts are on.
         *
         * The switch used to be `rememberSaveable`, which meant it read as off
         * on every cold start while the worker was still happily scheduled —
         * the control disagreed with the behaviour.
         */
        val ALERTS = stringPreferencesKey("alerts_enabled")

        /**
         * Profile URLs already reported for one handle.
         *
         * The baseline that makes "a new account appeared under your handle"
         * a statement about change rather than a re-listing of the same sweep.
         */
        fun seenProfiles(handle: String) = stringSetPreferencesKey("seen_profiles_$handle")

        /**
         * Cleanup progress, as two sets of profile URLs per handle.
         *
         * Two sets rather than a url→status map because the third state is the
         * absence of a decision: anything in neither set is still to do. That
         * makes a newly-discovered account default to "needs looking at"
         * without any migration, which a stored enum would not.
         */
        fun cleanupKept(handle: String) = stringSetPreferencesKey("cleanup_kept_$handle")
        fun cleanupDone(handle: String) = stringSetPreferencesKey("cleanup_done_$handle")

        /**
         * Whether the intro has been completed or skipped.
         *
         * Versioned in the key rather than stored as a number: if the intro
         * changes enough to be worth showing again, bump to `_v2` and everyone
         * sees the new one once. Reusing the key would silently hide it.
         */
        val ONBOARDED = stringPreferencesKey("onboarded_v1")
    }

    // ── First run ────────────────────────────────────────────────

    /**
     * False until the intro has been seen.
     *
     * Read as a flow so the very first frame can decide what to show without a
     * blocking read on the main thread; null means "not loaded yet", which the
     * caller renders as nothing rather than as the intro. Flashing the intro at
     * a returning user for one frame is worse than a beat of blank.
     */
    val onboarded: Flow<Boolean> = context.dataStore.data
        .map { it[Keys.ONBOARDED] == "true" }

    suspend fun setOnboarded(done: Boolean) {
        context.dataStore.edit { prefs ->
            if (done) prefs[Keys.ONBOARDED] = "true" else prefs.remove(Keys.ONBOARDED)
        }
    }

    // ── Breach alerting ──────────────────────────────────────────

    suspend fun seenBreaches(): Set<String> =
        context.dataStore.data.first()[Keys.SEEN_BREACHES] ?: emptySet()

    /**
     * Records the whole catalogue as seen.
     *
     * Called with every known breach on first run *without* notifying, so a new
     * install does not immediately fire an alert for a thousand historical
     * breaches. Only what appears after that point is new.
     */
    suspend fun markSeen(names: Collection<String>) {
        context.dataStore.edit { prefs ->
            prefs[Keys.SEEN_BREACHES] = (prefs[Keys.SEEN_BREACHES] ?: emptySet()) + names
        }
    }

    suspend fun hasBaseline(): Boolean = seenBreaches().isNotEmpty()

    suspend fun recordCheck(at: Long = System.currentTimeMillis()) {
        context.dataStore.edit { it[Keys.LAST_CHECK] = at.toString() }
    }

    val lastCheck: Flow<Long?> = context.dataStore.data
        .map { it[Keys.LAST_CHECK]?.toLongOrNull() }

    // ── Watchlist ────────────────────────────────────────────────

    val watchedEmails: Flow<Set<String>> = context.dataStore.data
        .map { it[Keys.WATCHED_EMAILS] ?: emptySet() }

    suspend fun watchEmail(email: String) {
        val clean = email.trim().lowercase()
        if (clean.isBlank()) return
        context.dataStore.edit { prefs ->
            prefs[Keys.WATCHED_EMAILS] = (prefs[Keys.WATCHED_EMAILS] ?: emptySet()) + clean
        }
    }

    suspend fun unwatchEmail(email: String) {
        val clean = email.trim().lowercase()
        context.dataStore.edit { prefs ->
            prefs[Keys.WATCHED_EMAILS] = (prefs[Keys.WATCHED_EMAILS] ?: emptySet()) - clean
            // Drop the per-address history too. Leaving it behind would keep a
            // record of an address the user just asked to stop watching, and
            // would silently suppress alerts if they ever re-added it.
            prefs.remove(Keys.seenSources(clean))
        }
    }

    // ── Per-address monitoring (transmits; opt-in) ───────────────

    /**
     * Whether the user has agreed to send watched addresses to the lookup
     * service. Defaults to false and is asked for separately from the
     * catalogue alerts, which never transmit anything.
     */
    val emailMonitoring: Flow<Boolean> = context.dataStore.data
        .map { it[Keys.EMAIL_MONITORING] == "true" }

    suspend fun setEmailMonitoring(on: Boolean) {
        context.dataStore.edit { prefs ->
            if (on) {
                prefs[Keys.EMAIL_MONITORING] = "true"
            } else {
                // Revoking clears every per-address history as well, so turning
                // it back on re-baselines instead of replaying old findings.
                prefs.remove(Keys.EMAIL_MONITORING)
                (prefs[Keys.WATCHED_EMAILS] ?: emptySet()).forEach {
                    prefs.remove(Keys.seenSources(it))
                }
            }
        }
    }

    suspend fun isEmailMonitoringOn(): Boolean =
        context.dataStore.data.first()[Keys.EMAIL_MONITORING] == "true"

    suspend fun seenSourcesFor(email: String): Set<String> =
        context.dataStore.data.first()[Keys.seenSources(email.trim().lowercase())] ?: emptySet()

    suspend fun markSourcesSeen(email: String, names: Collection<String>) {
        val key = Keys.seenSources(email.trim().lowercase())
        context.dataStore.edit { prefs ->
            prefs[key] = (prefs[key] ?: emptySet()) + names
        }
    }

    /**
     * True once an address has been checked at least once.
     *
     * The first check records what is already known *without* alerting: a newly
     * watched address is usually in several old breaches, and opening with a
     * push about a 2018 dump is noise, not news. Only what appears afterwards
     * is worth interrupting for. The existing exposure is shown on screen
     * instead, where the user asked for it.
     */
    suspend fun hasBaselineFor(email: String): Boolean =
        context.dataStore.data.first()
            .contains(Keys.seenSources(email.trim().lowercase()))

    val watchedHandles: Flow<Set<String>> = context.dataStore.data
        .map { it[Keys.WATCHED_HANDLES] ?: emptySet() }

    suspend fun watchHandle(handle: String) {
        val clean = handle.trim().removePrefix("@").lowercase()
        if (clean.isBlank()) return
        context.dataStore.edit { prefs ->
            prefs[Keys.WATCHED_HANDLES] = (prefs[Keys.WATCHED_HANDLES] ?: emptySet()) + clean
        }
    }

    suspend fun unwatchHandle(handle: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.WATCHED_HANDLES] =
                (prefs[Keys.WATCHED_HANDLES] ?: emptySet()) - handle.trim().lowercase()
        }
    }

    /**
     * Profiles already reported for a watched handle.
     *
     * Absent means no baseline yet, which the worker treats as "record what is
     * there now and say nothing" — otherwise enabling the feature would
     * immediately announce every account the user already knew about.
     */
    suspend fun seenProfiles(handle: String): Set<String>? =
        context.dataStore.data.first()[Keys.seenProfiles(handle.trim().lowercase())]

    suspend fun markProfilesSeen(handle: String, urls: Collection<String>) {
        val clean = handle.trim().lowercase()
        context.dataStore.edit { prefs ->
            prefs[Keys.seenProfiles(clean)] = urls.map { it.trimEnd('/') }.toSet()
        }
    }

    // ── Cleanup progress ─────────────────────────────────────────

    /** What the user has decided about one account. */
    enum class Cleanup { Todo, Keeping, Deleted }

    /** Every decision made for a handle, keyed by profile URL. */
    fun cleanupFor(handle: String): Flow<Map<String, Cleanup>> {
        val clean = handle.trim().removePrefix("@").lowercase()
        return context.dataStore.data.map { prefs ->
            val kept = prefs[Keys.cleanupKept(clean)] ?: emptySet()
            val done = prefs[Keys.cleanupDone(clean)] ?: emptySet()
            buildMap {
                kept.forEach { put(it, Cleanup.Keeping) }
                // Deleted wins a collision. It is the stronger statement, and a
                // URL should never be in both.
                done.forEach { put(it, Cleanup.Deleted) }
            }
        }
    }

    /**
     * Record a decision. [Cleanup.Todo] clears it.
     *
     * Always removes from both sets first, so toggling between the two cannot
     * leave a URL marked as kept *and* deleted.
     */
    suspend fun setCleanup(handle: String, url: String, state: Cleanup) {
        // The widget shows the unhandled count; nudge it rather than letting it
        // sit stale until the next hourly refresh.
        widgetRefresh()
        val clean = handle.trim().removePrefix("@").lowercase()
        val key = url.trimEnd('/')
        context.dataStore.edit { prefs ->
            val kept = (prefs[Keys.cleanupKept(clean)] ?: emptySet()) - key
            val done = (prefs[Keys.cleanupDone(clean)] ?: emptySet()) - key
            prefs[Keys.cleanupKept(clean)] = if (state == Cleanup.Keeping) kept + key else kept
            prefs[Keys.cleanupDone(clean)] = if (state == Cleanup.Deleted) done + key else done
        }
    }

    // ── Alerts ───────────────────────────────────────────────────

    val alertsEnabled: Flow<Boolean> = context.dataStore.data
        .map { it[Keys.ALERTS] == "true" }

    suspend fun setAlertsEnabled(on: Boolean) {
        context.dataStore.edit { prefs ->
            if (on) prefs[Keys.ALERTS] = "true" else prefs.remove(Keys.ALERTS)
        }
    }

    // ── Last scan ────────────────────────────────────────────────

    suspend fun saveScan(scan: SavedScan) {
        context.dataStore.edit { it[Keys.LAST_SCAN] = json.encodeToString(scan) }
        widgetRefresh()
    }

    /**
     * Redraw any placed widget.
     *
     * Reflective so the data layer keeps no compile-time dependency on the
     * widget, and wrapped because a launcher that cannot host widgets must
     * never break a save.
     */
    private fun widgetRefresh() {
        runCatching {
            Class.forName("com.aryan.myrecon.widget.ExposureWidget")
                .getDeclaredField("Companion").get(null)
                ?.let { companion ->
                    companion.javaClass
                        .getMethod("refresh", Context::class.java)
                        .invoke(companion, context.applicationContext)
                }
        }
    }

    suspend fun lastScan(): SavedScan? =
        context.dataStore.data.first()[Keys.LAST_SCAN]?.let { raw ->
            runCatching { json.decodeFromString<SavedScan>(raw) }.getOrNull()
        }

    suspend fun clearScan() {
        context.dataStore.edit { it.remove(Keys.LAST_SCAN) }
    }
}
