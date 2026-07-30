package com.aryan.myrecon.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.*
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

/**
 * Turns GPS coordinates into a named place.
 *
 * This is the honest substitute for visual landmark recognition, which needs a
 * paid vision API. When a photo carries GPS — and many do — resolving those
 * coordinates is *more* reliable than recognising a building from pixels: Big
 * Ben resolves to "Big Ben, Bridge Street, Westminster" with a Wikidata id and
 * the eight nearest notable places, from the numbers alone.
 *
 * The trade is stated rather than hidden: no GPS, no result. Nothing is guessed
 * from image content.
 *
 * Sources, both keyless:
 *   Nominatim (OpenStreetMap) — reverse geocoding
 *   Wikipedia REST + Action API — article summary and nearby places
 */
object GeoIntel {

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    // Nominatim's policy requires a genuine identifying agent with contact
    // details. A browser UA is a violation and gets the address blocked.
    private const val UA = "MyRecon-Android/1.0 (https://myrecon.xyz; abuse@myrecon.xyz)"

    /**
     * At most one Nominatim request per second, enforced across coroutines.
     * Exceeding it gets the IP banned, which would break the feature for every
     * user of the app — so this is not optional politeness.
     */
    private val throttle = Mutex()
    private var lastCall = 0L
    private const val MIN_INTERVAL_MS = 1_100L

    data class Place(
        val found: Boolean,
        val name: String? = null,
        val displayName: String? = null,
        val city: String? = null,
        val state: String? = null,
        val country: String? = null,
        val countryCode: String? = null,
        val postcode: String? = null,
        val wikidata: String? = null,
        val osmUrl: String? = null,
    )

    data class Article(
        val title: String,
        val description: String?,
        val extract: String?,
        val url: String?,
        val thumbnail: String?,
    )

    data class Nearby(val title: String, val distanceM: Double, val url: String)

    data class Report(
        val latitude: Double,
        val longitude: Double,
        val mapsUrl: String,
        val place: Place,
        val article: Article?,
        val nearby: List<Nearby>,
        val confidence: Int,
        val confidenceLabel: String,
        val error: String? = null,
    )

    fun validCoords(lat: Double?, lon: Double?): Boolean {
        if (lat == null || lon == null) return false
        // Reject null island exactly: 0,0 is overwhelmingly a zeroed GPS field
        // rather than a real position in the Gulf of Guinea.
        if (lat == 0.0 && lon == 0.0) return false
        return lat in -90.0..90.0 && lon in -180.0..180.0
    }

    suspend fun investigate(lat: Double, lon: Double): Report = withContext(Dispatchers.IO) {
        if (!validCoords(lat, lon)) {
            return@withContext Report(
                lat, lon, mapsUrl(lat, lon), Place(false), null, emptyList(), 0, "none",
                error = "No usable GPS coordinates.",
            )
        }

        val place = runCatching { reverseGeocode(lat, lon) }.getOrDefault(Place(false))
        val nearby = runCatching { nearbyPlaces(lat, lon) }.getOrDefault(emptyList())

        // Prefer the article Nominatim points at; otherwise the closest notable
        // place, which is usually the same feature under its common name.
        val article = runCatching {
            place.name?.let { summary(it) } ?: nearby.firstOrNull()?.let { summary(it.title) }
        }.getOrNull()

        var score = 0
        if (place.found) score += 30
        if (place.name != null) score += 25
        if (place.wikidata != null) score += 20
        if (article != null) score += 15
        if (nearby.firstOrNull()?.distanceM?.let { it <= 50 } == true) score += 10
        score = score.coerceAtMost(100)

        Report(
            latitude = lat, longitude = lon,
            mapsUrl = mapsUrl(lat, lon),
            place = place, article = article, nearby = nearby,
            confidence = score,
            confidenceLabel = when {
                score >= 70 -> "high"
                score >= 40 -> "medium"
                else -> "low"
            },
        )
    }

    private fun mapsUrl(lat: Double, lon: Double) =
        "https://www.openstreetmap.org/?mlat=$lat&mlon=$lon#map=17/$lat/$lon"

