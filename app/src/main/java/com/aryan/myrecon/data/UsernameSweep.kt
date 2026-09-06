package com.aryan.myrecon.data

import android.util.Log
import com.aryan.myrecon.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.buffer
import kotlinx.coroutines.flow.channelFlow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.joinAll
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

/**
 * Username sweep, run from the device.
 *
 * This is the last lookup that needed the server, and moving it here is not
 * only about latency. Platforms rate-limit and block datacentre address ranges
 * far more aggressively than residential and mobile ones, so the same sweep run
 * from a phone tends to see *fewer* false negatives than one run from a cloud
 * host. Doing it on-device is both faster and more accurate.
 *
 * Requests are GET, not HEAD: several platforms answer HEAD with 405 or return
 * a misleading status, and some serve a 200 "user not found" page that only a
 * body check can catch.
 */
object UsernameSweep {

    /** One platform's verdict. */
    data class Hit(
        val platform: PlatformDef,
        val exists: Boolean,
        val url: String,
        val status: Int,
        val confidence: String,
        /** Profile picture, when the page or API exposed one. */
        val avatar: String? = null,
        /** Display name, when available. */
        val displayName: String? = null,
    )

    /** Streamed while the sweep runs. */
    sealed interface Event {
        data class Progress(
            val checked: Int,
            val total: Int,
            val found: Int,
            val platform: String,
            val exists: Boolean,
        ) : Event

        data class Finished(val hits: List<Hit>) : Event
    }

