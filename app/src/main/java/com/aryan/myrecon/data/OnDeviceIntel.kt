package com.aryan.myrecon.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.*
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

/**
 * Lookups performed straight from the phone, with no MyRecon server involved.
 *
 * Why this exists: the backend runs on a free tier that sleeps, so a cold
 * request can stall for the better part of a minute. Every source below is
 * public and keyless, which means the phone can query it directly — the result
 * arrives in a second or two, works when our server is down, and the query
 * never passes through infrastructure we operate.
 *
 * The username sweep deliberately stays on the server: it fans out to 100+
 * hosts and that is genuine server work, not something to run on a battery.
 *
 * Every source here was verified reachable and keyless before being wired in:
 *   • Cloudflare DNS-over-HTTPS  — DNS records
 *   • rdap.org                   — domain registration (RDAP, the WHOIS successor)
 *   • ipwho.is                   — IP geolocation and network ownership
 *   • XposedOrNot                — breach corpus for an email address
 */
object OnDeviceIntel {

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    private const val UA = "MyRecon-Android/1.0 (+https://myrecon.xyz)"

    private suspend fun getJson(url: String, accept: String = "application/json"): JsonElement? =
        withContext(Dispatchers.IO) {
            val req = Request.Builder().url(url)
                .header("User-Agent", UA)
                .header("Accept", accept)
                .build()
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return@withContext null
                val text = resp.body?.string().orEmpty()
                runCatching { Json.parseToJsonElement(text) }.getOrNull()
            }
        }

    private fun JsonElement?.obj(): JsonObject? = this as? JsonObject
    private fun JsonObject?.str(key: String): String? =
        (this?.get(key) as? JsonPrimitive)?.takeIf { it.isString || it.contentOrNull != null }?.contentOrNull
            ?.takeIf { it.isNotBlank() && it != "null" }
    private fun JsonObject?.num(key: String): Double? =
        (this?.get(key) as? JsonPrimitive)?.contentOrNull?.toDoubleOrNull()
    private fun JsonObject?.bool(key: String): Boolean? =
        (this?.get(key) as? JsonPrimitive)?.contentOrNull?.toBooleanStrictOrNull()

    // ── DNS over HTTPS ───────────────────────────────────────────

    /** Numeric RR types, per IANA. DoH JSON answers carry the number, not a name. */
    private val RECORD_TYPES = listOf(
        "A" to 1, "AAAA" to 28, "MX" to 15, "NS" to 2,
        "TXT" to 16, "CNAME" to 5, "SOA" to 6, "CAA" to 257,
    )

    /**
     * Resolve every record type in parallel.
     *
     * Sequentially this is eight round trips; concurrently it is one, which is
     * the difference between a sluggish screen and an instant one.
     */
    suspend fun dns(domain: String): DnsResult = coroutineScope {
        val clean = domain.trim().removePrefix("http://").removePrefix("https://")
            .substringBefore('/').removePrefix("www.")

        val jobs = RECORD_TYPES.map { (label, type) ->
            async {
                val url = "https://cloudflare-dns.com/dns-query?name=$clean&type=$type"
                val body = getJson(url, accept = "application/dns-json").obj()
                val answers = (body?.get("Answer") as? JsonArray).orEmpty()
                label to answers.mapNotNull { ans ->
                    val o = ans as? JsonObject ?: return@mapNotNull null
                    val data = o.str("data") ?: return@mapNotNull null
                    DnsRecord(value = data, ttl = o.num("TTL")?.toInt())
                }
            }
        }

        val records = jobs.awaitAll().filter { it.second.isNotEmpty() }.toMap()
        DnsResult(
            query = DomainQuery(clean),
            records = records,
            summary = DnsSummary(totalRecords = records.values.sumOf { it.size }),
        )
    }

    // ── RDAP (domain registration) ───────────────────────────────

    /**
     * RDAP is the structured replacement for WHOIS and is served over HTTPS
     * with a documented JSON shape, which is why this can run client-side at
     * all — scraping WHOIS text would not survive on a phone.
     */
    suspend fun domain(name: String): DomainResult {
        val clean = name.trim().removePrefix("http://").removePrefix("https://")
            .substringBefore('/').removePrefix("www.").lowercase()

        val body = getJson("https://rdap.org/domain/$clean").obj()
            ?: return DomainResult(
                found = false,
                query = DomainQuery(clean),
                error = "No registration record found for this domain.",
            )

        val events = (body["events"] as? JsonArray).orEmpty().mapNotNull { it as? JsonObject }
        fun eventDate(action: String): String? = events
            .firstOrNull { it.str("eventAction").equals(action, ignoreCase = true) }
            ?.str("eventDate")?.take(10)

        // The registrar is an entity with the "registrar" role; its name lives
        // in a vCard array, which is positional rather than keyed.
        val registrar = (body["entities"] as? JsonArray).orEmpty()
            .mapNotNull { it as? JsonObject }
            .firstOrNull { e ->
                (e["roles"] as? JsonArray).orEmpty()
                    .any { (it as? JsonPrimitive)?.contentOrNull == "registrar" }
            }
            ?.let { e ->
                (e["vcardArray"] as? JsonArray)?.getOrNull(1)?.let { vc ->
                    (vc as? JsonArray).orEmpty().mapNotNull { it as? JsonArray }
                        .firstOrNull { (it.getOrNull(0) as? JsonPrimitive)?.contentOrNull == "fn" }
                        ?.getOrNull(3)?.let { (it as? JsonPrimitive)?.contentOrNull }
                }
            }

        val nameservers = (body["nameservers"] as? JsonArray).orEmpty()
            .mapNotNull { (it as? JsonObject).str("ldhName")?.lowercase() }

        val status = (body["status"] as? JsonArray).orEmpty()
            .mapNotNull { (it as? JsonPrimitive)?.contentOrNull }

        return DomainResult(
            found = true,
            query = DomainQuery(clean),
            whois = Whois(
                registrar = registrar,
                created = eventDate("registration"),
                expires = eventDate("expiration"),
                updated = eventDate("last changed") ?: eventDate("last update of RDAP database"),
                status = status,
                nameservers = nameservers,
            ),
        )
    }

    // ── IP intelligence ──────────────────────────────────────────

    suspend fun ip(address: String): IpResult {
        val clean = address.trim()
        val body = getJson("https://ipwho.is/$clean").obj()
            ?: return IpResult(found = false, query = IpQuery(clean), error = "Lookup service unreachable.")

        if (body.bool("success") == false) {
            return IpResult(
                found = false, query = IpQuery(clean),
                error = body.str("message") ?: "No data available for this address.",
            )
        }

        val conn = body["connection"].obj()
        val tz = body["timezone"].obj()
        return IpResult(
            found = true,
            query = IpQuery(clean),
            geo = Geo(
                city = body.str("city"),
                region = body.str("region"),
                country = body.str("country"),
                lat = body.num("latitude"),
                lon = body.num("longitude"),
                timezone = tz.str("id"),
            ),
            network = Network(
                asn = conn.num("asn")?.toInt()?.let { "AS$it" },
                org = conn.str("org"),
                isp = conn.str("isp"),
                // ipwho.is exposes no hosting flag; leaving it null is honest,
                // and the UI renders null as an em dash rather than "No".
                hosting = null,
            ),
        )
    }

    // ── Email breach exposure ────────────────────────────────────

    /**
     * Same XposedOrNot corpus the backend uses, queried directly.
     *
     * Only the fields the UI actually renders are parsed; the full analytics
     * document runs to 150 KB and decoding all of it on a phone would cost
     * more than it returns.
     */
    suspend fun emailBreaches(email: String): DarkWeb {
        val body = getJson("https://api.xposedornot.com/v1/breach-analytics?email=${email.trim()}").obj()
            ?: return DarkWeb(error = "Breach service unreachable.")

        val details = ((body["ExposedBreaches"].obj())?.get("breaches_details") as? JsonArray).orEmpty()
            .mapNotNull { it as? JsonObject }
        if (details.isEmpty()) return DarkWeb(breached = false)

        val metrics = body["BreachMetrics"].obj()
        // Some metrics arrive wrapped in a single-element array, others bare.
        fun firstOf(key: String): JsonObject? = when (val v = metrics?.get(key)) {
            is JsonArray -> v.firstOrNull() as? JsonObject
            is JsonObject -> v
            else -> null
        }

        val risk = firstOf("risk")
        val years = firstOf("yearwise_details")
        val timeline = years?.entries.orEmpty()
            .mapNotNull { (k, v) ->
                val year = k.removePrefix("y").toIntOrNull() ?: return@mapNotNull null
                val count = (v as? JsonPrimitive)?.contentOrNull?.toIntOrNull() ?: 0
                if (count > 0) TimelinePoint(year, count) else null
            }.sortedBy { it.year }

        val breaches = details
            .sortedByDescending { it.num("xposed_records") ?: 0.0 }
            .take(20)
            .map { b ->
                BreachDetail(
                    name = b.str("breach").orEmpty(),
                    domain = b.str("domain").orEmpty(),
                    date = b.str("xposed_date").orEmpty(),
                    records = b.num("xposed_records")?.toLong() ?: 0L,
                    industry = b.str("industry").orEmpty(),
                    verified = b.str("verified").equals("Yes", ignoreCase = true),
                    passwordRisk = b.str("password_risk").orEmpty(),
                    logo = b.str("logo").orEmpty(),
                    exposed = b.str("xposed_data").orEmpty()
                        .split(';').map { it.trim() }.filter { it.isNotEmpty() },
                    details = b.str("details").orEmpty().take(260),
                )
            }

        return DarkWeb(
            breached = true,
            count = details.size,
            riskLabel = risk.str("risk_label").orEmpty(),
            riskScore = risk.num("risk_score")?.toInt() ?: 0,
            recordsExposed = details.sumOf { (it.num("xposed_records") ?: 0.0).toLong() },
            breaches = breaches,
            timeline = timeline,
            exposedData = flattenExposed(firstOf("xposed_data")),
            pastes = (body["PastesSummary"].obj()).num("cnt")?.toInt() ?: 0,
        )
    }

    /** Flatten XposedOrNot's nested category tree into a ranked list. */
    private fun flattenExposed(tree: JsonObject?): List<ExposedData> {
        val out = mutableListOf<ExposedData>()
        (tree?.get("children") as? JsonArray).orEmpty().mapNotNull { it as? JsonObject }.forEach { group ->
            // Category labels ship with a leading emoji; keep the words.
            val category = group.str("name").orEmpty()
                .filter { it.isLetterOrDigit() || it == ' ' || it == '&' }.trim()
            (group["children"] as? JsonArray).orEmpty().mapNotNull { it as? JsonObject }.forEach { leaf ->
                val raw = leaf.str("name").orEmpty()
                out += ExposedData(
                    name = raw.removePrefix("data_"),
                    category = category,
                    count = leaf.num("value")?.toInt() ?: 0,
                )
            }
        }
        return out.sortedByDescending { it.count }
    }

    /**
     * Local address analysis — format, provider and disposability.
     * Pure computation, no network at all.
     */
    fun analyseEmail(email: String): EmailAnalysis {
        val local = email.substringBefore('@')
        val domain = email.substringAfter('@', "").lowercase()
        val (provider, type) = PROVIDERS[domain] ?: ("Custom / corporate domain" to "custom")
        return EmailAnalysis(
            provider = provider,
            providerType = type,
            deliverable = false,   // filled in by the MX lookup
            disposable = domain in DISPOSABLE,
            format = when {
                local.contains('.') -> "first.last"
                local.any { it.isDigit() } -> "name with digits"
                else -> "single token"
            },
            plusAddressing = local.contains('+'),
        )
    }

    private val PROVIDERS = mapOf(
        "gmail.com" to ("Google Gmail" to "personal"),
        "googlemail.com" to ("Google Gmail" to "personal"),
        "yahoo.com" to ("Yahoo Mail" to "personal"),
        "outlook.com" to ("Microsoft Outlook" to "personal"),
        "hotmail.com" to ("Microsoft Hotmail" to "personal"),
        "live.com" to ("Microsoft Live" to "personal"),
        "icloud.com" to ("Apple iCloud" to "personal"),
        "me.com" to ("Apple iCloud" to "personal"),
        "protonmail.com" to ("Proton Mail" to "privacy"),
        "proton.me" to ("Proton Mail" to "privacy"),
        "tutanota.com" to ("Tutanota" to "privacy"),
        "fastmail.com" to ("Fastmail" to "privacy"),
        "aol.com" to ("AOL Mail" to "personal"),
        "zoho.com" to ("Zoho Mail" to "business"),
        "gmx.com" to ("GMX Mail" to "personal"),
        "yandex.com" to ("Yandex Mail" to "personal"),
    )

    private val DISPOSABLE = setOf(
        "tempmail.com", "guerrillamail.com", "throwaway.email", "yopmail.com",
        "mailinator.com", "10minutemail.com", "trashmail.com", "sharklasers.com",
        "grr.la", "dispostable.com", "fakeinbox.com", "temp-mail.org",
        "getnada.com", "mohmal.com", "maildrop.cc", "burnermail.io",
    )

    /** Full on-device email report: local analysis + MX + breach corpus. */
    suspend fun email(address: String): EmailResult = coroutineScope {
        val clean = address.trim().lowercase()
        val domain = clean.substringAfter('@', "")

        val mxJob = async { if (domain.isBlank()) emptyList() else dns(domain).records["MX"].orEmpty() }
        val breachJob = async { runCatching { emailBreaches(clean) }.getOrElse { DarkWeb(error = it.message) } }

        val mx = mxJob.await()
        val dw = breachJob.await()
        val analysis = analyseEmail(clean).copy(
            deliverable = mx.isNotEmpty(),
            // MX answers are "10 aspmx.l.google.com." — keep the host only.
            mxHosts = mx.map { it.value.substringAfterLast(' ').trimEnd('.') },
        )

        EmailResult(
            query = EmailQuery(clean),
            analysis = analysis,
            summary = EmailSummary(
                breached = dw.breached,
                breachCount = dw.count,
                recordsExposed = dw.recordsExposed,
                riskLabel = dw.riskLabel,
                riskScore = dw.riskScore,
                deliverable = analysis.deliverable,
                disposable = analysis.disposable,
            ),
            darkweb = dw,
        )
    }
}
