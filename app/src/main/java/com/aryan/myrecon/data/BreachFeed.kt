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
 * The catalogue of publicly known breaches.
 *
 * Have I Been Pwned's /breaches endpoint is keyless — only per-account queries
 * need a paid key — so the full list of 1000+ breaches can be pulled on-device
 * for nothing. Comparing today's list against the last one seen is how the app
 * learns that something new was published.
 *
 * That comparison is the only honest basis for a notification: "a breach you
 * have not been told about exists" is genuinely new information the user could
 * not have known. Anything else would be a reminder, and reminders are how apps
 * get uninstalled.
 */
object BreachFeed {

    private const val URL = "https://haveibeenpwned.com/api/v3/breaches"

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    private val json = Json { ignoreUnknownKeys = true; isLenient = true }

    @Serializable
    data class Breach(
        @SerialName("Name") val name: String = "",
        @SerialName("Title") val title: String = "",
        @SerialName("Domain") val domain: String = "",
        @SerialName("BreachDate") val breachDate: String = "",
        @SerialName("AddedDate") val addedDate: String = "",
        @SerialName("PwnCount") val pwnCount: Long = 0,
        @SerialName("Description") val description: String = "",
        @SerialName("LogoPath") val logoPath: String = "",
        @SerialName("DataClasses") val dataClasses: List<String> = emptyList(),
        @SerialName("IsVerified") val isVerified: Boolean = false,
        @SerialName("IsStealerLog") val isStealerLog: Boolean = false,
        @SerialName("IsSpamList") val isSpamList: Boolean = false,
    ) {
        val displayTitle: String get() = title.ifBlank { name }

        /** Data classes that actually change what a person should do. */
        val severeExposure: List<String>
            get() = dataClasses.filter { d ->
                listOf("password", "bank", "credit card", "ssn", "social security",
                    "passport", "government", "security question", "credit status")
                    .any { it in d.lowercase() }
            }

        val isSevere: Boolean get() = severeExposure.isNotEmpty()
    }

    /** Fetch the full catalogue, newest first. */
    suspend fun fetchAll(): List<Breach> = withContext(Dispatchers.IO) {
        val req = Request.Builder().url(URL)
            .header("User-Agent", "MyRecon-Android/1.0")
            .header("Accept", "application/json")
            .build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) error("Breach catalogue unavailable (HTTP ${resp.code}).")
            json.decodeFromString<List<Breach>>(resp.body?.string().orEmpty())
                .sortedByDescending { it.addedDate }
        }
    }

    /**
     * Breaches published since the app last looked.
     *
     * Spam lists and stealer logs are excluded from *alerts*: they are added in
     * bulk and are not a discrete event a person can act on, so notifying about
     * them would train the user to ignore the channel. They still appear in the
     * in-app list.
     */
    fun newSince(all: List<Breach>, alreadySeen: Set<String>): List<Breach> =
        all.filter { it.name !in alreadySeen && !it.isSpamList && !it.isStealerLog }

    /** The line shown in a notification. Concrete numbers, no drama. */
    fun headline(b: Breach): String {
        val count = when {
            b.pwnCount >= 1_000_000 -> "%.0f million".format(b.pwnCount / 1e6)
            b.pwnCount >= 1_000 -> "%,d".format(b.pwnCount)
            else -> b.pwnCount.toString()
        }
        val what = b.severeExposure.firstOrNull()?.lowercase()
        return if (what != null) {
            "$count accounts exposed, including $what."
        } else {
            "$count accounts exposed."
        }
    }
}
