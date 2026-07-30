package com.aryan.myrecon.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.*
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

/**
 * Cryptographically verified identity links.
 *
 * Everything else in this app finds accounts that *share a handle*, which is
 * suggestive and nothing more — handle reuse between unrelated people is
 * common, which is why those results carry a confidence band rather than a
 * claim.
 *
 * Keybase is different in kind. Each proof is a signed statement, published on
 * the platform it refers to, that the same key controls both accounts. That
 * makes it evidence rather than correlation.
 *
 * The interesting output is an *alias*: a linked account whose handle differs
 * from the one searched. `sindresorhus` on GitHub is `mofle` on Hacker News —
 * a connection no handle sweep could ever make, because nobody would think to
 * search for "mofle".
 *
 * Free, keyless, no account.
 */
object KeybaseIntel {

    private const val ENDPOINT = "https://keybase.io/_/api/1.0/user/lookup.json"

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    data class Proof(
        val platform: String,
        val handle: String,
        val url: String?,
        /** True when this handle differs from the one searched — the discovery. */
        val isAlias: Boolean,
    )

    data class Identity(
        val found: Boolean,
        val username: String,
        val fullName: String? = null,
        val bio: String? = null,
        val location: String? = null,
        val avatar: String? = null,
        val proofs: List<Proof> = emptyList(),
        val error: String? = null,
    ) {
        /** Linked accounts under a different name. The reason this exists. */
        val aliases: List<Proof> get() = proofs.filter { it.isAlias }
    }

    /** Human-readable names for Keybase's proof_type values. */
    private val PLATFORM_NAMES = mapOf(
        "twitter" to "Twitter / X",
        "github" to "GitHub",
        "reddit" to "Reddit",
        "hackernews" to "Hacker News",
        "facebook" to "Facebook",
        "mastodon" to "Mastodon",
        "dns" to "Domain (DNS record)",
        "generic_web_site" to "Website",
        "gitlab" to "GitLab",
        "bitcoin" to "Bitcoin address",
        "zcash" to "Zcash address",
    )

    suspend fun lookup(handle: String): Identity = withContext(Dispatchers.IO) {
        val clean = handle.trim().removePrefix("@").lowercase()
        if (clean.isEmpty()) return@withContext Identity(false, clean, error = "No handle given.")

        val body = runCatching {
            val req = Request.Builder()
                .url("$ENDPOINT?usernames=$clean&fields=proofs_summary,basics,profile,pictures")
                .header("User-Agent", "MyRecon-Android/1.0")
                .header("Accept", "application/json")
                .build()
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return@runCatching null
                Json.parseToJsonElement(resp.body?.string().orEmpty()) as? JsonObject
            }
        }.getOrNull() ?: return@withContext Identity(
            false, clean, error = "Keybase was unreachable.",
        )

        // `them` is an array whose entries are null for unknown usernames.
        val them = (body["them"] as? JsonArray)?.firstOrNull() as? JsonObject
            ?: return@withContext Identity(false, clean)

        fun str(obj: JsonObject?, key: String) =
            (obj?.get(key) as? JsonPrimitive)?.contentOrNull?.takeIf { it.isNotBlank() }

        val profile = them["profile"] as? JsonObject
        val proofs = ((them["proofs_summary"] as? JsonObject)?.get("all") as? JsonArray)
            .orEmpty()
            .mapNotNull { el ->
                val o = el as? JsonObject ?: return@mapNotNull null
                val type = str(o, "proof_type") ?: return@mapNotNull null
                val nametag = str(o, "nametag") ?: return@mapNotNull null
                Proof(
                    platform = PLATFORM_NAMES[type] ?: type.replace('_', ' '),
                    handle = nametag,
                    url = str(o, "service_url") ?: str(o, "proof_url"),
                    isAlias = !nametag.equals(clean, ignoreCase = true),
                )
            }
            // Aliases first: they are the finding, the rest is confirmation.
            .sortedByDescending { it.isAlias }

        Identity(
            found = true,
            username = str(them["basics"] as? JsonObject, "username") ?: clean,
            fullName = str(profile, "full_name"),
            bio = str(profile, "bio"),
            location = str(profile, "location"),
            avatar = ((them["pictures"] as? JsonObject)?.get("primary") as? JsonObject)
                ?.let { str(it, "url") },
            proofs = proofs,
        )
    }
}
