package com.aryan.myrecon.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.contentOrNull
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
        val destination: Destination? = null,
        val payee: Payee? = null,
        val error: String? = null,
    )

    /** QR codes carry more than URLs; each type needs different handling. */
    enum class Kind { Url, WifiCredentials, ContactCard, PlainText, PhoneOrSms, Crypto, Payment }

    /**
     * What is actually at the other end, in words a person can act on.
     *
     * A final URL answers "where does this go" only for someone who reads
     * URLs. Most people scanning a code want "it opens a YouTube video" or
     * "it is a Google Form asking for your details", which is the difference
     * between a destination they expected and one they did not.
     */
    data class Destination(
        /** "YouTube video", "Play Store app", "Google Form". */
        val what: String,
        /** The page's own title, where one could be read. */
        val title: String? = null,
    )

    /** Parsed payment request. Everything here decides whether money moves. */
    data class Payee(
        val address: String,
        val name: String?,
        val amount: String?,
        val currency: String?,
        val note: String?,
    )

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
        if (kind == Kind.Payment) {
            val payee = parsePayee(scanned)
            val signals = paymentSignals(payee)
            return@withContext Report(
                scanned = scanned, finalUrl = null, host = null, redirectChain = emptyList(),
                registered = null, ageDays = null, registrar = null,
                signals = signals,
                riskScore = signals.sumOf { it.weight }.coerceIn(0, 100),
                // Never "Safe". A payment code is not dangerous by default, but
                // nothing that moves money should carry a green tick.
                verdict = Verdict.Caution,
                kind = kind,
                destination = Destination("Payment request", payee?.name),
                payee = payee,
            )
        }
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
                    "This website is not properly registered",
                    "There is no public ownership record for $base. Real businesses have one.",
                    15,
                )
            }
        }

        // ── Chain and transport ──────────────────────────────────
        val hops = chain.size
        if (hops >= 3) {
            signals += Signal(
                "It bounces through $hops addresses",
                "Scam links are often passed through several addresses to hide where they " +
                    "really end up.",
                20,
            )
        }
        chain.mapNotNull { hostOf(it) }.filter { it in SHORTENERS }.distinct().forEach {
            signals += Signal(
                "The link was shortened by $it",
                "A short link hides where it goes. MyRecon followed it so you can see the " +
                    "real destination.",
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
                "This site has no padlock. Anything you type into it — a password, a card " +
                    "number — travels in a form others on the same network can read.",
                18,
            )
        }

        // ── Host shape ───────────────────────────────────────────
        if (host != null) {
            val tld = host.substringAfterLast('.', "")
            if (tld in RISKY_TLDS) {
                signals += Signal(
                    "Cheap web address (.$tld)",
                    "Addresses ending in .$tld are free or nearly free, so scammers use " +
                        "them heavily. Plenty of honest sites use them too.",
                    14,
                )
            }
            if (host.matches(Regex("""^\d{1,3}(\.\d{1,3}){3}$"""))) {
                signals += Signal(
                    "A bare IP address instead of a website name",
                    "Real companies have a name, like example.com. A string of numbers avoids " +
                        "leaving any ownership record at all.",
                    30,
                )
            }
            impersonationOf(host)?.let { brand ->
                signals += Signal(
                    "Pretending to be \"$brand\"",
                    "The address has a well-known name buried inside it, but the site is not " +
                        "actually theirs. This is the single most common trick in scam links.",
                    40,
                )
            }
            if (host != IDN.toASCII(host) || host.any { it.code > 127 }) {
                signals += Signal(
                    "Look-alike letters in the address",
                    "The address uses letters from another alphabet that are drawn to look " +
                        "like ordinary ones. It may not be the site you think it is.",
                    35,
                )
            }
            if (host.count { it == '-' } >= 3) {
                signals += Signal(
                    "Lots of dashes in the address",
                    "Addresses like secure-login-verify-account are typical of throwaway " +
                        "sites set up for one scam.",
                    12,
                )
            }
            if (host.split('.').size >= 5) {
                signals += Signal(
                    "A very long address",
                    "A long prefix pushes the real website name off the edge of a phone " +
                        "screen, so you cannot see who you are actually visiting.",
                    15,
                )
            }
        }

        if (finalUrl == null) {
            signals += Signal(
                "The link did not open",
                "MyRecon could not reach it, so there is no way to check where it goes.",
                10,
            )
        }

        // What this actually opens. Deliberately outside the scoring: a title
        // is whatever the page calls itself, and a phishing page calls itself
        // whatever it likes. It is context for the reader, not evidence.
        val destination = finalUrl?.let { url ->
            val what = knownDestination(url, host)
            val title = pageTitle(url)
            if (what == null && title == null) null else Destination(what ?: "Web page", title)
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
            destination = destination,
        )
    }


    // ── Payment requests ─────────────────────────────────────────

    /**
     * Parse a payment intent, of which UPI is the one that matters here.
     *
     * `upi://pay?pa=someone@bank&pn=Name&am=250&cu=INR&tn=note`
     */
    fun parsePayee(raw: String): Payee? {
        val query = raw.substringAfter('?', "")
        if (query.isBlank()) return null
        val params = query.split('&').mapNotNull {
            val (k, v) = it.split('=', limit = 2).takeIf { p -> p.size == 2 } ?: return@mapNotNull null
            k.lowercase() to runCatching { java.net.URLDecoder.decode(v, "UTF-8") }.getOrDefault(v)
        }.toMap()
        val address = params["pa"] ?: params["addr"] ?: return null
        return Payee(
            address = address,
            name = params["pn"]?.takeIf { it.isNotBlank() },
            amount = params["am"]?.takeIf { it.isNotBlank() },
            currency = params["cu"]?.takeIf { it.isNotBlank() },
            note = params["tn"]?.takeIf { it.isNotBlank() },
        )
    }

    /**
     * The signals that decide whether someone should let money leave.
     *
     * The load-bearing one is the last: scanning a QR code never *receives*
     * money. "Scan this to get your refund/cashback/prize" is the single most
     * common UPI fraud in India, and the victim authorises the payment
     * themselves, which is why the bank will not reverse it. Saying so plainly
     * at the moment of scanning is worth more than any score.
     */
    private fun paymentSignals(payee: Payee?): List<Signal> {
        val out = mutableListOf<Signal>()
        if (payee == null) {
            out += Signal(
                "Payment request",
                "This code opens a payment app. Check who is being paid, and how much, on the " +
                    "confirmation screen before approving anything.",
                20,
            )
            return out
        }

        out += Signal(
            "Pays ${payee.name ?: payee.address}",
            "Money goes to ${payee.address}" +
                (payee.name?.let { ", shown as \"$it\"" } ?: "") +
                ". The name is chosen by whoever made the code and is not verified by anyone.",
            18,
        )

        if (payee.amount != null) {
            out += Signal(
                "Amount is fixed at ${payee.currency ?: ""} ${payee.amount}".trim(),
                "The code sets the amount, so the payment app may show it already filled in. " +
                    "Confirm it is what you agreed.",
                8,
            )
        } else {
            out += Signal(
                "Amount is left open",
                "You type the amount. Normal for a shop counter, and also how an overcharge " +
                    "goes unnoticed.",
                4,
            )
        }

        out += Signal(
            "Scanning never receives money",
            "A QR code can only send. If you were told this would pay you a refund, cashback " +
                "or prize, it will take money instead — and because you approve it yourself, " +
                "the bank will usually not reverse it.",
            22,
        )
        return out
    }

    // ── What is at the other end ─────────────────────────────────

    /**
     * Well-known destinations, matched on host and path shape.
     *
     * Named explicitly rather than inferred, because "youtube.com/watch" being
     * a video is a fact, while anything guessed from a page's own markup is
     * whatever that page chose to claim.
     */
    private fun knownDestination(url: String, host: String?): String? {
        val h = host?.removePrefix("www.")?.lowercase() ?: return null
        val path = runCatching { java.net.URI(url).path.orEmpty() }.getOrDefault("")
        return when {
            h == "youtu.be" || h.endsWith("youtube.com") -> when {
                path.startsWith("/watch") || h == "youtu.be" -> "YouTube video"
                path.startsWith("/shorts") -> "YouTube Short"
                path.startsWith("/playlist") -> "YouTube playlist"
                else -> "YouTube page"
            }
            h.endsWith("play.google.com") -> "Google Play app listing"
            h.endsWith("apps.apple.com") -> "App Store listing"
            h.endsWith("docs.google.com") && path.contains("/forms") -> "Google Form — it can ask you for personal details"
            h.endsWith("forms.gle") -> "Google Form — it can ask you for personal details"
            h.endsWith("docs.google.com") -> "Google Docs file"
            h.endsWith("drive.google.com") -> "Google Drive file"
            h.endsWith("maps.google.com") || h == "maps.app.goo.gl" || h == "goo.gl" && path.startsWith("/maps") -> "Google Maps location"
            h.endsWith("instagram.com") -> if (path.startsWith("/p/") || path.startsWith("/reel")) "Instagram post" else "Instagram profile"
            h.endsWith("wa.me") || h.endsWith("api.whatsapp.com") -> "Opens a WhatsApp chat"
            h.endsWith("t.me") -> "Opens a Telegram chat or channel"
            h.endsWith("x.com") || h.endsWith("twitter.com") -> "Post or profile on X"
            h.endsWith("linkedin.com") -> "LinkedIn page"
            h.endsWith("facebook.com") || h.endsWith("fb.me") -> "Facebook page"
            h.endsWith("spotify.com") -> "Spotify"
            h.endsWith("github.com") -> "GitHub repository or profile"
            h.endsWith("amazon.in") || h.endsWith("amazon.com") -> "Amazon product page"
            h.endsWith("paypal.com") || h.endsWith("paypal.me") -> "PayPal payment page — it can ask you to send money"
            h.endsWith("linktr.ee") -> "Link-in-bio page"
            else -> null
        }
    }

    /**
     * The page's own title, read from the first few KB.
     *
     * Only ever presented as what the page calls itself. A phishing page will
     * happily title itself "State Bank of India", so this is context for the
     * reader, never evidence — which is why it does not feed the score.
     */
    private fun pageTitle(url: String): String? = oEmbedTitle(url) ?: htmlTitle(url)

    /**
     * Titles for hosts that will not give one to a plain HTTP client.
     *
     * YouTube answers a non-browser agent with a consent interstitial, so the
     * <title> read from its HTML is useless — which showed up as "YouTube
     * video" with no name attached, on the single most common kind of scanned
     * link. Its oEmbed endpoint is keyless and returns the real title.
     */
    private fun oEmbedTitle(url: String): String? {
        val host = hostOf(url)?.removePrefix("www.")?.lowercase() ?: return null
        val endpoint = when {
            host.endsWith("youtube.com") || host == "youtu.be" ->
                "https://www.youtube.com/oembed?format=json&url="
            host.endsWith("vimeo.com") -> "https://vimeo.com/api/oembed.json?url="
            else -> return null
        }
        return runCatching {
            val req = Request.Builder()
                .url(endpoint + java.net.URLEncoder.encode(url, "UTF-8"))
                .header("User-Agent", UA)
                .build()
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return@use null
                val body = resp.body?.string().orEmpty()
                // Parsed, not pattern-matched. A title containing a quote or a
                // backslash is ordinary, and hand-rolling that escaping is how
                // the first attempt at this silently returned nothing.
                val root = kotlinx.serialization.json.Json { ignoreUnknownKeys = true }
                    .parseToJsonElement(body) as? kotlinx.serialization.json.JsonObject
                (root?.get("title") as? kotlinx.serialization.json.JsonPrimitive)
                    ?.contentOrNull
                    ?.trim()?.take(120)?.takeIf { it.isNotBlank() }
            }
        }.getOrNull()
    }

    private fun htmlTitle(url: String): String? = runCatching {
        val req = Request.Builder().url(url)
            .header("User-Agent", UA)
            .header("Accept", "text/html,*/*;q=0.8")
            .build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) return@use null
            val head = resp.body?.source()?.let { src ->
                src.request(48_000)
                src.buffer.snapshot(minOf(src.buffer.size, 48_000L).toInt()).utf8()
            } ?: return@use null
            val m = Regex("""<title[^>]*>(.*?)</title>""",
                setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL)).find(head)
            m?.groupValues?.get(1)
                ?.replace(Regex("""\s+"""), " ")
                ?.replace("&amp;", "&")?.replace("&quot;", "\"")
                ?.replace("&#39;", "'")?.replace("&lt;", "<")?.replace("&gt;", ">")
                ?.trim()?.take(120)?.takeIf { it.isNotBlank() }
        }
    }.getOrNull()

    // ── Helpers ──────────────────────────────────────────────────

    fun classify(raw: String): Kind {
        val s = raw.trim()
        return when {
            s.startsWith("WIFI:", true) -> Kind.WifiCredentials
            s.startsWith("BEGIN:VCARD", true) || s.startsWith("MECARD:", true) -> Kind.ContactCard
            s.startsWith("tel:", true) || s.startsWith("sms:", true) ||
                s.startsWith("smsto:", true) -> Kind.PhoneOrSms
            s.startsWith("bitcoin:", true) || s.startsWith("ethereum:", true) -> Kind.Crypto
            // upi:// is the most-scanned code in India and was landing in
            // PlainText, so the one kind of QR that literally moves money got
            // no analysis at all.
            s.startsWith("upi://", true) || s.startsWith("upi:", true) ||
                s.startsWith("paytmmp://", true) || s.startsWith("phonepe://", true) ||
                s.startsWith("gpay://", true) || s.startsWith("tez://", true) -> Kind.Payment
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
