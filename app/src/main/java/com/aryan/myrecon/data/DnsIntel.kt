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
 * DNS, read for what it means rather than what it says.
 *
 * A record dump answers "what is published". It does not answer the questions
 * someone actually opened the tool for: can this domain be spoofed, who runs
 * its mail, which vendors does the organisation use, where does it physically
 * resolve to, and what else exists under it. Every one of those is derivable
 * from public DNS plus Certificate Transparency, keylessly, and none of it was
 * being derived.
 *
 * Five things are added on top of the raw records:
 *
 *   • **Email security** — SPF, DMARC, DKIM, MTA-STS, TLS-RPT and BIMI, parsed
 *     and reduced to a verdict. `p=none` with a perfect SPF record still means
 *     anyone can spoof the domain, and the tool should say so in those words.
 *   • **The vendor estate** — MX names the mail provider, NS names the DNS
 *     provider, and TXT verification tokens name most of the rest. An
 *     `atlassian-domain-verification` record is the organisation telling the
 *     world it runs Atlassian.
 *   • **Where it resolves** — reverse DNS, ASN, owner and country per address.
 *   • **Structural facts** — DNSSEC validation, wildcards, CAA issuers, TTLs.
 *   • **Subdomains** — from Certificate Transparency, which publishes every
 *     hostname anyone has ever requested a certificate for.
 *
 * All of it runs from the phone against Cloudflare DoH, crt.sh and Certspotter.
 * The ~35 DNS queries are issued concurrently, so the whole report costs about
 * as long as the slowest single lookup.
 */
object DnsIntel {

    // ── Result ───────────────────────────────────────────────────

    enum class Severity { Ok, Info, Warn, Bad }

    /** One judgement about the domain, with the evidence that produced it. */
    data class Finding(val text: String, val severity: Severity)

    data class Spf(
        val raw: String,
        /** What the record tells receivers to do with mail from elsewhere. */
        val policy: String,
        val includes: List<String>,
        /** RFC 7208 caps the record at ten DNS-resolving mechanisms. */
        val lookups: Int,
    )

    data class Dmarc(
        val raw: String,
        val policy: String,
        val subdomainPolicy: String?,
        val percent: Int,
        val aggregateReports: List<String>,
        val forensicReports: List<String>,
    )

    data class EmailSecurity(
        val acceptsMail: Boolean,
        val spf: Spf?,
        val dmarc: Dmarc?,
        val dkimSelectors: List<String>,
        val mtaSts: Boolean,
        val tlsRpt: Boolean,
        val bimi: Boolean,
        /** One sentence a non-specialist can act on. */
        val verdict: String,
        val severity: Severity,
        val findings: List<Finding>,
    )

    /** A product or service the domain's records reveal. */
    data class Vendor(val name: String, val category: String, val evidence: String)

    /** An address the domain resolves to, with who owns it. */
    data class Address(
        val ip: String,
        val reverse: String? = null,
        val asn: String? = null,
        val org: String? = null,
        val country: String? = null,
        val city: String? = null,
    )

    data class Caa(val tag: String, val value: String)

    data class Subdomains(
        val names: List<String> = emptyList(),
        val sources: List<String> = emptyList(),
        val total: Int = 0,
        val error: String? = null,
    )

    data class Report(
        val domain: String,
        val records: Map<String, List<DnsRecord>>,
        /** True when the resolver could cryptographically validate the answer. */
        val dnssecValidated: Boolean,
        val dsPresent: Boolean,
        val dnskeyCount: Int,
        val email: EmailSecurity,
        val stack: List<Vendor>,
        val addresses: List<Address>,
        val caa: List<Caa>,
        val wildcard: Boolean,
        val minTtl: Int?,
        val maxTtl: Int?,
        val subdomains: Subdomains,
        val notes: List<String>,
    ) {
        val totalRecords: Int get() = records.values.sumOf { it.size }
    }

    // ── Transport ────────────────────────────────────────────────

    private val client = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    private const val UA = "MyRecon-Android/1.1 (+https://myrecon.xyz)"
    private const val DOH = "https://cloudflare-dns.com/dns-query"

