package com.aryan.myrecon.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

/**
 * The Breach Files, as published on the website.
 *
 * Distinct from [BreachFeed], which pulls Have I Been Pwned's raw catalogue so
 * the background worker can tell that something new exists. This reads the feed
 * *we* generate: the same breaches after our severity scoring, our reading of
 * what each leaked field costs a person, and the logo and prose that go with
 * them. HIBP's list answers "what happened"; this one answers "and what we said
 * about it".
 *
 * Reading the site's own JSON rather than re-deriving any of it means the app
 * and the website can never disagree. The scoring lives in one place, runs once
 * every six hours in the build, and both surfaces read the result.
 *
 * Keyless, static, on a CDN — so this is one cheap GET with no server of ours
 * in the path.
 */
object BreachArticles {

    private const val FEED = "https://www.myrecon.xyz/assets/data/breaches.json"

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    private val json = Json { ignoreUnknownKeys = true; isLenient = true }

    @Serializable
    data class Article(
        val name: String = "",
        val title: String = "",
        val slug: String = "",
        /** The full write-up on the site. */
        val url: String = "",
        val domain: String? = null,
        @SerialName("breach_date") val breachDate: String = "",
        @SerialName("added_date") val addedDate: String = "",
        val accounts: Long = 0,
        @SerialName("data_classes") val dataClasses: List<String> = emptyList(),
        val verified: Boolean = false,
        val sensitive: Boolean = false,
        @SerialName("stealer_log") val stealerLog: Boolean = false,
        val logo: String? = null,
        /** MyRecon's 0–100 score, computed at build time on the site. */
        val severity: Int = 0,
        val band: String = "",
        @SerialName("data_provider") val dataProvider: String? = null,
        val summary: String = "",
    )

    @Serializable
    data class Feed(
        val generated: String = "",
        val source: String = "",
        val licence: String = "",
        @SerialName("total_accounts") val totalAccounts: Long = 0,
        val breaches: List<Article> = emptyList(),
    )

    /**
     * Held for the process lifetime once fetched.
     *
     * The site regenerates every six hours, so re-fetching on every tab switch
     * would be traffic spent to receive the same bytes. A pull-to-refresh style
     * reload is [fetch] with `force`.
     */
    @Volatile
    private var cached: Feed? = null

    suspend fun load(force: Boolean = false): Feed {
        cached?.takeIf { !force }?.let { return it }
        val feed = fetch()
        cached = feed
        return feed
    }

    private suspend fun fetch(): Feed = withContext(Dispatchers.IO) {
        val req = Request.Builder().url(FEED)
            .header("User-Agent", "MyRecon-Android/1.1 (+https://myrecon.xyz)")
            .header("Accept", "application/json")
            .build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) error("The Breach Files are unavailable (HTTP ${resp.code}).")
            val body = resp.body?.string().orEmpty()
            json.decodeFromString<Feed>(body)
        }
    }
}
