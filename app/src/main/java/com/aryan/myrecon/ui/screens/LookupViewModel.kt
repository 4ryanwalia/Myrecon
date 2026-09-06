package com.aryan.myrecon.ui.screens

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AlternateEmail
import androidx.compose.material.icons.filled.Dns
import androidx.compose.material.icons.filled.Hub
import androidx.compose.material.icons.filled.Language
import androidx.compose.material.icons.filled.MailOutline
import androidx.compose.material.icons.filled.Router
import android.app.Application
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aryan.myrecon.data.*
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch

/** Where a lookup actually runs. Surfaced in the UI, because "nothing left
 *  your phone" is only a meaningful claim if the app says when it is true. */
enum class Runs { OnDevice, Server }

/** The lookups the app offers. Mirrors the web tool tabs, plus deep search. */
enum class Tool(
    val label: String,
    val hint: String,
    val placeholder: String,
    val runs: Runs,
    val icon: ImageVector,
    val streams: Boolean = false,
) {
    Username(
        "Username", "Check a handle across ${PlatformCatalogue.size} platforms.", "e.g. torvalds",
        Runs.OnDevice, Icons.Filled.AlternateEmail, streams = true,
    ),
    Email(
        "Email", "Provider, deliverability and breach exposure.", "e.g. name@example.com",
        Runs.OnDevice, Icons.Filled.MailOutline,
    ),
    Domain(
        "Domain", "RDAP registration, nameservers and status.", "e.g. example.com",
        Runs.OnDevice, Icons.Filled.Language,
    ),
    Dns(
        "DNS", "A, AAAA, MX, NS, TXT, CNAME, SOA and CAA records.", "e.g. cloudflare.com",
        Runs.OnDevice, Icons.Filled.Dns,
    ),
    Ip(
        "IP", "Geolocation and network ownership.", "e.g. 8.8.8.8",
        Runs.OnDevice, Icons.Filled.Router,
    ),
    Deep(
        "Deep Search", "Correlate a handle into a scored relationship graph.", "e.g. torvalds",
        Runs.Server, Icons.Filled.Hub, streams = true,
    ),
}

/**
 * A username sweep plus its verified-identity lookup.
 *
 * Kept separate from [UsernameResult], which is a wire model shared with the
 * backend — Keybase runs entirely client-side and has no business in a schema
 * the server also parses.
 */
data class SweepResult(
    val result: UsernameResult,
    val identity: KeybaseIntel.Identity?,
    /** True when reloaded from disk rather than just scanned, so the UI can
     *  say so instead of implying the data is live. */
    val restored: Boolean = false,
)

/** What the screen is currently showing. */
sealed interface LookupState {
    data object Idle : LookupState

    data class Running(
        val phase: String,
        val detail: String,
        val percent: Int,
        val log: List<String>,
        // Populated only by the platform sweep, which drives the radar. Other
        // lookups leave these at zero and get the simpler console instead.
        val checked: Int = 0,
        val total: Int = 0,
        val found: Int = 0,
    ) : LookupState

    data class Done(val result: Any) : LookupState
    data class Failed(val message: String) : LookupState
}

class LookupViewModel(app: Application) : AndroidViewModel(app) {

    private val store = ReconStore(app)

    init {
        // Restore the last sweep so a result is not lost by switching apps.
        // Holding it only in the ViewModel survived a configuration change but
        // not process death, and Android reclaims a backgrounded app freely —
        // which is exactly when someone has tapped through to a browser.
        viewModelScope.launch {
            val saved = store.lastScan() ?: return@launch
            if (_state.value !is LookupState.Idle) return@launch
            _query.value = saved.handle
            _state.value = LookupState.Done(
                SweepResult(
                    result = UsernameResult(
                        query = UsernameQuery(saved.handle),
                        summary = UsernameSummary(
                            total = saved.profiles.size,
                            profiles = saved.profiles.size,
                        ),
                        results = UsernameBuckets(
                            profiles = saved.profiles.map {
                                Profile(
                                    url = it.url,
                                    platform = it.platform,
                                    category = it.category,
                                    confidence = it.confidence,
                                    exists = true,
                                    profilePicUrl = it.avatar,
                                    displayName = it.displayName,
                                )
                            }
                        ),
                    ),
                    identity = null,
                    restored = true,
                )
            )
        }
    }

    private val _tool = MutableStateFlow(Tool.Username)
    val tool: StateFlow<Tool> = _tool.asStateFlow()

    private val _query = MutableStateFlow("")
    val query: StateFlow<String> = _query.asStateFlow()