    private suspend fun doh(name: String, type: Int): JsonObject? =
        withContext(Dispatchers.IO) {
            val req = Request.Builder().url("$DOH?name=$name&type=$type")
                .header("User-Agent", UA)
                .header("Accept", "application/dns-json")
                .build()
            runCatching {
                client.newCall(req).execute().use { resp ->
                    if (!resp.isSuccessful) return@use null
                    Json.parseToJsonElement(resp.body?.string().orEmpty()) as? JsonObject
                }
            }.getOrNull()
        }

    private fun JsonObject?.answers(): List<JsonObject> =
        (this?.get("Answer") as? JsonArray).orEmpty().mapNotNull { it as? JsonObject }

    private fun JsonObject.data(): String? =
        (this["data"] as? JsonPrimitive)?.contentOrNull?.takeIf { it.isNotBlank() }

    private fun JsonObject.ttl(): Int? =
        (this["TTL"] as? JsonPrimitive)?.contentOrNull?.toIntOrNull()

    /** Records over 255 bytes arrive as several quoted strings; join them. */
    private fun txt(raw: String): String =
        Regex("\"([^\"]*)\"").findAll(raw)
            .joinToString("") { it.groupValues[1] }
            .ifBlank { raw.trim('"') }

    private suspend fun txtAt(name: String): List<String> =
        doh(name, 16).answers().mapNotNull { it.data() }.map(::txt)

    /** Numeric RR types, per IANA. The DoH JSON answer carries the number. */
    private val RECORD_TYPES = listOf(
        "A" to 1, "AAAA" to 28, "MX" to 15, "NS" to 2, "TXT" to 16,
        "CNAME" to 5, "SOA" to 6, "CAA" to 257,
        // HTTPS/SVCB publish ALPN, encrypted-client-hello config and address
        // hints. Increasingly the record that actually decides how a browser
        // connects, and absent from every DNS tool that stopped at the classics.
        "HTTPS" to 65, "SVCB" to 64,
        "DS" to 43, "DNSKEY" to 48,
    )

    // ── Report ───────────────────────────────────────────────────

    /**
     * Built on [Dispatchers.Default], not on the caller's thread.
     *
     * The individual network calls each switch to IO, but the work *between*
     * them does not: about thirty-five coroutines resume here, and the vendor
     * fingerprint scans every TXT record against four lookup tables. Called
     * from `viewModelScope`, all of that would land on the main thread and
     * compete with the frames that are drawing the result.
     */
    suspend fun report(input: String): Report = withContext(Dispatchers.Default) {
        buildReport(input)
    }

