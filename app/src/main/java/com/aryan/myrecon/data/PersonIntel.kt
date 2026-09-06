package com.aryan.myrecon.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.*
import okhttp3.OkHttpClient
import okhttp3.Request
import java.net.URLEncoder
import java.util.concurrent.TimeUnit

/**
 * Structured sources that answer a *name* rather than a handle.
 *
 * A web search tells you which pages mention a name. These three tell you
 * something better: a record, published by someone who curates it, that ties a
 * name to a LinkedIn profile, an employer, a field of work. Wikidata alone
 * turns "Satya Nadella" into the LinkedIn ID `satyanadella`, an X handle, an
 * employer, an education history and a Wikipedia article — none of it scraped,
 * all of it keyless.
 *
 *   • Wikidata   — public figures; carries explicit LinkedIn (P6634), X,
 *                  Instagram, Facebook, YouTube and GitHub identifiers.
 *   • GitHub     — `in:fullname` search; developers who put a real name on
 *                  their account, with company and location attached.
 *   • ORCID      — researchers, with institutional affiliation.
 *
 * Everything here returns *candidates*. Two people share a name constantly,
 * and a record that matches the string is not a record of the person searched
 * for. The description is carried alongside every candidate precisely so the
 * user can make that judgement rather than the app making it for them — the
 * same reason the investigation graph refuses to derive handles from names.
 */
object PersonIntel {

    private val client = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    private const val UA = "MyRecon-Android/1.1 (+https://myrecon.xyz)"

    private suspend fun json(url: String, accept: String = "application/json"): JsonElement? =
        withContext(Dispatchers.IO) {
            val req = Request.Builder().url(url)
                .header("User-Agent", UA)
                .header("Accept", accept)
                .build()
            runCatching {
                client.newCall(req).execute().use { resp ->
                    if (!resp.isSuccessful) return@use null
                    Json.parseToJsonElement(resp.body?.string().orEmpty())
                }
            }.getOrNull()
        }

    private fun enc(s: String) = URLEncoder.encode(s, "UTF-8")

    private fun JsonElement?.obj(): JsonObject? = this as? JsonObject
    private fun JsonElement?.arr(): JsonArray? = this as? JsonArray
    private fun JsonObject?.str(key: String): String? =
        (this?.get(key) as? JsonPrimitive)?.contentOrNull
            ?.takeIf { it.isNotBlank() && it != "null" }

    /** An identifier or profile URL a record hands us. */
    data class Link(val label: String, val url: String, val handle: String? = null)

    // ── Wikidata ─────────────────────────────────────────────────

    /** A person Wikidata has an entry for, and what it says about them. */
    data class Person(
        val name: String,
        val description: String,
        val wikidataId: String,
        val wikipedia: String?,
        val image: String?,
        /** Occupation, employer, education, nationality, date of birth. */
        val facts: List<Pair<String, String>>,
        /** LinkedIn, X, Instagram, Facebook, YouTube, GitHub, website. */
        val links: List<Link>,
    )

    private const val WD = "https://www.wikidata.org/w/api.php"

    /** JsonObject is itself a Map, so `orEmpty()` on a null one widens the
     *  type away from JsonObject. An explicit empty avoids that. */
    private val EMPTY_OBJ = JsonObject(emptyMap())

    /**
     * Properties worth reading off a person entry.
     *
     * P6634 is the one that makes this feature work: Wikidata records a
     * person's LinkedIn profile ID as a first-class identifier, so a name goes
     * to a LinkedIn URL without guessing at a slug.
     */
    private val SOCIAL_PROPS = listOf(
        Triple("P6634", "LinkedIn", "https://www.linkedin.com/in/%s"),
        Triple("P2002", "X (Twitter)", "https://x.com/%s"),
        Triple("P2003", "Instagram", "https://www.instagram.com/%s"),
        Triple("P2013", "Facebook", "https://www.facebook.com/%s"),
        Triple("P2397", "YouTube", "https://www.youtube.com/channel/%s"),
        Triple("P2037", "GitHub", "https://github.com/%s"),
        Triple("P4264", "LinkedIn (company)", "https://www.linkedin.com/company/%s"),
    )

    /** Item-valued properties, rendered as facts once their labels resolve. */
    private val ITEM_FACTS = listOf(
        "P106" to "Occupation",
        "P108" to "Employer",
        "P69" to "Educated at",
        "P27" to "Citizenship",
    )