    // The "Deep sweep" toggle was removed. It survived the move of the username
    // sweep on-device but the parameter did not — UsernameSweep.run() takes no
    // depth argument, so the switch changed nothing and the two modes were
    // identical. A control that does nothing is worse than no control, and a
    // rewarded ad unlocking it was paying users in nothing at all.
    //
    // Deep Search remains a genuinely separate tool and always runs deep.

    private val _state = MutableStateFlow<LookupState>(LookupState.Idle)
    val state: StateFlow<LookupState> = _state.asStateFlow()

    private var job: Job? = null

    fun selectTool(t: Tool) {
        if (t == _tool.value) return
        job?.cancel()
        _tool.value = t
        _query.value = ""
        _state.value = LookupState.Idle
    }

    fun setQuery(v: String) { _query.value = v }

    fun cancel() {
        job?.cancel()
        _state.value = LookupState.Idle
    }

    fun run() {
        val q = _query.value.trim()
        if (q.isEmpty()) return
        val t = _tool.value

        job?.cancel()
        job = viewModelScope.launch {
            _state.value = LookupState.Running("Starting", "Preparing the lookup…", 0, emptyList())
            try {
                if (t.streams) runStreaming(t, q) else runSimple(t, q)
            } catch (e: Throwable) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                _state.value = LookupState.Failed(e.message ?: "The lookup failed.")
            }
        }
    }

    /**
     * Non-streaming lookups.
     *
     * These query public sources straight from the phone. If one is
     * unreachable the MyRecon backend is tried as a fallback, so a blocked
     * upstream degrades to a slower answer rather than no answer.
     */
    private suspend fun runSimple(t: Tool, q: String) {
        _state.value = LookupState.Running(
            t.label,
            if (t.runs == Runs.OnDevice) "Querying public sources from this device…" else "Querying…",
            35,
            emptyList(),
        )

        val result: Any = when (t) {
            Tool.Email -> orFallback({ OnDeviceIntel.email(q) }, { ReconApi.email(q) })
            Tool.Domain -> orFallback({ OnDeviceIntel.domain(q) }, { ReconApi.domain(q) })
            Tool.Dns -> orFallback({ OnDeviceIntel.dns(q) }, { ReconApi.dns(q) })
            Tool.Ip -> orFallback({ OnDeviceIntel.ip(q) }, { ReconApi.ip(q) })
            else -> error("not a simple tool: $t")
        }
        _state.value = LookupState.Done(result)
    }

    /** Run [primary]; on any non-cancellation failure, fall back to [secondary]. */
    private suspend fun <T> orFallback(primary: suspend () -> T, secondary: suspend () -> T): T =
        try {
            primary()
        } catch (e: kotlinx.coroutines.CancellationException) {
            throw e
        } catch (_: Throwable) {
            secondary()
        }

    /**
     * Consume an NDJSON stream, updating progress as events arrive.
     *
     * The log is capped: a deep sweep emits ~70 events and an unbounded list
     * would grow the recomposition cost of every frame for no benefit — only
     * the recent lines are ever on screen.
     */
    /**
     * On-device username sweep.
     *
     * Progress is emitted per platform so the console shows the same live
     * telemetry the web build has — the wait is visible rather than blank.
     */
    private suspend fun runSweep(q: String) {
        val log = ArrayDeque<String>()
        UsernameSweep.run(q).collect { ev ->
            when (ev) {
                is UsernameSweep.Event.Progress -> {
                    log.addFirst(
                        "[${ev.checked}/${ev.total}] ${ev.platform} — ${if (ev.exists) "found" else "clear"}"
                    )
                    while (log.size > 40) log.removeLast()
                    _state.value = LookupState.Running(
                        phase = "Checking platforms",
                        detail = ev.platform,
                        percent = (ev.checked * 100 / ev.total).coerceIn(0, 100),
                        log = log.toList(),
                        checked = ev.checked,
                        total = ev.total,
                        found = ev.found,
                    )
                }

                is UsernameSweep.Event.Finished -> {
                    // Verified identity links, fetched once the sweep settles.
                    // Additive: a Keybase failure must not lose the sweep.
                    val identity = runCatching { KeybaseIntel.lookup(q) }.getOrNull()

                    // Keep reachable-but-unconfirmed profiles visible. Some
                    // social platforms, notably Instagram and Pinterest,
                    // render the account data client-side or block parts of
                    // the page from a mobile request. In that case the sweep
                    // cannot make a strong claim, but hiding the returned
                    // profile entirely is a false negative. The result card
                    // labels these as low confidence rather than presenting
                    // them as confirmed accounts.
                    val profiles = ev.hits
                        .filter { it.confidence != "unverified" }
                        .map { h ->
                        Profile(
                            url = h.url,
                            platform = h.platform.name,
                            category = h.platform.category,
                            confidence = h.confidence,
                            exists = true,
                            profilePicUrl = h.avatar,
                            displayName = h.displayName,
                        )
                    }
                    // Persist before publishing, so the result is already
                    // recoverable by the time the user can act on it.
                    runCatching {
                        store.saveScan(
                            SavedScan(
                                handle = q,
                                at = System.currentTimeMillis(),
                                profiles = ev.hits.map {
                                    SavedProfile(
                                        platform = it.platform.name,
                                        category = it.platform.category,
                                        url = it.url,
                                        confidence = it.confidence,
                                        avatar = it.avatar,
                                        displayName = it.displayName,
                                    )
                                },
                            )
                        )
                    }

                    _state.value = LookupState.Done(
                        SweepResult(
                            result = UsernameResult(
                                query = UsernameQuery(q),
                                summary = UsernameSummary(
                                    total = profiles.size,
                                    profiles = profiles.size,
                                ),
                                results = UsernameBuckets(profiles = profiles),
                            ),
                            identity = identity?.takeIf { it.found },
                        )
                    )
                    fillMissingAvatars(q, profiles)
                }
            }
        }
    }

    private suspend fun runStreaming(t: Tool, q: String) {
        if (t == Tool.Username) return runSweep(q)

        // Deep Search is the deep mode — there is no shallow variant of it.
        val flow = ReconApi.investigateStream(q, deep = true)

        val log = ArrayDeque<String>()
        flow.catch { e -> _state.value = LookupState.Failed(e.message ?: "The scan failed.") }
            .collect { ev ->
                when (ev.type) {
                    "progress" -> {
                        ev.detail?.takeIf { it.isNotBlank() }?.let {
                            log.addFirst(it)
                            while (log.size > 40) log.removeLast()
                        }
                        _state.value = LookupState.Running(
                            phase = ev.phase ?: "Working",
                            detail = ev.detail.orEmpty(),
                            percent = (ev.percent ?: 0.0).toInt().coerceIn(0, 100),
                            log = log.toList(),
                        )
                    }
                    "error" -> _state.value = LookupState.Failed(ev.error ?: "The scan failed.")
                    "complete" -> {
                        val el = ev.data ?: return@collect
                        val parsed: Any = if (t == Tool.Deep) {
                            ReconApi.json.decodeFromJsonElement(InvestigationResult.serializer(), el)
                        } else {
                            ReconApi.json.decodeFromJsonElement(UsernameResult.serializer(), el)
                        }
                        _state.value = LookupState.Done(parsed)
                    }
                }
            }
    }

    /**
     * Ask the server for avatars the device could not get.
     *
     * Instagram decides who it answers by address, and a phone it has begun
     * refusing cannot recover on its own — the profile is found, but comes
     * back with no picture. The server is normally a different address and its
     * enricher has fallbacks the on-device probe does not, so it can usually
     * answer what the device could not.
     *
     * Deliberately narrow. It runs after results are already on screen, so the
     * sweep never waits on the network; it only touches profiles that are
     * missing an avatar, so a working local answer is never overwritten; and
     * it cannot change whether a profile is reported, only how it looks. A
     * failure leaves the placeholder tile exactly as it is.
     */
    private fun fillMissingAvatars(handle: String, profiles: List<Profile>) {
        val needing = profiles.filter {
            it.profilePicUrl.isNullOrBlank() && it.platform in SERVER_ENRICHED
        }
        if (needing.isEmpty()) return

        viewModelScope.launch {
            val filled = needing.mapNotNull { profile ->
                val pic = runCatching { ReconApi.enrich(profile.platform, handle) }
                    .getOrNull()?.profile?.profilePicUrl
                    ?.takeIf { it.isNotBlank() }
                pic?.let { profile.platform to it }
            }.toMap()
            if (filled.isEmpty()) return@launch

            // Done.result is Any — this screen serves several lookup types —
            // so re-check it is still a sweep before touching it. The user may
            // have run something else while the enrichment was in flight.
            val done = _state.value as? LookupState.Done ?: return@launch
            val sweep = done.result as? SweepResult ?: return@launch
            val updated = sweep.result.results.profiles.map { p ->
                filled[p.platform]?.let { p.copy(profilePicUrl = it) } ?: p
            }
            _state.value = LookupState.Done(
                sweep.copy(
                    result = sweep.result.copy(
                        results = sweep.result.results.copy(profiles = updated),
                    ),
                ),
            )
        }
    }

    private companion object {
        /**
         * Platforms worth a server round-trip when the device gets no avatar.
         *
         * Kept short on purpose: each entry is a request, and most platforms
         * that yield no picture genuinely have none to give.
         */
        val SERVER_ENRICHED = setOf("Instagram", "Pinterest", "TikTok", "Threads")
    }

}