    private suspend fun buildReport(input: String): Report = coroutineScope {
        // Lowercase first: a pasted "HTTPS://WWW.Example.com/x" has to lose the
        // scheme and the www, and prefix matching is case-sensitive.
        val domain = input.trim().lowercase()
            .removePrefix("http://").removePrefix("https://")
            .substringBefore('/').substringBefore('?')
            .removePrefix("www.").trimEnd('.')

        // Everything that only needs one round trip goes out at once.
        val recordJobs = RECORD_TYPES.map { (label, type) ->
            async { label to doh(domain, type) }
        }
        val dmarcJob = async { txtAt("_dmarc.$domain") }
        val mtaStsJob = async { txtAt("_mta-sts.$domain") }
        val tlsRptJob = async { txtAt("_smtp._tls.$domain") }
        val bimiJob = async { txtAt("default._bimi.$domain") }
        val dkimJob = async {
            DKIM_SELECTORS.map { sel ->
                async { sel to txtAt("$sel._domainkey.$domain").any { "p=" in it || "v=DKIM1" in it } }
            }.awaitAll().filter { it.second }.map { it.first }
        }
        // A zone that answers for a name nobody registered answers for every
        // name, which makes "this subdomain exists" meaningless here.
        val wildcardJob = async {
            val probe = "mr" + (100000..999999).random() + "x.$domain"
            doh(probe, 1).answers().isNotEmpty()
        }
        val ctJob = async { certificateTransparency(domain) }

        val responses = recordJobs.awaitAll().toMap()
        val records = responses.mapNotNull { (label, body) ->
            val recs = body.answers().mapNotNull { a ->
                a.data()?.let { DnsRecord(value = it, ttl = a.ttl()) }
            }
            if (recs.isEmpty()) null else label to recs
        }.toMap()

        val txtValues = records["TXT"].orEmpty().map { txt(it.value) }
        val mx = records["MX"].orEmpty().map { it.value.substringAfterLast(' ').trimEnd('.').lowercase() }
        val ns = records["NS"].orEmpty().map { it.value.trimEnd('.').lowercase() }

        val spf = parseSpf(txtValues)
        val dmarc = parseDmarc(dmarcJob.await())
        val dkim = dkimJob.await()
        val mtaSts = mtaStsJob.await().any { it.startsWith("v=STSv1") }
        val tlsRpt = tlsRptJob.await().any { it.startsWith("v=TLSRPTv1") }
        val bimi = bimiJob.await().any { it.startsWith("v=BIMI1") }

        val addresses = addressIntel(records["A"].orEmpty().map { it.value })

        val ttls = records.values.flatten().mapNotNull { it.ttl }

        Report(
            domain = domain,
            records = records,
            // The AD bit is the resolver saying it validated the chain itself.
            dnssecValidated = (responses["A"] ?: responses["SOA"])
                ?.get("AD")?.let { (it as? JsonPrimitive)?.contentOrNull == "true" } ?: false,
            dsPresent = records.containsKey("DS"),
            dnskeyCount = records["DNSKEY"].orEmpty().size,
            email = assessEmail(
                acceptsMail = mx.isNotEmpty(),
                spf = spf, dmarc = dmarc, dkim = dkim,
                mtaSts = mtaSts, tlsRpt = tlsRpt, bimi = bimi,
            ),
            stack = fingerprint(mx, ns, txtValues, spf),
            addresses = addresses,
            caa = records["CAA"].orEmpty().mapNotNull { parseCaa(it.value) },
            wildcard = wildcardJob.await(),
            minTtl = ttls.minOrNull(),
            maxTtl = ttls.maxOrNull(),
            subdomains = ctJob.await(),
            notes = notes(),
        )
    }

    // ── SPF ──────────────────────────────────────────────────────

    /** Mechanisms that cost a DNS lookup, against RFC 7208's limit of ten. */
    private val SPF_LOOKUPS = listOf("include:", "a:", "mx:", "ptr:", "exists:", "redirect=")

    private fun parseSpf(txtValues: List<String>): Spf? {
        val raw = txtValues.firstOrNull { it.startsWith("v=spf1", ignoreCase = true) } ?: return null
        val terms = raw.split(Regex("\\s+")).filter { it.isNotBlank() }
        val all = terms.lastOrNull { it.endsWith("all", ignoreCase = true) }
        return Spf(
            raw = raw,
            policy = when (all?.firstOrNull()) {
                '-' -> "fail"       // reject anything not listed
                '~' -> "softfail"   // accept but mark
                '?' -> "neutral"    // no opinion
                '+' -> "pass"       // everyone passes — the same as no SPF
                else -> "none"
            },
            includes = terms.filter { it.startsWith("include:", ignoreCase = true) }
                .map { it.substringAfter(':') },
            lookups = terms.count { term -> SPF_LOOKUPS.any { term.startsWith(it, ignoreCase = true) } } +
                terms.count { it == "a" || it == "mx" },
        )
    }

    private fun parseDmarc(txtValues: List<String>): Dmarc? {
        val raw = txtValues.firstOrNull { it.startsWith("v=DMARC1", ignoreCase = true) } ?: return null
        val tags = raw.split(';').mapNotNull { part ->
            val (k, v) = part.split('=', limit = 2).takeIf { it.size == 2 } ?: return@mapNotNull null
            k.trim().lowercase() to v.trim()
        }.toMap()
        fun mailboxes(key: String) = tags[key].orEmpty()
            .split(',').map { it.trim().removePrefix("mailto:") }.filter { it.isNotBlank() }
        return Dmarc(
            raw = raw,
            policy = tags["p"]?.lowercase() ?: "none",
            subdomainPolicy = tags["sp"]?.lowercase(),
            percent = tags["pct"]?.toIntOrNull() ?: 100,
            aggregateReports = mailboxes("rua"),
            forensicReports = mailboxes("ruf"),
        )
    }

