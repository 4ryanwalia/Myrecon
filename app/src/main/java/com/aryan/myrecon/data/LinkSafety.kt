package com.aryan.myrecon.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.net.IDN
import java.time.LocalDate
import java.time.temporal.ChronoUnit
import java.util.concurrent.TimeUnit

/**
 * Link risk assessment for a scanned QR code.
 *
 * Decoding a QR is trivial; the value is in what happens next. A scanned code
 * hides its destination behind a shortener, and the single strongest signal
 * that a link is a scam is the age of the domain it finally lands on —
 * phishing infrastructure is registered days before use, because it gets taken
 * down. That check is possible here only because the RDAP lookup already
 * exists.
 *
 * Every signal is reported with its basis. A verdict without reasons is just an
 * opinion, and the user is about to decide whether to trust a link based on it.
 */
object LinkSafety {

    /** One observation contributing to the verdict. */
    data class Signal(
        val label: String,
        val detail: String,
        /** Positive raises risk, negative lowers it. */
        val weight: Int,
    )

    enum class Verdict { Safe, Caution, Dangerous, Unknown }

    data class Report(
        val scanned: String,
        val finalUrl: String?,
        val host: String?,
        val redirectChain: List<String>,
        val registered: String?,
        val ageDays: Long?,
        val registrar: String?,
        val signals: List<Signal>,
        val riskScore: Int,
        val verdict: Verdict,
        val kind: Kind,
        val error: String? = null,
    )

    /** QR codes carry more than URLs; each type needs different handling. */
    enum class Kind { Url, WifiCredentials, ContactCard, PlainText, PhoneOrSms, Crypto }

    private val client = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        // Redirects are followed manually so the whole chain can be shown — the
        // hops themselves are evidence, and a chain of three shorteners is a
        // signal no single destination reveals.
        .followRedirects(false)
        .build()

    private const val UA =
        "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) " +
            "Chrome/124.0.0.0 Mobile Safari/537.36"

    /**
     * Known URL shorteners. Their presence is not itself suspicious — plenty of
     * legitimate mail uses them — but it means the visible text tells the user
     * nothing about the destination, so the chain must be resolved.
     */
    private val SHORTENERS = setOf(
        "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly",
        "adf.ly", "bl.ink", "lnkd.in", "rebrand.ly", "cutt.ly", "shorturl.at",
        "rb.gy", "tiny.cc", "s.id", "short.io", "t.ly", "qr.ae", "v.gd",
    )

    /**
     * TLDs that are cheap or free and consequently dominate phishing samples.
     * A weak signal alone — plenty of legitimate sites use them.
     */
    private val RISKY_TLDS = setOf(
        "tk", "ml", "ga", "cf", "gq", "top", "xyz", "buzz", "click", "link",
        "work", "date", "loan", "zip", "mov", "rest", "cam", "surf",
    )

    /** Brand names typically impersonated, for lookalike detection. */
    private val IMPERSONATED = listOf(
        "paypal", "apple", "google", "microsoft", "amazon", "netflix", "meta",
        "facebook", "instagram", "whatsapp", "binance", "coinbase", "metamask",
        "dhl", "fedex", "usps", "hmrc", "irs", "nhs", "gov",
    )

    // ── Entry point ──────────────────────────────────────────────

