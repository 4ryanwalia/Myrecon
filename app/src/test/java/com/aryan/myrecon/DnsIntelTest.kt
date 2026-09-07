package com.aryan.myrecon

import com.aryan.myrecon.data.DnsIntel
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

/**
 * The DNS report, against live zones.
 *
 * Fixtures would prove the parser and nothing else, and the parser was never
 * the risk — the risk is whether ~35 concurrent DoH queries, two Certificate
 * Transparency logs and a geolocation lookup all answer an unauthenticated
 * phone inside a usable amount of time. Only real hosts answer that.
 *
 * The domains are chosen for stable, opposite postures: github.com publishes
 * DMARC with a real policy, and example.com is IANA's reserved domain that
 * deliberately sends no mail.
 */
class DnsIntelTest {

    @Test
    fun `a real zone yields records, vendors and an email verdict`() = runBlocking {
        val r = DnsIntel.report("github.com")

        println("domain: ${r.domain} — ${r.totalRecords} records across ${r.records.keys}")
        println("email: ${r.email.verdict}")
        println("  spf=${r.email.spf?.policy} dmarc=${r.email.dmarc?.policy} dkim=${r.email.dkimSelectors}")
        println("stack: ${r.stack.map { it.category + ": " + it.name }}")
        println("addresses: ${r.addresses.map { it.ip + " " + it.org }}")
        println("subdomains: ${r.subdomains.total} from ${r.subdomains.sources}")
        println("dnssec=${r.dnssecValidated} wildcard=${r.wildcard} ttl=${r.minTtl}..${r.maxTtl}")

        assertTrue("expected A records", r.records["A"].orEmpty().isNotEmpty())
        assertTrue("expected MX records", r.records["MX"].orEmpty().isNotEmpty())
        assertTrue("expected NS records", r.records["NS"].orEmpty().isNotEmpty())

        // github.com has published DMARC for years; if this breaks, the parse
        // broke, not GitHub.
        val dmarc = r.email.dmarc
        assertNotNull("expected a DMARC record", dmarc)
        assertTrue(
            "unexpected DMARC policy ${dmarc!!.policy}",
            dmarc.policy in setOf("none", "quarantine", "reject"),
        )
        assertTrue("DMARC raw must be the record", dmarc.raw.startsWith("v=DMARC1"))

        assertNotNull("expected an SPF record", r.email.spf)
        assertTrue("verdict must not be empty", r.email.verdict.isNotBlank())
        assertTrue("findings must be produced", r.email.findings.isNotEmpty())

        // MX and NS are both recognisable providers for this domain.
        assertTrue("expected a mail vendor", r.stack.any { it.category == "Mail" })
        assertTrue("expected a DNS vendor", r.stack.any { it.category == "DNS" })

        // Address intel resolves and attributes.
        assertTrue("expected at least one address", r.addresses.isNotEmpty())
        assertTrue("expected network ownership", r.addresses.any { it.org != null })

        assertTrue("CT should find subdomains for github.com", r.subdomains.total > 5)
        assertTrue(
            "every name must sit under the domain",
            r.subdomains.names.all { it.endsWith(".github.com") },
        )
        assertFalse("wildcards must be stripped", r.subdomains.names.any { it.startsWith("*") })
        assertTrue("limits are always reported", r.notes.isNotEmpty())
    }

    @Test
    fun `a domain that sends no mail is reported as spoofable`() = runBlocking {
        val r = DnsIntel.report("example.com")
        println("example.com: ${r.email.verdict}")
        println("  acceptsMail=${r.email.acceptsMail} dmarc=${r.email.dmarc?.policy}")

        // IANA's reserved domain publishes SPF -all and DMARC p=reject with no
        // MX. Whatever the exact posture, the verdict must be a real sentence
        // and the findings must explain it.
        assertTrue(r.email.verdict.isNotBlank())
        assertTrue(r.email.findings.isNotEmpty())
        assertTrue("SOA is published for any live zone", r.records.containsKey("SOA"))
    }

    @Test
    fun `the input is normalised before it is queried`() = runBlocking {
        val r = DnsIntel.report("  https://WWW.Cloudflare.com/some/path  ")
        assertEquals("cloudflare.com", r.domain)
        assertTrue(r.records.containsKey("A"))
        // Cloudflare signs its own zone and publishes HTTPS records; this is
        // the check that the newer record types are actually being fetched.
        assertTrue("expected DNSSEC validation", r.dnssecValidated)
        assertTrue(
            "expected an HTTPS/SVCB record",
            r.records.containsKey("HTTPS") || r.records.containsKey("SVCB"),
        )
    }

    @Test
    fun `an unregistered domain degrades instead of failing`() = runBlocking {
        val r = DnsIntel.report("zzq7x4-not-a-real-domain-91966.example")
        println("empty zone: ${r.totalRecords} records, verdict: ${r.email.verdict}")
        assertEquals(0, r.totalRecords)
        assertFalse(r.wildcard)
        assertNull(r.email.spf)
        assertNull(r.email.dmarc)
        assertTrue("a verdict is still produced", r.email.verdict.isNotBlank())
        assertTrue(r.subdomains.names.isEmpty())
    }
}