    /**
     * Reduce the whole email posture to one sentence.
     *
     * The sentence is about spoofing, because that is the question these
     * records exist to answer and the one a reader can act on. A domain with a
     * flawless SPF record and `p=none` is not protected — receivers are told to
     * deliver the forgery anyway — and phrasing that as "SPF configured" would
     * be technically true and practically misleading.
     */
    private fun assessEmail(
        acceptsMail: Boolean,
        spf: Spf?,
        dmarc: Dmarc?,
        dkim: List<String>,
        mtaSts: Boolean,
        tlsRpt: Boolean,
        bimi: Boolean,
    ): EmailSecurity {
        val findings = mutableListOf<Finding>()

        when {
            spf == null -> findings += Finding(
                "No SPF record. Nothing tells receivers which servers may send as this domain.",
                Severity.Bad,
            )
            spf.policy == "pass" -> findings += Finding(
                "SPF ends in +all, which passes every sender. That is weaker than having no SPF at all.",
                Severity.Bad,
            )
            spf.policy == "none" -> findings += Finding(
                "SPF has no all mechanism, so it makes no statement about unlisted senders.",
                Severity.Warn,
            )
            spf.policy == "neutral" -> findings += Finding(
                "SPF ends in ?all — explicitly no opinion on unlisted senders.",
                Severity.Warn,
            )
            spf.policy == "softfail" -> findings += Finding(
                "SPF ends in ~all: unlisted senders are marked but still delivered.",
                Severity.Info,
            )
            else -> findings += Finding("SPF ends in -all: unlisted senders are rejected.", Severity.Ok)
        }

        if (spf != null && spf.lookups > 10) findings += Finding(
            "SPF needs ${spf.lookups} DNS lookups; the limit is 10. Over it, receivers " +
                "may treat the record as permanently broken.",
            Severity.Warn,
        )

        when {
            dmarc == null -> findings += Finding(
                "No DMARC record. Receivers are given no instruction, so forgeries are " +
                    "usually delivered.",
                Severity.Bad,
            )
            dmarc.policy == "reject" && dmarc.percent >= 100 -> findings += Finding(
                "DMARC p=reject at 100%: receivers are told to refuse mail that fails.",
                Severity.Ok,
            )
            dmarc.policy == "reject" -> findings += Finding(
                "DMARC p=reject but only ${dmarc.percent}% of failing mail is covered.",
                Severity.Warn,
            )
            dmarc.policy == "quarantine" -> findings += Finding(
                "DMARC p=quarantine: failing mail goes to spam rather than being refused.",
                Severity.Warn,
            )
            else -> findings += Finding(
                "DMARC p=none — monitoring only. Failing mail is still delivered, so this " +
                    "does not stop spoofing.",
                Severity.Bad,
            )
        }

        dmarc?.subdomainPolicy?.let {
            findings += Finding(
                "Subdomain policy sp=$it applies to every subdomain.",
                if (it == "none") Severity.Warn else Severity.Ok,
            )
        }
        if (dmarc != null && dmarc.aggregateReports.isEmpty()) findings += Finding(
            "No rua address, so nobody receives the aggregate reports DMARC produces.",
            Severity.Info,
        )

        findings += if (dkim.isEmpty()) {
            Finding(
                "No DKIM key found at the common selectors. One may still exist under a " +
                    "private selector name — this check guesses, it does not enumerate.",
                Severity.Info,
            )
        } else {
            Finding("DKIM keys published at: ${dkim.joinToString(", ")}.", Severity.Ok)
        }

        if (acceptsMail) {
            if (mtaSts) findings += Finding("MTA-STS published: senders are told to require TLS.", Severity.Ok)
            if (tlsRpt) findings += Finding("TLS-RPT published: TLS failures are reported back.", Severity.Ok)
            if (!mtaSts) findings += Finding(
                "No MTA-STS. Delivery to this domain can be downgraded to plaintext by an " +
                    "attacker on the path.",
                Severity.Info,
            )
        }
        if (bimi) findings += Finding("BIMI published — a verified logo is offered to inboxes.", Severity.Info)

        val strongDmarc = dmarc != null && dmarc.percent >= 100 &&
            (dmarc.policy == "reject" || dmarc.policy == "quarantine")
        val strongSpf = spf != null && (spf.policy == "fail" || spf.policy == "softfail")

        val severity = when {
            dmarc?.policy == "reject" && dmarc.percent >= 100 && strongSpf -> Severity.Ok
            strongDmarc -> Severity.Warn
            dmarc != null || spf != null -> Severity.Bad
            else -> Severity.Bad
        }

        val verdict = when {
            dmarc?.policy == "reject" && dmarc.percent >= 100 && strongSpf ->
                "Well protected. Mail forged from this domain should be refused outright."
            dmarc?.policy == "reject" ->
                "Mostly protected, with gaps — see the findings below."
            dmarc?.policy == "quarantine" ->
                "Partly protected. Forged mail is sent to spam rather than refused, so it " +
                    "still reaches the recipient's mailbox."
            dmarc != null ->
                "Spoofable. A DMARC record exists but at p=none, which asks receivers to " +
                    "deliver forgeries and report them."
            spf != null ->
                "Spoofable. SPF alone does not stop forgery of the visible From address — " +
                    "that needs DMARC, and there is none."
            !acceptsMail ->
                "Spoofable, and this domain does not receive mail either. A domain that " +
                    "sends no mail should still publish SPF -all and DMARC p=reject."
            else -> "Spoofable. Neither SPF nor DMARC is published."
        }

        return EmailSecurity(
            acceptsMail = acceptsMail,
            spf = spf, dmarc = dmarc, dkimSelectors = dkim,
            mtaSts = mtaSts, tlsRpt = tlsRpt, bimi = bimi,
            verdict = verdict, severity = severity,
            findings = findings.sortedBy { it.severity.ordinal }.reversed(),
        )
    }

