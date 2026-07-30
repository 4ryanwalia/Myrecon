package com.aryan.myrecon

import com.aryan.myrecon.data.OnDeviceIntel
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

/**
 * Integration tests against the real public endpoints.
 *
 * These hit the network deliberately. The parsing is the whole risk here — the
 * shapes belong to third parties and a mocked fixture would only prove the
 * mock matches itself. If one of these fails, either an upstream changed its
 * response or the app is misreading it, and both are things worth failing on.
 */
class OnDeviceIntelTest {

    @Test
    fun `dns over https returns real records`() = runBlocking {
        val r = OnDeviceIntel.dns("github.com")
        println("DNS types: ${r.records.keys}  total=${r.summary.totalRecords}")
        assertTrue("expected at least one A record", r.records["A"].orEmpty().isNotEmpty())
        assertTrue("expected MX records", r.records["MX"].orEmpty().isNotEmpty())
        assertTrue("expected NS records", r.records["NS"].orEmpty().isNotEmpty())
        assertEquals("github.com", r.query.domain)
        // An A record must look like an IPv4 address.
        val a = r.records["A"]!!.first().value
        assertTrue("A record '$a' is not an IPv4 address", Regex("""^\d+\.\d+\.\d+\.\d+$""").matches(a))
        assertTrue("TTL should be present", r.records["A"]!!.first().ttl != null)
    }

    @Test
    fun `url and www prefixes are stripped before resolving`() = runBlocking {
        val r = OnDeviceIntel.dns("https://www.github.com/some/path")
        assertEquals("github.com", r.query.domain)
        assertTrue(r.records["A"].orEmpty().isNotEmpty())
    }

    @Test
    fun `rdap returns registration detail`() = runBlocking {
        val r = OnDeviceIntel.domain("github.com")
        println("registrar=${r.whois.registrar} created=${r.whois.created} ns=${r.whois.nameservers.take(2)}")
        assertTrue("domain should be found", r.found)
        assertNotNull("registrar should parse out of the vCard array", r.whois.registrar)
        assertNotNull("creation date should parse", r.whois.created)
        assertTrue("expected nameservers", r.whois.nameservers.isNotEmpty())
        assertTrue("expected status codes", r.whois.status.isNotEmpty())
        // GitHub was registered in 2007; a sane parse must reflect that.
        assertTrue("created '${r.whois.created}' should start with a year", r.whois.created!!.startsWith("20"))
    }

    @Test
    fun `unregistered domain reports not found rather than throwing`() = runBlocking {
        val r = OnDeviceIntel.domain("this-domain-almost-certainly-does-not-exist-9x7q2.com")
        assertFalse(r.found)
        assertNotNull(r.error)
    }

    @Test
    fun `ip lookup resolves geolocation and network owner`() = runBlocking {
        val r = OnDeviceIntel.ip("8.8.8.8")
        println("geo=${r.geo.city}, ${r.geo.country}  asn=${r.network.asn} org=${r.network.org}")
        assertTrue("IP should be found", r.found)
        assertEquals("United States", r.geo.country)
        assertNotNull("latitude should parse", r.geo.lat)
        assertEquals("AS15169", r.network.asn)
        assertTrue("org should mention Google", r.network.org.orEmpty().contains("Google", true))
    }

    @Test
    fun `email report combines mx and breach corpus`() = runBlocking {
        val r = OnDeviceIntel.email("test@example.com")
        println("breached=${r.summary.breached} count=${r.summary.breachCount} risk=${r.summary.riskLabel}")
        assertEquals("test@example.com", r.query.email)
        assertTrue("test@example.com is heavily breached", r.summary.breached)
        assertTrue("expected many breaches", r.summary.breachCount > 50)
        assertTrue("expected per-breach detail", r.darkweb.breaches.isNotEmpty())
        assertTrue("expected a timeline", r.darkweb.timeline.isNotEmpty())
        assertTrue("expected exposed-data categories", r.darkweb.exposedData.isNotEmpty())
        // Timeline must be chronological for the chart to make sense.
        val years = r.darkweb.timeline.map { it.year }
        assertEquals(years.sorted(), years)
    }

    @Test
    fun `local email analysis needs no network`() {
        val gmail = OnDeviceIntel.analyseEmail("someone@gmail.com")
        assertEquals("Google Gmail", gmail.provider)
        assertEquals("personal", gmail.providerType)
        assertFalse(gmail.disposable)

        val temp = OnDeviceIntel.analyseEmail("x@mailinator.com")
        assertTrue("mailinator should be flagged disposable", temp.disposable)

        val plus = OnDeviceIntel.analyseEmail("first.last+tag@fastmail.com")
        assertTrue(plus.plusAddressing)
        assertEquals("first.last", plus.format)
        assertEquals("privacy", plus.providerType)

        val corp = OnDeviceIntel.analyseEmail("ceo@some-company.co.uk")
        assertEquals("Custom / corporate domain", corp.provider)
    }
}