    suspend fun analyse(scanned: String): Report = withContext(Dispatchers.IO) {
        val kind = classify(scanned)
        if (kind != Kind.Url) {
            return@withContext nonUrlReport(scanned, kind)
        }

        val chain = mutableListOf<String>()
        val finalUrl = runCatching { resolveChain(scanned, chain) }.getOrNull()
        val host = hostOf(finalUrl ?: scanned)

        val signals = mutableListOf<Signal>()
        var registered: String? = null
        var ageDays: Long? = null
        var registrar: String? = null

        // ── Domain age, the strongest single signal ──────────────
        val base = baseDomain(host)
        if (base != null) {
            val rdap = runCatching { OnDeviceIntel.domain(base) }.getOrNull()
            if (rdap?.found == true) {
                registered = rdap.whois.created
                registrar = rdap.whois.registrar
                ageDays = registered?.let { daysSince(it) }
                when {
                    ageDays == null -> Unit
                    ageDays <= 7 -> signals += Signal(
                        "Domain is $ageDays days old",
                        "Registered on $registered. Phishing domains are almost always days " +
                            "old, because they get taken down. This is the strongest warning here.",
                        45,
                    )
                    ageDays <= 30 -> signals += Signal(
                        "Domain registered this month",
                        "Created on $registered. Recent registration is common for scam " +
                            "infrastructure, though not proof of it.",
                        28,
                    )
                    ageDays <= 180 -> signals += Signal(
                        "Domain is under six months old",
                        "Created on $registered.",
                        12,
                    )
                    ageDays >= 730 -> signals += Signal(
                        "Domain is well established",
                        "Registered on $registered, over ${ageDays / 365} years ago. Long-lived " +
                            "domains are rarely used for one-off scams.",
                        -20,
                    )
                }
            } else {
                signals += Signal(
                    "No registration record",
                    "RDAP returned nothing for $base. Unusual for a legitimate site.",
                    15,
                )
            }
        }

        // ── Chain and transport ──────────────────────────────────
        val hops = chain.size
        if (hops >= 3) {
            signals += Signal(
                "$hops redirects before landing",
                "Long redirect chains are used to hide a destination from scanners.",
                20,
            )
        }
        chain.mapNotNull { hostOf(it) }.filter { it in SHORTENERS }.distinct().forEach {
            signals += Signal(
                "Shortened via $it",
                "The code did not show its destination. Resolved here so you can see it.",
                8,
            )
        }
        // Evaluate the scheme of whatever we can see. Reading only finalUrl
        // meant an unreachable host skipped this entirely — but a scam link
        // that happens to be down still said http:// on the code, and that is
        // knowable without touching the network.
        val schemeSource = finalUrl ?: scanned
        if (schemeSource.startsWith("http://", ignoreCase = true)) {
            signals += Signal(
                "Not encrypted",
                "The destination uses plain HTTP, so anything submitted travels in clear text.",
                18,
            )
        }

        // ── Host shape ───────────────────────────────────────────
        if (host != null) {
            val tld = host.substringAfterLast('.', "")
            if (tld in RISKY_TLDS) {
                signals += Signal(
                    "Cheap top-level domain (.$tld)",
                    "Free and low-cost TLDs are over-represented in phishing.",
                    14,
                )
            }
            if (host.matches(Regex("""^\d{1,3}(\.\d{1,3}){3}$"""))) {
                signals += Signal(
                    "Raw IP address instead of a name",
                    "Legitimate services publish a hostname. A bare IP avoids domain records entirely.",
                    30,
                )
            }
            impersonationOf(host)?.let { brand ->
                signals += Signal(
                    "Resembles \"$brand\" without being it",
                    "The hostname contains a well-known brand as a decoration rather than its " +
                        "real domain. This is the most common phishing pattern there is.",
                    40,
                )
            }
            if (host != IDN.toASCII(host) || host.any { it.code > 127 }) {
                signals += Signal(
                    "Non-ASCII characters in the hostname",
                    "Letters from other alphabets can be drawn to look like Latin ones, so the " +
                        "name may not be the site you think it is.",
                    35,
                )
            }
            if (host.count { it == '-' } >= 3) {
                signals += Signal(
                    "Many hyphens in the hostname",
                    "Strings like secure-login-verify-account are typical of throwaway domains.",
                    12,
                )
            }
            if (host.split('.').size >= 5) {
                signals += Signal(
                    "Deeply nested subdomains",
                    "A long prefix can push the real domain out of view on a phone's address bar.",
                    15,
                )
            }
        }

        if (finalUrl == null) {
            signals += Signal(
                "Destination unreachable",
                "The link could not be followed, so its destination is unverified.",
                10,
            )
        }

        val score = signals.sumOf { it.weight }.coerceIn(0, 100)
        Report(
            scanned = scanned,
            finalUrl = finalUrl,
            host = host,
            redirectChain = chain,
            registered = registered,
            ageDays = ageDays,
            registrar = registrar,
            signals = signals.sortedByDescending { it.weight },
            riskScore = score,
            verdict = when {
                finalUrl == null && signals.none { it.weight >= 30 } -> Verdict.Unknown
                score >= 55 -> Verdict.Dangerous
                score >= 25 -> Verdict.Caution
                else -> Verdict.Safe
            },
            kind = Kind.Url,
        )
    }

    // ── Helpers ──────────────────────────────────────────────────