    /**
     * Selectors worth guessing.
     *
     * DKIM has no discovery mechanism — a key lives at a name the sender chose,
     * and there is no way to list them. What every scanner does instead is try
     * the selectors the large platforms hardcode, which covers most real
     * domains. A miss is reported as "not found at the common selectors", never
     * as "no DKIM".
     */
    private val DKIM_SELECTORS = listOf(
        "default", "google", "selector1", "selector2", "k1", "k2", "k3",
        "dkim", "mail", "s1", "s2", "smtp", "mandrill", "zoho", "protonmail",
        "mxvault", "sig1", "everlytickey1", "hs1", "sendgrid", "amazonses",
        "pm", "fd", "ctct1",
    )

    // ── Vendor fingerprinting ────────────────────────────────────

    private val MAIL_PROVIDERS = listOf(
        "google.com" to "Google Workspace",
        "googlemail.com" to "Google Workspace",
        "protection.outlook.com" to "Microsoft 365",
        "protonmail.ch" to "Proton Mail",
        "protonmail.com" to "Proton Mail",
        "zoho.com" to "Zoho Mail",
        "zoho.eu" to "Zoho Mail",
        "zoho.in" to "Zoho Mail",
        "messagingengine.com" to "Fastmail",
        "mimecast.com" to "Mimecast",
        "pphosted.com" to "Proofpoint",
        "ppe-hosted.com" to "Proofpoint",
        "barracudanetworks.com" to "Barracuda",
        "mx.cloudflare.net" to "Cloudflare Email Routing",
        "secureserver.net" to "GoDaddy Email",
        "improvmx.com" to "ImprovMX",
        "yandex.net" to "Yandex Mail",
        "qq.com" to "Tencent Exmail",
        "titan.email" to "Titan Email",
        "emailsrvr.com" to "Rackspace Email",
        "mailgun.org" to "Mailgun",
        "amazonaws.com" to "Amazon SES",
        "hostinger.com" to "Hostinger Email",
        "migadu.com" to "Migadu",
        "purelymail.com" to "Purelymail",
    )

