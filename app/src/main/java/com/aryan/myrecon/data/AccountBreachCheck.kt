package com.aryan.myrecon.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

/**
 * Per-address breach lookup.
 *
 * [BreachFeed] answers "what was published"; this answers "were *you* in it".
 * They are deliberately separate, because they cost different things. The
 * catalogue check is free in every sense — a public list, downloaded and
 * compared on the device, telling nobody anything. This one requires handing
 * the address to a third party, which is a real disclosure and is why nothing
 * here runs unless the user has switched it on for that specific address.
 *
 * LeakCheck's public endpoint is keyless, so the paid-API rule is not broken,
 * but it is rate-limited and deliberately vague: it names the corpora an
 * address appears in and the classes of field exposed, not the values. That is
 * the right amount for an alert — enough to act on, not enough to be a leak in
 * its own right.
 *
 * A failure returns null rather than an empty result. "We could not ask" and
 * "you are not in any breach" must never collapse into the same answer, or a
 * throttled network reads as good news.
 */
object AccountBreachCheck {

    private const val URL = "https://leakcheck.io/api/public"

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    private val json = Json { ignoreUnknownKeys = true; isLenient = true }

    /** One corpus an address was found in. */
    @Serializable
    data class Source(
        val name: String = "",
        val date: String = "",
    ) {
        /** "Robinhood.com (2021-11)", or just the name when undated. */
        val label: String get() = if (date.isBlank()) name else "$name ($date)"
    }

    @Serializable
    private data class ApiResponse(
        val success: Boolean = false,
        val found: Int = 0,
        val sources: List<Source> = emptyList(),
        val fields: List<String> = emptyList(),
        val error: String? = null,
    )

    /**
     * What an address is known to appear in.
     *
     * @return null when the lookup could not be completed — offline, throttled,
     *   or an unreadable response. Callers must treat that as "unknown", never
     *   as "clean".
     */
    data class Report(
        val email: String,
        val sources: List<Source>,
        val fields: List<String>,
    ) {
        val count: Int get() = sources.size

        /** Field classes that make a breach worth interrupting someone for. */
        val isSevere: Boolean
            get() = fields.any { it.lowercase() in SEVERE_FIELDS }
    }

    private val SEVERE_FIELDS = setOf(
        "password", "hash", "ssn", "address", "phone", "dob", "credit_card", "cvv",
    )

    suspend fun check(email: String): Report? = withContext(Dispatchers.IO) {
        val clean = email.trim().lowercase()
        if (clean.isBlank() || "@" !in clean) return@withContext null

        val url = URL.toHttpUrl().newBuilder()
            .addQueryParameter("check", clean)
            .build()

        val request = Request.Builder()
            .url(url)
            .header("User-Agent", "MyRecon/1.0 (+https://myrecon.xyz)")
            .header("Accept", "application/json")
            .get()
            .build()

        runCatching {
            client.newCall(request).execute().use { resp ->
                if (!resp.isSuccessful) return@use null
                val body = resp.body?.string().orEmpty()
                if (body.isBlank()) return@use null
                val parsed = json.decodeFromString<ApiResponse>(body)
                // success=false is the endpoint's "not found", which is a real
                // answer: an address with no known exposure. Only a transport
                // or parse failure is unknown.
                if (!parsed.success) {
                    Report(clean, emptyList(), emptyList())
                } else {
                    Report(clean, parsed.sources.filter { it.name.isNotBlank() }, parsed.fields)
                }
            }
        }.getOrNull()
    }
}