    // ── Sources ──────────────────────────────────────────────────

    private suspend fun reverseGeocode(lat: Double, lon: Double): Place {
        val body = throttled(
            "https://nominatim.openstreetmap.org/reverse" +
                "?lat=$lat&lon=$lon&format=jsonv2&addressdetails=1&extratags=1"
        ) ?: return Place(false)

        val o = body as? JsonObject ?: return Place(false)
        if (o["error"] != null) return Place(false)
        val addr = o["address"] as? JsonObject
        val extra = o["extratags"] as? JsonObject

        fun s(obj: JsonObject?, k: String) =
            (obj?.get(k) as? JsonPrimitive)?.contentOrNull?.takeIf { it.isNotBlank() }

        val osmType = s(o, "osm_type")
        val osmId = s(o, "osm_id")

        return Place(
            found = true,
            name = s(o, "name"),
            displayName = s(o, "display_name"),
            // Nominatim varies which key holds the settlement by country, so
            // fall through the plausible ones in decreasing specificity.
            city = s(addr, "city") ?: s(addr, "town") ?: s(addr, "village")
                ?: s(addr, "municipality") ?: s(addr, "county"),
            state = s(addr, "state"),
            country = s(addr, "country"),
            countryCode = s(addr, "country_code")?.uppercase(),
            postcode = s(addr, "postcode"),
            wikidata = s(extra, "wikidata"),
            osmUrl = if (osmType != null && osmId != null)
                "https://www.openstreetmap.org/$osmType/$osmId" else null,
        )
    }

    private fun nearbyPlaces(lat: Double, lon: Double, radiusM: Int = 1000, limit: Int = 8): List<Nearby> {
        val body = plainGet(
            "https://en.wikipedia.org/w/api.php?action=query&list=geosearch" +
                "&gscoord=$lat%7C$lon&gsradius=${radiusM.coerceIn(10, 10_000)}" +
                "&gslimit=${limit.coerceIn(1, 50)}&format=json"
        ) as? JsonObject ?: return emptyList()

        val results = ((body["query"] as? JsonObject)?.get("geosearch") as? JsonArray) ?: return emptyList()
        return results.mapNotNull { el ->
            val o = el as? JsonObject ?: return@mapNotNull null
            val title = (o["title"] as? JsonPrimitive)?.contentOrNull ?: return@mapNotNull null
            val dist = (o["dist"] as? JsonPrimitive)?.contentOrNull?.toDoubleOrNull() ?: 0.0
            Nearby(title, dist, "https://en.wikipedia.org/wiki/" + title.replace(' ', '_'))
        }
    }

    private fun summary(title: String): Article? {
        val o = plainGet(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" +
                title.replace(' ', '_').replace("/", "%2F")
        ) as? JsonObject ?: return null

        fun s(obj: JsonObject?, k: String) = (obj?.get(k) as? JsonPrimitive)?.contentOrNull
        val resolved = s(o, "title") ?: return null
        if (s(o, "type")?.contains("not_found") == true) return null

        return Article(
            title = resolved,
            description = s(o, "description"),
            extract = s(o, "extract"),
            url = ((o["content_urls"] as? JsonObject)?.get("desktop") as? JsonObject)
                ?.let { s(it, "page") },
            thumbnail = (o["thumbnail"] as? JsonObject)?.let { s(it, "source") },
        )
    }

    // ── Transport ────────────────────────────────────────────────

    private suspend fun throttled(url: String): JsonElement? {
        throttle.withLock {
            val wait = MIN_INTERVAL_MS - (System.currentTimeMillis() - lastCall)
            if (wait > 0) kotlinx.coroutines.delay(wait)
            lastCall = System.currentTimeMillis()
        }
        return plainGet(url)
    }

    /** Wikipedia has no comparable limit at this volume, so it skips the throttle. */
    private fun plainGet(url: String): JsonElement? = runCatching {
        val req = Request.Builder().url(url)
            .header("User-Agent", UA)
            .header("Accept", "application/json")
            .build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) return null
            Json.parseToJsonElement(resp.body?.string().orEmpty())
        }
    }.getOrNull()
}