    private val DNS_PROVIDERS = listOf(
        "ns.cloudflare.com" to "Cloudflare DNS",
        "awsdns" to "AWS Route 53",
        "googledomains.com" to "Google Cloud DNS",
        "ns-cloud-" to "Google Cloud DNS",
        "azure-dns" to "Azure DNS",
        "nsone.net" to "NS1",
        "akam.net" to "Akamai",
        "akamaidns" to "Akamai",
        "dnsmadeeasy.com" to "DNS Made Easy",
        "domaincontrol.com" to "GoDaddy DNS",
        "registrar-servers.com" to "Namecheap DNS",
        "digitalocean.com" to "DigitalOcean DNS",
        "vercel-dns.com" to "Vercel DNS",
        "dnsimple.com" to "DNSimple",
        "gandi.net" to "Gandi",
        "ovh.net" to "OVH",
        "name.com" to "Name.com",
        "hover.com" to "Hover",
        "wixdns.net" to "Wix",
        "shopify.com" to "Shopify",
        "squarespacedns.com" to "Squarespace",
        "netlify.com" to "Netlify DNS",
        "bigrock.in" to "BigRock",
        "hostinger.com" to "Hostinger DNS",
        "he.net" to "Hurricane Electric",
        "ultradns" to "Vercara UltraDNS",
        "constellix.com" to "Constellix",
        "dnspod.net" to "DNSPod",
        "alidns.com" to "Alibaba Cloud DNS",
    )

    /**
     * TXT verification tokens.
     *
     * These are the strongest signal in the whole record set and the least
     * looked at. A domain proves ownership to a SaaS vendor by publishing a
     * token the vendor issued, which means the TXT set is an organisation's
     * own list of the services it has signed up for.
     */
    private val TXT_VENDORS = listOf(
        "google-site-verification" to "Google",
        "ms=" to "Microsoft 365",
        "facebook-domain-verification" to "Meta Business",
        "atlassian-domain-verification" to "Atlassian",
        "atlassian-sending-domain-verification" to "Atlassian",
        "stripe-verification" to "Stripe",
        "docusign" to "DocuSign",
        "zoom-domain-verification" to "Zoom",
        "zoom_verify_" to "Zoom",
        "slack-domain-verification" to "Slack",
        "adobe-idp-site-verification" to "Adobe",
        "adobe-sign-verification" to "Adobe Sign",
        "apple-domain-verification" to "Apple",
        "dropbox-domain-verification" to "Dropbox",
        "shopify" to "Shopify",
        "globalsign-domain-verification" to "GlobalSign",
        "logmein-verification-code" to "GoTo / LogMeIn",
        "citrix-verification-code" to "Citrix",
        "miro-verification" to "Miro",
        "notion-domain-verification" to "Notion",
        "asana-domain-verification" to "Asana",
        "canva-site-verification" to "Canva",
        "mongodb-site-verification" to "MongoDB",
        "openai-domain-verification" to "OpenAI",
        "cisco-ci-domain-verification" to "Cisco",
        "workplace-domain-verification" to "Meta Workplace",
        "webexdomainverification" to "Webex",
        "pardot" to "Salesforce Pardot",
        "onetrust-domain-verification" to "OneTrust",
        "segment-site-verification" to "Segment",
        "status-page-domain-verification" to "Atlassian Statuspage",
        "twilio-domain-verification" to "Twilio",
        "loom-site-verification" to "Loom",
        "airtable-verification" to "Airtable",
        "figma-domain-verification" to "Figma",
        "smartsheet-site-validation" to "Smartsheet",
        "yandex-verification" to "Yandex",
        "detectify-verification" to "Detectify",
        "have-i-been-pwned-verification" to "Have I Been Pwned",
        "brevo-code" to "Brevo",
        "sendinblue-code" to "Brevo",
        "cloudhealth" to "VMware CloudHealth",
        "calendly-site-verification" to "Calendly",
        "wrike-verification" to "Wrike",
        "dynatrace-site-verification" to "Dynatrace",
        "workiva-site-verification" to "Workiva",
    )

    /** SPF includes name the platforms allowed to send as the domain. */
    private val SPF_SENDERS = listOf(
        "_spf.google.com" to "Google Workspace",
        "spf.protection.outlook.com" to "Microsoft 365",
        "sendgrid.net" to "SendGrid",
        "mailgun.org" to "Mailgun",
        "servers.mcsv.net" to "Mailchimp",
        "salesforce.com" to "Salesforce",
        "mandrillapp.com" to "Mandrill",
        "zendesk.com" to "Zendesk",
        "intercom.io" to "Intercom",
        "amazonses.com" to "Amazon SES",
        "spf.mtasv.net" to "Postmark",
        "hubspot.com" to "HubSpot",
        "hubspotemail.net" to "HubSpot",
        "qualtrics.com" to "Qualtrics",
        "atlassian.net" to "Atlassian",
        "stspg-customer.com" to "Atlassian Statuspage",
        "helpscoutemail.com" to "Help Scout",
        "freshdesk.com" to "Freshdesk",
        "mailjet.com" to "Mailjet",
        "brevo.com" to "Brevo",
        "sendinblue.com" to "Brevo",
        "createsend.com" to "Campaign Monitor",
        "klaviyo.com" to "Klaviyo",
        "pardot.com" to "Salesforce Pardot",
        "zoho.com" to "Zoho",
        "proofpoint.com" to "Proofpoint",
        "mimecast.com" to "Mimecast",
        "greenhouse.io" to "Greenhouse",
        "workday.com" to "Workday",
        "docusign.net" to "DocuSign",
    )

