package com.aryan.myrecon.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.net.URI
import java.net.URLDecoder
import java.net.URLEncoder
import java.util.concurrent.TimeUnit

/**
 * Keyless web search, run from the device.
 *
 * Deep Search needs to actually *execute* dork queries, not just print them,
 * and every search API that would do that cleanly costs money. What is left is
 * the two engines that still answer an unauthenticated request:
 *
 *   • DuckDuckGo Lite — good relevance, honours `site:`, but challenges a
 *     caller that asks too often. It is tried first and dropped for the rest
 *     of the run the moment it serves a challenge page.
 *   • Bing's RSS output — reliably answers HTTP 200 without a key, but is
 *     sloppy: for a query it does not like it returns ten results for
 *     something else entirely. Measured while building this, `site:instagram.com
 *     "cristiano"` came back as a list of React tutorials.
 *
 * That last behaviour is why [Constraint] exists. Every hit is checked back
 * against the query that supposedly produced it — the host must satisfy
 * `site:`, the path must satisfy a path-scoped `site:`, every quoted phrase
 * must actually appear, `filetype:` must match — and anything that fails is
 * discarded. An engine that answers off-topic contributes nothing rather than
 * contributing noise, which is the only way results from a source this loose
 * can be put in front of someone as evidence.
 *
 * Running from the phone rather than the backend is the same call the username
 * sweep made, for a stronger reason here: search engines rate-limit datacentre
 * ranges far harder than mobile ones. One person's handset asking twenty
 * questions looks like a person. A Render worker asking on behalf of everyone
 * looks like a scraper, and is treated as one.
 */
object WebSearch {

    /** One verified search result. */
    data class Hit(
        val url: String,
        val title: String,
        val snippet: String,
        val host: String,
        /** The query that found it — shown so a result can be traced back. */
        val query: String,
        val engine: String,
    )

    enum class Engine(val label: String) { DuckDuckGo("DuckDuckGo"), Bing("Bing") }

    private val client = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(12, TimeUnit.SECONDS)
        .followRedirects(true)
        .retryOnConnectionFailure(false)
        .build()

    private const val UA =
        "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) " +
            "Chrome/124.0.0.0 Mobile Safari/537.36"

    /**
     * Minimum gap between outbound queries, plus a little noise.
     *
     * Both engines answer a burst with a challenge page. Spacing requests is
     * what keeps a twenty-query plan returning results for its whole length
     * instead of dying after the third, and the jitter keeps the run from
     * looking like a metronome, which is itself a signal.
     */
    private const val THROTTLE_MS = 1_200L
    private const val JITTER_MS = 400L

    /**
     * Pause before re-asking an engine that just challenged us.
     *
     * One challenge is not a verdict — DuckDuckGo throttles a burst and then
     * answers again — so an engine is only written off after it refuses twice
     * in a row. Giving up on the first refusal cost the whole run its better
     * engine over what was often a single impatient request.
     */
    private const val CHALLENGE_BACKOFF_MS = 3_000L

    private val gate = Mutex()
    private var lastRequestAt = 0L

    /**
     * Engines that have started refusing during this run.
     *
     * Session state, not permanent: [newSession] clears it, so a later search
     * gets a fresh attempt at the better engine rather than being stuck on the
     * fallback for the life of the process.
     */
    private val blocked = mutableSetOf<Engine>()

    /** Call once at the start of a search run. */
    fun newSession() {
        synchronized(blocked) { blocked.clear() }
    }

    /** Engines still answering. Empty means every engine refused this run. */
    fun availableEngines(): List<Engine> =
        synchronized(blocked) { Engine.entries.filter { it !in blocked } }

    private fun markBlocked(e: Engine) {
        synchronized(blocked) { blocked += e }
    }

    private fun isBlocked(e: Engine): Boolean = synchronized(blocked) { e in blocked }

    // ── Query constraints ────────────────────────────────────────

    /**
     * What a dork actually demands, extracted from its text.
     *
     * This is the contract a result has to satisfy to be believed.
     */
    data class Constraint(
        /** Registrable host from `site:`, lowercased, no `www.`. */
        val site: String? = null,
        /** Path prefix from a path-scoped `site:`, e.g. `/in` or `/user/bob`. */
        val sitePath: String? = null,
        /** Every `"quoted phrase"`. All must appear. */
        val phrases: List<String> = emptyList(),
        /** Extension demanded by `filetype:`, without the dot. */
        val filetype: String? = null,
    ) {
        /**
         * Does this result satisfy the query that claims to have found it?
         *
         * Deliberately strict. Losing a real result because its snippet was
         * truncated past the phrase is a recoverable disappointment; showing
         * someone a React tutorial as an Instagram finding is not.
         */
        fun accepts(url: String, title: String, snippet: String): Boolean {
            val host = hostOf(url) ?: return false
            if (host in ENGINE_HOSTS) return false

            if (site != null && host != site && !host.endsWith(".$site")) return false

            val path = runCatching { URI(url).path.orEmpty() }.getOrDefault("")
            if (sitePath != null && !path.lowercase().startsWith(sitePath)) return false
            if (filetype != null && !path.lowercase().endsWith(".$filetype")) return false

            if (phrases.isNotEmpty()) {
                // The URL counts as evidence: a profile page frequently carries
                // the handle in its path while the snippet is boilerplate.
                val hay = normalise(title + " " + snippet + " " + decode(url))
                if (phrases.any { normalise(it) !in hay }) return false
            }
            return true
        }
    }