    fun classify(raw: String): Kind {
        val s = raw.trim()
        return when {
            s.startsWith("WIFI:", true) -> Kind.WifiCredentials
            s.startsWith("BEGIN:VCARD", true) || s.startsWith("MECARD:", true) -> Kind.ContactCard
            s.startsWith("tel:", true) || s.startsWith("sms:", true) ||
                s.startsWith("smsto:", true) -> Kind.PhoneOrSms
            s.startsWith("bitcoin:", true) || s.startsWith("ethereum:", true) -> Kind.Crypto
            s.startsWith("http://", true) || s.startsWith("https://", true) -> Kind.Url
            // A bare domain with no scheme is still a link in practice.
            Regex("""^[a-z0-9-]+(\.[a-z0-9-]+)+(/.*)?$""", RegexOption.IGNORE_CASE).matches(s) -> Kind.Url
            else -> Kind.PlainText
        }
    }

    private fun nonUrlReport(scanned: String, kind: Kind): Report {
        val signals = when (kind) {
            Kind.WifiCredentials -> listOf(
                Signal(
                    "Wi-Fi credentials",
                    "This code joins a wireless network. A hostile network can watch and alter " +
                        "unencrypted traffic, so only use it if you trust whoever posted it.",
                    20,
                )
            )
            Kind.Crypto -> listOf(
                Signal(
                    "Cryptocurrency payment request",
                    "Crypto transfers cannot be reversed. Verify the address by another channel " +
                        "before sending anything.",
                    35,
                )
            )
            Kind.PhoneOrSms -> listOf(
                Signal(
                    "Dials or texts a number",
                    "Premium-rate numbers are a common charge scam. Check the number before use.",
                    18,
                )
            )
            Kind.ContactCard -> listOf(
                Signal("Contact card", "Adds someone to your address book. No network risk.", 0)
            )
            else -> emptyList()
        }
        val score = signals.sumOf { it.weight }
        return Report(
            scanned = scanned, finalUrl = null, host = null, redirectChain = emptyList(),
            registered = null, ageDays = null, registrar = null,
            signals = signals, riskScore = score,
            verdict = if (score >= 25) Verdict.Caution else Verdict.Safe,
            kind = kind,
        )
    }

    /** Follow redirects by hand, recording each hop. Capped to stop loops. */
    private fun resolveChain(start: String, chain: MutableList<String>, max: Int = 8): String {
        var current = if (start.startsWith("http", true)) start else "https://$start"
        repeat(max) {
            chain += current
            val req = Request.Builder().url(current)
                .header("User-Agent", UA)
                .head()
                .build()
            val next = client.newCall(req).execute().use { resp ->
                if (resp.code !in 300..399) return current
                resp.header("Location") ?: return current
            }
            current = when {
                next.startsWith("http", true) -> next
                next.startsWith("/") -> {
                    val u = java.net.URI(current)
                    "${u.scheme}://${u.host}$next"
                }
                else -> return current
            }
        }
        return current
    }

    fun hostOf(url: String?): String? = runCatching {
        val withScheme = if (url!!.startsWith("http", true)) url else "https://$url"
        java.net.URI(withScheme).host?.lowercase()?.removePrefix("www.")
    }.getOrNull()

    /** Registrable domain, approximately — enough for an RDAP query. */
    fun baseDomain(host: String?): String? {
        val parts = host?.split('.')?.filter { it.isNotBlank() } ?: return null
        if (parts.size < 2) return null
        // Handles the common two-part suffixes (co.uk, com.au) without shipping
        // the full public suffix list.
        val twoPartSuffixes = setOf("co", "com", "net", "org", "gov", "ac", "edu")
        return if (parts.size >= 3 && parts[parts.size - 2] in twoPartSuffixes && parts.last().length == 2) {
            parts.takeLast(3).joinToString(".")
        } else {
            parts.takeLast(2).joinToString(".")
        }
    }

    /**
     * Detects a brand used as decoration rather than as the real domain.
     * `paypal.com` is fine; `paypal-secure.top` and `secure.paypal.evil.com`
     * are not.
     */
    fun impersonationOf(host: String): String? {
        val base = baseDomain(host) ?: return null
        val brandPart = base.substringBefore('.')
        return IMPERSONATED.firstOrNull { brand ->
            host.contains(brand, ignoreCase = true) && !brandPart.equals(brand, ignoreCase = true)
        }
    }

    private fun daysSince(isoDate: String): Long? = runCatching {
        ChronoUnit.DAYS.between(LocalDate.parse(isoDate.take(10)), LocalDate.now())
    }.getOrNull()
}