    private fun fingerprint(
        mx: List<String>,
        ns: List<String>,
        txtValues: List<String>,
        spf: Spf?,
    ): List<Vendor> {
        val out = linkedMapOf<String, Vendor>()
        fun add(name: String, category: String, evidence: String) {
            out.putIfAbsent("$category/$name", Vendor(name, category, evidence))
        }

        mx.forEach { host ->
            MAIL_PROVIDERS.firstOrNull { host.endsWith(it.first) || host.contains(it.first) }
                ?.let { add(it.second, "Mail", "MX $host") }
        }
        ns.forEach { host ->
            DNS_PROVIDERS.firstOrNull { host.contains(it.first) }
                ?.let { add(it.second, "DNS", "NS $host") }
        }
        txtValues.forEach { value ->
            val lower = value.lowercase()
            TXT_VENDORS.firstOrNull { lower.startsWith(it.first) || lower.contains(it.first) }
                ?.let { add(it.second, "Verified with", "TXT ${value.take(60)}") }
        }
        spf?.includes?.forEach { include ->
            val lower = include.lowercase()
            SPF_SENDERS.firstOrNull { lower.endsWith(it.first) || lower.contains(it.first) }
                ?.let { add(it.second, "Sends mail", "SPF include:$include") }
        }
        return out.values.toList()
    }

    // ── Address intelligence ─────────────────────────────────────

    /**
     * Who owns the addresses this name points at.
     *
     * Capped at four. Large sites round-robin dozens of addresses that all
     * belong to the same network, and the fifth lookup adds nothing the first
     * four did not already say.
     */
    private suspend fun addressIntel(ips: List<String>): List<Address> = coroutineScope {
        ips.distinct().take(4).map { ip ->
            async {
                val ptrJob = async { reverse(ip) }
                val whoJob = async { ipInfo(ip) }
                val who = whoJob.await()
                Address(
                    ip = ip,
                    reverse = ptrJob.await(),
                    asn = who?.first,
                    org = who?.second,
                    country = who?.third?.first,
                    city = who?.third?.second,
                )
            }
        }.awaitAll()
    }

    /** IPv4 reverse lookup. The v6 nibble form is omitted; PTR is rare there. */
    private suspend fun reverse(ip: String): String? {
        val octets = ip.split('.')
        if (octets.size != 4 || octets.any { it.toIntOrNull() == null }) return null
        val name = octets.reversed().joinToString(".") + ".in-addr.arpa"
        return doh(name, 12).answers().firstNotNullOfOrNull { it.data() }?.trimEnd('.')
    }

    private suspend fun ipInfo(ip: String): Triple<String?, String?, Pair<String?, String?>>? =
        withContext(Dispatchers.IO) {
            val req = Request.Builder().url("https://ipwho.is/$ip")
                .header("User-Agent", UA).build()
            runCatching {
                client.newCall(req).execute().use { resp ->
                    if (!resp.isSuccessful) return@use null
                    val body = Json.parseToJsonElement(resp.body?.string().orEmpty()) as? JsonObject
                    val conn = body?.get("connection") as? JsonObject
                    fun s(o: JsonObject?, k: String) = (o?.get(k) as? JsonPrimitive)?.contentOrNull
                        ?.takeIf { it.isNotBlank() && it != "null" }
                    Triple(
                        s(conn, "asn")?.let { "AS$it" },
                        s(conn, "org") ?: s(conn, "isp"),
                        s(body, "country") to s(body, "city"),
                    )
                }
            }.getOrNull()
        }