    /** Engine result pages and redirectors — never a finding in their own right. */
    private val ENGINE_HOSTS = setOf(
        "duckduckgo.com", "lite.duckduckgo.com", "html.duckduckgo.com",
        "bing.com", "google.com", "search.yahoo.com", "yandex.com",
        "webcache.googleusercontent.com",
    )

    private val PHRASE_RE = Regex("\"([^\"]+)\"")
    private val SITE_RE = Regex("""\bsite:([^\s"]+)""", RegexOption.IGNORE_CASE)
    private val FILETYPE_RE = Regex("""\bfiletype:([A-Za-z0-9]+)""", RegexOption.IGNORE_CASE)

    fun constraintsOf(query: String): Constraint {
        val siteRaw = SITE_RE.find(query)?.groupValues?.get(1)?.lowercase()
        val host = siteRaw?.substringBefore('/')?.removePrefix("www.")
        val path = siteRaw?.substringAfter('/', "")
            ?.takeIf { it.isNotBlank() }
            ?.let { "/" + it.trimEnd('/') }

        return Constraint(
            site = host,
            sitePath = path,
            // An OR-group cannot be required as a conjunction, so a query
            // carrying one drops phrase checking and leans on the host check
            // alone. Requiring every alternative would reject the very results
            // the OR was written to find.
            phrases = if (query.contains(" OR ")) emptyList()
            else PHRASE_RE.findAll(query).map { it.groupValues[1] }.toList(),
            filetype = FILETYPE_RE.find(query)?.groupValues?.get(1)?.lowercase(),
        )
    }

    /** Punctuation-insensitive comparison, so `"u/bob"` still matches `u/bob:`. */
    private fun normalise(s: String): String =
        s.lowercase().map { if (it.isLetterOrDigit()) it else ' ' }
            .joinToString("").replace(Regex("\\s+"), " ").trim()

    fun hostOf(url: String): String? = runCatching {
        URI(url).host?.lowercase()?.removePrefix("www.")?.takeIf { it.isNotBlank() }
    }.getOrNull()

    // ── Execution ────────────────────────────────────────────────

    /**
     * Run one query and return only the hits that satisfy it.
     *
     * Engines are tried in preference order; the first that returns anything
     * verified wins. An engine that answers with a challenge is recorded and
     * skipped for the rest of the session rather than being asked nineteen
     * more times.
     */
    suspend fun search(query: String, limit: Int = 8): List<Hit> {
        val constraint = constraintsOf(query)
        // A query with nothing to check against would accept whatever Bing felt
        // like returning. Refuse it here rather than trusting callers.
        if (constraint.site == null && constraint.phrases.isEmpty() && constraint.filetype == null) {
            return emptyList()
        }
        for (engine in Engine.entries) {
            if (isBlocked(engine)) continue
            val raw = runCatching { fetch(engine, query) }.getOrNull()
            if (raw == null) {
                markBlocked(engine)
                continue
            }
            if (raw.isEmpty()) continue  // answered, but genuinely had nothing

            val verified = raw
                .filter { constraint.accepts(it.url, it.title, it.snippet) }
                .distinctBy { it.url.trimEnd('/') }
                .take(limit)
            if (verified.isNotEmpty()) return verified
        }
        return emptyList()
    }

    private suspend fun fetch(engine: Engine, query: String): List<Hit>? {
        throttle()
        val first = when (engine) {
            Engine.DuckDuckGo -> duckDuckGo(query)
            Engine.Bing -> bing(query)
        }
        // Bing does not challenge; a null from it is a real failure. DuckDuckGo
        // gets a second chance after a pause before the run writes it off.
        if (first != null || engine != Engine.DuckDuckGo) return first
        delay(CHALLENGE_BACKOFF_MS)
        return duckDuckGo(query)
    }