    /**
     * Look a name up in Wikidata and return the human entries that match.
     *
     * Three round trips at most: search for candidates, read their claims in
     * one batch, then resolve the item-valued claims' labels in one more. Doing
     * it per-candidate would be a dozen requests for a screen that has to feel
     * immediate.
     */
    suspend fun wikidata(name: String, limit: Int = 3): List<Person> {
        val search = json(
            "$WD?action=wbsearchentities&search=${enc(name)}&language=en&uselang=en" +
                "&type=item&format=json&origin=*&limit=7"
        ).obj()?.get("search").arr().orEmpty()
        if (search.isEmpty()) return emptyList()

        val ids = search.mapNotNull { (it as? JsonObject).str("id") }.take(7)
        if (ids.isEmpty()) return emptyList()

        val entities = json(
            "$WD?action=wbgetentities&ids=${ids.joinToString("|")}" +
                "&props=claims%7Cdescriptions%7Clabels%7Csitelinks%2Furls" +
                "&languages=en&sitefilter=enwiki&format=json&origin=*"
        ).obj()?.get("entities").obj() ?: return emptyList()

        // Only humans. A search for a name also returns films, songs and
        // disambiguation pages, none of which are the person being looked for.
        val people = ids.mapNotNull { id ->
            val ent = entities[id].obj() ?: return@mapNotNull null
            val claims = ent["claims"].obj() ?: return@mapNotNull null
            if (!isHuman(claims)) return@mapNotNull null
            id to ent
        }.take(limit)
        if (people.isEmpty()) return emptyList()

        // Resolve every referenced item label in one batch.
        val referenced = people.flatMap { (_, ent) ->
            val claims = ent["claims"].obj() ?: EMPTY_OBJ
            ITEM_FACTS.flatMap { (prop, _) -> itemIds(claims, prop).take(3) }
        }.distinct().take(48)
        val labels = if (referenced.isEmpty()) emptyMap() else resolveLabels(referenced)

        return people.map { (id, ent) ->
            val claims = ent["claims"].obj() ?: EMPTY_OBJ

            val facts = buildList {
                ITEM_FACTS.forEach { (prop, label) ->
                    val values = itemIds(claims, prop).take(3).mapNotNull { labels[it] }
                    if (values.isNotEmpty()) add(label to values.joinToString(", "))
                }
                timeValue(claims, "P569")?.let { add("Born" to it) }
                timeValue(claims, "P570")?.let { add("Died" to it) }
            }

            val links = buildList {
                SOCIAL_PROPS.forEach { (prop, label, template) ->
                    stringValue(claims, prop)?.let {
                        add(Link(label, template.format(enc(it).replace("+", "%20")), it))
                    }
                }
                stringValue(claims, "P856")?.let { add(Link("Official website", it)) }
            }

            Person(
                name = ent["labels"].obj()?.get("en").obj().str("value") ?: name,
                description = ent["descriptions"].obj()?.get("en").obj().str("value").orEmpty(),
                wikidataId = id,
                wikipedia = ent["sitelinks"].obj()?.get("enwiki").obj().str("url"),
                image = stringValue(claims, "P18")?.let {
                    "https://commons.wikimedia.org/wiki/Special:FilePath/" +
                        enc(it).replace("+", "%20") + "?width=240"
                },
                facts = facts,
                links = links,
            )
        }.filter { it.links.isNotEmpty() || it.facts.isNotEmpty() }
    }

    /** P31 (instance of) = Q5 (human). */
    private fun isHuman(claims: JsonObject): Boolean =
        itemIds(claims, "P31").contains("Q5")

    private fun snaks(claims: JsonObject, prop: String): List<JsonObject> =
        claims[prop].arr().orEmpty().mapNotNull { (it as? JsonObject)?.get("mainsnak").obj() }

    private fun stringValue(claims: JsonObject, prop: String): String? =
        snaks(claims, prop).firstNotNullOfOrNull { snak ->
            (snak["datavalue"].obj()?.get("value") as? JsonPrimitive)?.contentOrNull
        }?.takeIf { it.isNotBlank() }

    private fun itemIds(claims: JsonObject, prop: String): List<String> =
        snaks(claims, prop).mapNotNull { snak ->
            snak["datavalue"].obj()?.get("value").obj().str("id")
        }

    private val MONTHS = listOf(
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    )