    // ── CAA ──────────────────────────────────────────────────────

    /** `0 issue "letsencrypt.org"` → which authorities may issue certificates. */
    private fun parseCaa(raw: String): Caa? {
        val parts = raw.trim().split(Regex("\\s+"), limit = 3)
        if (parts.size < 3) return null
        return Caa(tag = parts[1].lowercase(), value = parts[2].trim('"'))
    }

    // ── Certificate Transparency ─────────────────────────────────

    private val CT_NAME_RE = Regex("\"(?:name_value|dns_names)\"\\s*:\\s*(\"[^\"]*\"|\\[[^]]*])")

    /**
     * Subdomains, from the certificates issued for them.
     *
     * Every publicly trusted certificate is logged, and the logs are readable
     * without a key — which makes CT the one subdomain source that needs no
     * wordlist, no scanning and no permission. It finds names no bruteforce
     * would guess, and it finds them because the organisation asked a CA for
     * them.
     *
     * Both sources are queried together rather than in sequence: crt.sh has
     * the deeper history but returns 502 often enough that depending on it
     * alone means an empty section on a good day.
     */
    private suspend fun certificateTransparency(domain: String): Subdomains = coroutineScope {
        val crt = async { fetchNames("https://crt.sh/?q=%25.$domain&output=json&exclude=expired") }
        val spotter = async {
            fetchNames(
                "https://api.certspotter.com/v1/issuances?domain=$domain" +
                    "&include_subdomains=true&expand=dns_names"
            )
        }

        val sources = mutableListOf<String>()
        val names = sortedSetOf<String>()
        crt.await()?.let { sources += "crt.sh"; names += it }
        spotter.await()?.let { sources += "Certspotter"; names += it }

        if (sources.isEmpty()) {
            return@coroutineScope Subdomains(
                error = "Both Certificate Transparency sources were unreachable.",
            )
        }

        // Wildcards are not hostnames, and the apex is not a subdomain.
        val cleaned = names
            .map { it.removePrefix("*.") }
            .filter { it.endsWith(".$domain") && it != domain }
            .distinct()
            .sortedWith(compareBy({ it.count { c -> c == '.' } }, { it }))

        Subdomains(
            names = cleaned.take(250),
            sources = sources,
            total = cleaned.size,
        )
    }

    /**
     * Pull hostnames out of a CT response by pattern rather than by parsing.
     *
     * A busy domain's crt.sh document runs to megabytes, and decoding all of it
     * on a phone to keep a few hundred strings is waste. Matching the field
     * directly also survives a response that was cut short, which a JSON parse
     * would not.
     */
    private suspend fun fetchNames(url: String): List<String>? = withContext(Dispatchers.IO) {
        val req = Request.Builder().url(url)
            .header("User-Agent", UA)
            .header("Accept", "application/json")
            .build()
        runCatching {
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return@use null
                val text = resp.body?.source()?.let { source ->
                    source.request(MAX_CT_BYTES)
                    source.buffer.snapshot(minOf(source.buffer.size, MAX_CT_BYTES).toInt()).utf8()
                } ?: return@use null

                CT_NAME_RE.findAll(text).flatMap { m ->
                    m.groupValues[1]
                        .split("\\n", ",")
                        .map { it.trim().trim('[', ']', '"', ' ').lowercase() }
                        .filter { it.isNotBlank() && '.' in it && ' ' !in it }
                }.toList()
            }
        }.getOrNull()
    }

    private const val MAX_CT_BYTES = 3L * 1024 * 1024

    // ── Limits ───────────────────────────────────────────────────

    private fun notes(): List<String> = listOf(
        "DKIM has no discovery mechanism. Keys are looked for at the common selector " +
            "names the large platforms use, so \"none found\" means none at those names — " +
            "not that the domain has no DKIM.",
        "Vendors are read from records the domain publishes about itself. They show what " +
            "it has been set up to use, which is not proof that the service is still in use.",
        "Certificate Transparency lists every hostname a certificate was issued for, " +
            "including ones long retired. A name here is evidence a certificate existed, " +
            "not that the host is live.",
        "Answers come from one resolver. A domain serving different records by region " +
            "will look different from somewhere else.",
    )
}