    private val client = OkHttpClient.Builder()
        .connectTimeout(6, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
        // Redirects ARE followed. Disabling them was a mistake: Reddit answers
        // 301 and YouTube 302 for perfectly real profiles (canonicalising the
        // URL), and treating that as absent hid them entirely. What matters is
        // not that a redirect happened but where it landed — see LANDING_MISS.
        .followRedirects(true)
        .followSslRedirects(true)
        .retryOnConnectionFailure(false)
        .build()

    /**
     * Redirect destinations that mean "no such user".
     *
     * A profile URL that ends up at a login wall, a signup page or the site
     * root is the platform's way of saying it has nothing to show.
     */
    private val LANDING_MISS = listOf(
        "/login", "/signin", "/sign_in", "/signup", "/register",
        "/accounts/login", "/404", "/not-found", "/error",
    )

    private const val UA =
        "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) " +
            "Chrome/124.0.0.0 Mobile Safari/537.36"

    /**
     * Phrases that mean "no such user" on a page still served with HTTP 200.
     *
     * A bare "404" is deliberately absent: large pages embed that string in
     * analytics payloads and asset URLs, and matching it flagged live profiles
     * as missing.
     */
    private val NOT_FOUND_MARKERS = listOf(
        "page not found", "user not found", "profile not found", "page doesn't exist",
        "couldn't find this account", "couldn't find that page", "doesn't exist",
        "does not exist", "no such user", "sorry, this page", "page isn't available",
        "page not available", "account suspended", "user does not exist",
        "this account doesn't exist", "nothing to see here",
    )

    /** Error words that appear in the <title> of a not-found page. */
    private val TITLE_ERROR_MARKERS = listOf(
        "not found", "error", "404", "page unavailable", "oops", "doesn't exist",
    )

    private val TITLE_RE = Regex("""<title[^>]*>(.*?)</title>""", RegexOption.DOT_MATCHES_ALL)

    /**
     * Profile picture extraction from Open Graph tags.
     *
     * Costs nothing extra: the body is already being read for the not-found
     * check, and og:image sits in <head>, well inside the peek. Attribute order
     * varies between platforms, so both orderings are matched.
     */
    private val OG_IMAGE_RES = listOf(
        Regex("""<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']""", RegexOption.IGNORE_CASE),
        Regex("""<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']""", RegexOption.IGNORE_CASE),
        Regex("""<meta[^>]+name=["']twitter:image["'][^>]+content=["']([^"']+)["']""", RegexOption.IGNORE_CASE),
        Regex("""<meta[^>]+content=["']([^"']+)["'][^>]+name=["']twitter:image["']""", RegexOption.IGNORE_CASE),
    )

    private val OG_TITLE_RE =
        Regex("""<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']+)["']""", RegexOption.IGNORE_CASE)

    /**
     * Substrings that mark a stock image rather than a person's own.
     *
     * DeviantArt, for instance, serves `default_group.gif` for accounts with no
     * picture. Showing that would imply we found an avatar when we did not, so
     * it is discarded and the coloured monogram is used instead.
     */
    private val PLACEHOLDER_MARKERS = listOf(
        "default", "placeholder", "anonymous", "no-avatar", "noavatar",
        "blank", "generic", "mystery", "gravatar.com/avatar/00000",
        // Site-wide Open Graph artwork. Many platforms set og:image to their own
        // logo on every page, so a profile with no picture yields the brand
        // asset instead. Showing that is worse than showing nothing: it looks
        // like a real avatar and would repeat identically across results.
        "ogimage", "og-image", "og_image", "og.png", "og.jpg", "opengraph",
        "/share/", "twitter-card", "social-card", "default-avatar",
    )

    /** `&` and friends, as JSON APIs escape them inside string values. */
    private val UNICODE_ESCAPE = Regex("""\\u([0-9a-fA-F]{4})""")

    private fun cleanAvatar(raw: String?): String? {
        var url = raw?.trim() ?: return null

        // Instagram's API returns avatar URLs with the ampersands escaped as
        // &. Left as-is the query string is malformed and the CDN rejects
        // it, which shows up as a silently broken image.
        url = UNICODE_ESCAPE.replace(url) { m ->
            m.groupValues[1].toInt(16).toChar().toString()
        }.replace("&amp;", "&").replace("\\/", "/")

        if (!url.startsWith("http")) return null
        val lower = url.lowercase()
        if (PLACEHOLDER_MARKERS.any { it in lower }) return null

        // Some pages emit a doubled query ("...?v=4?s=400"); keep the first.
        val second = url.indexOf('?', url.indexOf('?') + 1)
        return if (second > 0) url.substring(0, second) else url
    }

    private fun avatarFrom(peek: String): String? =
        OG_IMAGE_RES.firstNotNullOfOrNull { re ->
            cleanAvatar(re.find(peek)?.groupValues?.getOrNull(1))
        }

    /**
     * Pull a string field out of a JSON payload without building a model for
     * every API's shape. Regex rather than a parser because the field names are
     * all that is wanted and the payloads are large — GitHub calls it
     * `avatar_url`, Instagram `profile_pic_url_hd`.
     */
    private fun jsonField(body: String, field: String): String? =
        Regex(""""$field"\s*:\s*"([^"]+)"""").find(body)
            ?.groupValues?.getOrNull(1)
            ?.replace("\\/", "/")
            ?.takeIf { it.isNotBlank() }

    private fun avatarFromJson(body: String): String? =
        listOf(
            "profile_pic_url_hd", "profile_pic_url", "avatar_url", "icon_img", "image_url",
            "image_xlarge_url", "image_large_url", "profile_image_url_https",
            "profile_image_url", "avatar", "avatarUrl", "photo_url", "picture",
            "thumbnail_url", "image",
        )
            .firstNotNullOfOrNull { cleanAvatar(jsonField(body, it)) }

    /**
     * Platforms pinned to the top of their own category.
     *
     * The sort is global but ResultViews groups by category afterwards, so
     * each entry only ever competes with its own group: Instagram and
     * Pinterest lead Social, YouTube leads Video. Relative order between
     * different categories is therefore irrelevant — what matters is that a
     * pinned platform outranks everything sharing its category, which the
     * alphabetical fallback otherwise decided (YouTube lost to DailyMotion,
     * Kick, Rumble, Twitch and Vimeo purely on spelling).
     *
     * Names must match PlatformCatalogue exactly. Kept in step with
     * _PINNED_PLATFORMS in backend/services/search.py so both surfaces order
     * results the same way.
     */
    private val PINNED = listOf("Instagram", "Pinterest", "YouTube")

    private const val CONCURRENCY = 16

    /**
     * How much of the body to read.
     *
     * 4 KB was far too small: Instagram serves ~590 KB and Pinterest ~1 MB, and
     * the "unavailable" text sits well past the start, so every one of those
     * looked like a hit. 48 KB reaches the marker on the pages checked here
     * while keeping the worst case for a full sweep to a few megabytes, which
     * matters on mobile data.
     */
    private const val BODY_PEEK_BYTES = 48_000L
    /**
     * Pinterest reads almost the whole document, because its profile data is
     * at the very bottom of it.
     *
     * Measured on live profiles rather than estimated: the page decodes to
     * 1.31-1.52 MB and the `"username"` field lands at 1,036,563
     * (jamieoliver) and 1,242,000 (marthastewart), with `image_xlarge_url`
     * about 90 KB further on. At the previous 192 KB every one of those sat
     * far outside the slice, so [pinterestProfileIn] could never return true
     * and [avatarFromJson] could never find the avatar - Pinterest was not
     * merely unreliable here, it was undetectable.
     *
     * This costs no extra network. The response is Brotli-encoded and weighs
     * ~140 KB on the wire either way; the peek only bounds how much of it is
     * decompressed, so the old limit was saving heap, never data. 1.8 MB
     * leaves headroom over the largest page measured (2.04 MB decoded for the
     * @pinterest account itself, whose fields sit at ~1.75 MB).
     */
    private const val PINTEREST_PEEK_BYTES = 1_800_000L
    // Mobile YouTube sends a large application shell before its real channel
    // metadata. The channel's og:image is commonly hundreds of KB into the
    // response, so the normal page window never reaches it.
    private const val YOUTUBE_PEEK_BYTES = 1_000_000L

    /**
     * Instagram has a floor *and* a ceiling, and the ceiling is the subtle one.
     *
     * Floor: Instagram emits ~95 KB of inline script before `<head>` closes —
     * `<title>` was measured at 94,964 — and og:image sits beside it. At 48 KB
     * the window stopped short of every avatar signal, so a profile that was
     * otherwise detected came back with no picture.
     *
     * Ceiling: do NOT raise this past ~300 KB. Instagram echoes the requested
     * handle back at ~308,900 inside an `"httperrorpage"` routing object, and
     * it does so for handles that do not exist — measured, `nasa` and
     * `zzqnope99123xqq` both produce it, in shells whose sizes differ by 12
     * bytes. A window that reaches the echo would make `mentionsHandle` true
     * for every handle on earth and turn Instagram into a permanent false
     * positive. 160 KB clears the head and stays far short of the echo.
     */
    private const val INSTAGRAM_PEEK_BYTES = 160_000L

    private fun pinterestProfileIn(body: String, handle: String): Boolean {
        val escaped = Regex.escape(handle.lowercase())
        val hasHandle = Regex("""[\"']username[\"']\s*:\s*[\"']$escaped[\"']""")
            .containsMatchIn(body)
        val hasProfileField = listOf(
            "\"full_name\"", "\"image_xlarge_url\"", "\"image_large_url\"",
            "\"follower_count\"", "\"following_count\"",
        ).any { it in body }
        return hasHandle && hasProfileField
    }

    /**
     * Check [username] across every catalogued platform.
     *
     * Emits progress as each check completes and a final [Event.Finished].
     * Concurrency is capped so a phone on mobile data is not asked to open 118
     * sockets at once.
     */
    fun run(username: String): Flow<Event> = channelFlow {
        val handle = username.trim().removePrefix("@")
        require(handle.isNotEmpty()) { "Username is empty." }

        val platforms = PlatformCatalogue.ALL
        val gate = Semaphore(CONCURRENCY)
        val checked = AtomicInteger(0)
        val found = AtomicInteger(0)
        val hits = java.util.Collections.synchronizedList(mutableListOf<Hit>())

        val jobs = platforms.map { p ->
            launch {
                gate.withPermit {
                    val hit = probe(p, handle)
                    logHit(p, hit)
                    val n = checked.incrementAndGet()
                    if (hit != null && hit.exists) {
                        hits += hit
                        found.incrementAndGet()
                    }
                    send(
                        Event.Progress(
                            checked = n,
                            total = platforms.size,
                            found = found.get(),
                            platform = p.name,
                            exists = hit?.exists == true,
                        )
                    )
                }
            }
        }

        // Wait for every probe before the terminal event, so Finished always
        // carries the complete set rather than whatever had arrived so far.
        jobs.joinAll()
        // Pinned platforms first (Instagram, then Pinterest), then confidence,
        // then name.
        //
        // Not cosmetic: while the reward gate is locked ResultViews shows only
        // the first account in each category, so whatever sorts first in
        // Social is the only social account most users ever see. Instagram is
        // the one they are almost always looking for, and alphabetical order
        // was burying it behind Ello, Facebook and Gab.
        send(Event.Finished(hits.sortedWith(
            compareBy<Hit> { PINNED.indexOf(it.platform.name).takeIf { i -> i >= 0 } ?: PINNED.size }
                .thenByDescending { it.confidence == "high" }
                .thenBy { it.platform.name },
        )))
    }.flowOn(Dispatchers.IO).buffer()

    /**
     * JSON-endpoint check: 200 means the account exists, 404 means it does not.
     * Returns null when the endpoint is unavailable (rate limit, block, network
     * error) so the caller can fall back to the HTML check rather than
     * reporting a definite answer it does not have.
     */
    private fun probeApi(p: PlatformDef, handle: String): Hit? {
        val api = p.apiUrlFor(handle) ?: return null
        return try {
            val b = Request.Builder().url(api)
                .header("User-Agent", UA)
                .header("Accept", "application/json")
            p.apiHeaders.forEach { (k, v) -> b.header(k, v) }

            client.newCall(b.get().build()).execute().use { resp ->
                when (resp.code) {
                    200 -> {
                        // Instagram's profile object can be much larger than
                        // other API responses. Its avatar URL is sometimes
                        // outside the first 16 KB, so give that endpoint a
                        // bounded larger read before falling back to HTML.
                        val limit = when (p.name) {
                            "Instagram" -> 128_000L
                            else -> 64_000L
                        }
                        val body = runCatching { resp.peekBody(limit).string() }.getOrDefault("")
                        // An empty array or null user is a 200 that still means absent.
                        val empty = body.isBlank() || body == "[]" ||
                            body.contains("\"user\": null") || body.contains("\"user\":null")
                        if (empty) {
                            Hit(p, false, p.urlFor(handle), 200, "none")
                        } else {
                            Hit(
                                p, true, p.urlFor(handle), 200, "high",
                                avatar = avatarFromJson(body),
                                displayName = jsonField(body, "full_name")
                                    ?: jsonField(body, "name"),
                            )
                        }
                    }
                    404, 410 -> Hit(p, false, p.urlFor(handle), resp.code, "none")
                    // 403 / 429 mean blocked or throttled, not absent.
                    else -> null
                }
            }
        } catch (_: Throwable) {
            null
        }
    }

    /**
     * Debug-only trace of what each platform actually produced.
     *
     * An avatar that fails to appear is indistinguishable, on screen, from one
     * that was never found — SubcomposeAsyncImage falls back to the same
     * PlatformTile whether Coil errored or the URL was null. This says which,
     * so a missing picture can be diagnosed from Logcat instead of inferred.
     *
     * Stripped from release by the BuildConfig.DEBUG guard; filter Logcat on
     * the "MyReconSweep" tag.
     */
    private fun logHit(p: PlatformDef, hit: Hit?) {
        if (!BuildConfig.DEBUG) return
        Log.d(
            "MyReconSweep",
            "${p.name}: exists=${hit?.exists} conf=${hit?.confidence} " +
                "status=${hit?.status} avatar=${hit?.avatar ?: "<none>"}",
        )
    }

    @Suppress("ReturnCount")
    private fun probe(p: PlatformDef, handle: String): Hit? {
        // Prefer an unambiguous API answer where the platform offers one.
        probeApi(p, handle)?.let { return it }

        val url = p.urlFor(handle)
        return try {
            val req = Request.Builder().url(url)
                .header("User-Agent", UA)
                .header("Accept", "text/html,application/xhtml+xml")
                .header("Accept-Language", "en-US,en;q=0.9")
                .get()
                .build()

            client.newCall(req).execute().use { resp ->
                val code = resp.code
                if (code != p.okStatus) {
                    return Hit(p, exists = false, url = url, status = code, confidence = "none")
                }

                // Bounded peek — whole pages for 117 platforms would burn the
                // user's data allowance for no extra signal.
                // Two views of the same bytes, and the distinction matters.
                // Marker matching wants lower case; anything handed back to
                // the UI must keep the case it was served in. Pinterest's
                // avatars live at paths like /280x280_RS/, and lowercasing
                // that is a 403 from the CDN — the image simply never loads.
                // Display names have the same problem, less visibly.
                val raw = runCatching {
                    val limit = when (p.name) {
                        "Pinterest" -> PINTEREST_PEEK_BYTES
                        "YouTube" -> YOUTUBE_PEEK_BYTES
                        "Instagram" -> INSTAGRAM_PEEK_BYTES
                        else -> BODY_PEEK_BYTES
                    }
                    resp.peekBody(limit).string()
                }.getOrDefault("")
                val peek = raw.lowercase()

                val title = TITLE_RE.find(peek)?.groupValues?.get(1)?.trim().orEmpty()

                // Signal 1 — the page says outright that nothing is here.
                if (NOT_FOUND_MARKERS.any { it in peek }) {
                    return Hit(p, exists = false, url = url, status = code, confidence = "none")
                }
                // Signal 2 — the title is an error page ("Steam Community :: Error").
                if (TITLE_ERROR_MARKERS.any { it in title }) {
                    return Hit(p, exists = false, url = url, status = code, confidence = "none")
                }

                // Signal 3 — a real profile nearly always names its owner. When
                // the handle appears nowhere in the page, this is very likely a
                // generic template served for any input. Reported as
                // "unverified" rather than absent: the evidence is weak both
                // ways, and silently dropping it would understate a footprint
                // just as badly as claiming it would overstate one.
                // Signal 3 — where the redirect chain ended. A profile URL that
                // lands on a login wall or the site root has nothing behind it.
                val landed = resp.request.url.encodedPath.lowercase()
                if (LANDING_MISS.any { landed.endsWith(it) || landed == it }) {
                    return Hit(p, exists = false, url = url, status = code, confidence = "none")
                }

                // Whether the page names its owner RAISES confidence but no
                // longer rejects. Using absence as a rejection was wrong: many
                // profiles are rendered client-side, so Instagram and Pinterest
                // omit the handle from their HTML even for accounts that exist,
                // and the rule hid them completely.
                val mentionsHandle = handle.lowercase() in peek
                val pinterestProfile = p.name == "Pinterest" && pinterestProfileIn(peek, handle)
                val conf = when {
                    // Serves a page for any handle, so nothing here is evidence.
                    p.name in PlatformCatalogue.ECHOES_HANDLE -> "unverified"
                    mentionsHandle && p.name in PlatformCatalogue.CORROBORATING -> "high"
                    mentionsHandle || pinterestProfile -> "medium"
                    // Reachable, no error, but unconfirmed — reported as a
                    // possible hit rather than dropped or overclaimed.
                    else -> "low"
                }
                Hit(
                    p, exists = conf != "unverified", url = url, status = code, confidence = conf,
                    avatar = avatarFrom(raw) ?: avatarFromJson(raw),
                    displayName = OG_TITLE_RE.find(raw)?.groupValues?.getOrNull(1)?.trim()
                        ?.takeIf { it.isNotBlank() && !it.equals(p.name, ignoreCase = true) },
                )
            }
        } catch (_: Throwable) {
            // Timeouts and DNS failures are "unknown", not "absent" — reporting
            // them as absent would quietly understate someone's footprint.
            null
        }
    }
}