    /**
     * Wikidata times carry their own precision — 9 is year-only, 11 is a full
     * date. Printing "1 January 1967" for a year-precision value would invent
     * a day the record does not claim.
     */
    private fun timeValue(claims: JsonObject, prop: String): String? {
        val value = snaks(claims, prop).firstNotNullOfOrNull {
            it["datavalue"].obj()?.get("value").obj()
        } ?: return null
        val time = value.str("time") ?: return null
        val precision = (value["precision"] as? JsonPrimitive)?.contentOrNull?.toIntOrNull() ?: 11
        val year = time.drop(1).take(4)
        if (precision <= 9) return year
        val month = time.drop(6).take(2).toIntOrNull() ?: return year
        if (precision == 10) return "${MONTHS.getOrNull(month - 1) ?: month} $year"
        val day = time.drop(9).take(2).toIntOrNull() ?: return year
        return "$day ${MONTHS.getOrNull(month - 1) ?: month} $year"
    }

    private suspend fun resolveLabels(ids: List<String>): Map<String, String> {
        val entities = json(
            "$WD?action=wbgetentities&ids=${ids.joinToString("|")}" +
                "&props=labels&languages=en&format=json&origin=*"
        ).obj()?.get("entities").obj() ?: return emptyMap()
        return ids.mapNotNull { id ->
            entities[id].obj()?.get("labels").obj()?.get("en").obj().str("value")
                ?.let { id to it }
        }.toMap()
    }

    // ── GitHub ───────────────────────────────────────────────────

    /** A GitHub account whose profile carries this name. */
    data class Developer(
        val login: String,
        val url: String,
        val avatar: String?,
        val name: String?,
        val company: String?,
        val location: String?,
        val blog: String?,
        val bio: String?,
    )

    /**
     * Search accounts by the name on the profile, not the handle.
     *
     * Unauthenticated search allows ten requests a minute, which is plenty for
     * one query; detail is then fetched for the top few only, because that
     * endpoint has a separate and much tighter hourly budget.
     */
    suspend fun github(name: String, limit: Int = 3): List<Developer> {
        val items = json(
            "https://api.github.com/search/users?q=" +
                enc("\"$name\" in:fullname") + "&per_page=$limit",
            accept = "application/vnd.github+json",
        ).obj()?.get("items").arr().orEmpty().mapNotNull { it as? JsonObject }
        if (items.isEmpty()) return emptyList()

        return items.take(limit).mapNotNull { item ->
            val login = item.str("login") ?: return@mapNotNull null
            val detail = json(
                "https://api.github.com/users/$login",
                accept = "application/vnd.github+json",
            ).obj()
            // `in:fullname` also matches the bio, so a search for a well-known
            // name returns everyone who quoted them. Keep only accounts whose
            // profile name is actually the name searched.
            if (!detail.str("name").orEmpty().contains(name, ignoreCase = true)) {
                return@mapNotNull null
            }
            Developer(
                login = login,
                url = item.str("html_url") ?: "https://github.com/$login",
                avatar = item.str("avatar_url"),
                name = detail.str("name"),
                company = detail.str("company"),
                location = detail.str("location"),
                blog = detail.str("blog"),
                bio = detail.str("bio")?.take(200),
            )
        }
    }

    // ── ORCID ────────────────────────────────────────────────────

    /** A researcher registered under this name. */
    data class Researcher(
        val orcid: String,
        val name: String,
        val institutions: List<String>,
    ) {
        val url: String get() = "https://orcid.org/$orcid"
    }

    /**
     * ORCID's public search. Free, keyless, and the registry academics
     * maintain themselves, so an affiliation here is self-published rather
     * than inferred.
     */
    suspend fun orcid(name: String, limit: Int = 3): List<Researcher> {
        val parts = name.trim().split(Regex("\\s+"))
        if (parts.size < 2) return emptyList()
        val given = parts.first()
        val family = parts.last()

        val results = json(
            "https://pub.orcid.org/v3.0/expanded-search/?q=" +
                enc("given-names:$given AND family-name:$family") + "&rows=$limit"
        ).obj()?.get("expanded-result").arr().orEmpty().mapNotNull { it as? JsonObject }

        return results.mapNotNull { r ->
            val id = r.str("orcid-id") ?: return@mapNotNull null
            Researcher(
                orcid = id,
                name = listOfNotNull(r.str("given-names"), r.str("family-names"))
                    .joinToString(" ").ifBlank { name },
                institutions = r["institution-name"].arr().orEmpty()
                    .mapNotNull { (it as? JsonPrimitive)?.contentOrNull }
                    .filter { it.isNotBlank() }
                    .distinct().take(3),
            )
        }
    }
}