    private suspend fun throttle() {
        val wait = gate.withLock {
            val now = System.currentTimeMillis()
            val gap = THROTTLE_MS + (0 until JITTER_MS).random()
            val pending = (lastRequestAt + gap - now).coerceAtLeast(0)
            lastRequestAt = now + pending
            pending
        }
        if (wait > 0) delay(wait)
    }

    private suspend fun body(url: String): String? = withContext(Dispatchers.IO) {
        val req = Request.Builder().url(url)
            .header("User-Agent", UA)
            .header("Accept-Language", "en-US,en;q=0.9")
            .build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) return@withContext null
            resp.body?.string()
        }
    }

    private fun encode(q: String): String = URLEncoder.encode(q, "UTF-8")

    // ── DuckDuckGo Lite ──────────────────────────────────────────

    // Lite writes its attributes with single quotes and puts the link, the
    // snippet and the display URL in three separate table rows, so results and
    // snippets are matched up by position rather than by nesting.
    private val DDG_LINK_RE = Regex(
        """<a[^>]+href=["']([^"']+)["'][^>]*class=["']result-link["'][^>]*>(.*?)</a>""",
        setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL),
    )
    private val DDG_SNIPPET_RE = Regex(
        """class=["']result-snippet["'][^>]*>(.*?)</td>""",
        setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL),
    )

    /** Returns null when DuckDuckGo served a challenge instead of results. */
    private suspend fun duckDuckGo(query: String): List<Hit>? {
        val html = body("https://lite.duckduckgo.com/lite/?q=" + encode(query)) ?: return null
        // The challenge page is a normal 200 with an anomaly form in it and no
        // results at all — indistinguishable from success by status alone.
        if ("anomaly.js" in html || "challenge-form" in html) return null

        val links = DDG_LINK_RE.findAll(html).toList()
        // "result-link" present but unparsed means the markup moved; that is a
        // parser failure, not an empty result set, so fail over to Bing.
        if (links.isEmpty()) return if ("result-link" in html) null else emptyList()

        val snippets = DDG_SNIPPET_RE.findAll(html).map { strip(it.groupValues[1]) }.toList()
        return links.mapIndexedNotNull { i, m ->
            val url = unwrap(m.groupValues[1]) ?: return@mapIndexedNotNull null
            Hit(
                url = url,
                title = strip(m.groupValues[2]),
                snippet = snippets.getOrElse(i) { "" },
                host = hostOf(url).orEmpty(),
                query = query,
                engine = Engine.DuckDuckGo.label,
            )
        }
    }

    /** Lite routes clicks through `/l/?uddg=<encoded target>`. Recover the target. */
    private fun unwrap(href: String): String? {
        val raw = if (href.startsWith("//")) "https:" + href else href
        if ("uddg=" !in raw) return raw.takeIf { it.startsWith("http") }
        val encoded = raw.substringAfter("uddg=").substringBefore('&')
        return decode(encoded).takeIf { it.startsWith("http") }
    }

    // ── Bing RSS ─────────────────────────────────────────────────

    private val RSS_ITEM_RE = Regex("""<item>(.*?)</item>""", RegexOption.DOT_MATCHES_ALL)

    private fun rssField(item: String, tag: String): String =
        Regex("<$tag>(.*?)</$tag>", RegexOption.DOT_MATCHES_ALL)
            .find(item)?.groupValues?.get(1).orEmpty().let(::strip)

    private suspend fun bing(query: String): List<Hit>? {
        val xml = body("https://www.bing.com/search?q=" + encode(query) + "&format=rss&count=20")
            ?: return null
        return RSS_ITEM_RE.findAll(xml).mapNotNull { m ->
            val item = m.groupValues[1]
            val url = rssField(item, "link").takeIf { it.startsWith("http") }
                ?: return@mapNotNull null
            Hit(
                url = url,
                title = rssField(item, "title"),
                snippet = rssField(item, "description"),
                host = hostOf(url).orEmpty(),
                query = query,
                engine = Engine.Bing.label,
            )
        }.toList()
    }

    // ── Text helpers ─────────────────────────────────────────────

    private val TAG_RE = Regex("<[^>]+>")

    /** Drop markup and decode entities — both engines return HTML in fields. */
    fun strip(s: String): String = TAG_RE.replace(s, "")
        .replace("&amp;", "&").replace("&quot;", "\"").replace("&#34;", "\"")
        .replace("&#39;", "'").replace("&#x27;", "'").replace("&apos;", "'")
        .replace("&lt;", "<").replace("&gt;", ">")
        .replace("&nbsp;", " ").replace("&hellip;", "…")
        .replace(Regex("\\s+"), " ").trim()

    private fun decode(s: String): String =
        runCatching { URLDecoder.decode(s, "UTF-8") }.getOrDefault(s)
}
