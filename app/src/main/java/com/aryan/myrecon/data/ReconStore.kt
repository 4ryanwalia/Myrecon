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
        context.dataStore.edit { prefs ->
            prefs[Keys.WATCHED_EMAILS] =
                (prefs[Keys.WATCHED_EMAILS] ?: emptySet()) - email.trim().lowercase()
        }
    }

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

    // ── Last scan ────────────────────────────────────────────────

    suspend fun saveScan(scan: SavedScan) {
        context.dataStore.edit { it[Keys.LAST_SCAN] = json.encodeToString(scan) }
    }

    suspend fun lastScan(): SavedScan? =
        context.dataStore.data.first()[Keys.LAST_SCAN]?.let { raw ->
            runCatching { json.decodeFromString<SavedScan>(raw) }.getOrNull()
        }

    suspend fun clearScan() {
        context.dataStore.edit { it.remove(Keys.LAST_SCAN) }
    }
}
