package com.aryan.myrecon

import com.aryan.myrecon.data.LinkSafety
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

/**
 * The verdict here is what a user leans on before deciding to open a link, so
 * the classification and impersonation rules are tested exhaustively offline,
 * and the end-to-end path is checked against real domains.
 */
class LinkSafetyTest {

    // ── Pure logic, no network ───────────────────────────────────

    @Test
    fun `payload kinds are classified correctly`() {
        val k = LinkSafety::classify
        assertEquals(LinkSafety.Kind.Url, k("https://example.com"))
        assertEquals(LinkSafety.Kind.Url, k("http://example.com/path?a=1"))
        assertEquals(LinkSafety.Kind.Url, k("example.com"))
        assertEquals(LinkSafety.Kind.Url, k("sub.example.co.uk/x"))
        assertEquals(LinkSafety.Kind.WifiCredentials, k("WIFI:S:MyNet;T:WPA;P:secret;;"))
        assertEquals(LinkSafety.Kind.ContactCard, k("BEGIN:VCARD\nFN:Ada"))
        assertEquals(LinkSafety.Kind.ContactCard, k("MECARD:N:Ada;;"))
        assertEquals(LinkSafety.Kind.PhoneOrSms, k("tel:+15550100"))
        assertEquals(LinkSafety.Kind.PhoneOrSms, k("SMSTO:+15550100:hi"))
        assertEquals(LinkSafety.Kind.Crypto, k("bitcoin:1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"))
        assertEquals(LinkSafety.Kind.PlainText, k("just some words"))
    }

    @Test
    fun `base domain handles multi part suffixes`() {
        val b = LinkSafety::baseDomain
        assertEquals("example.com", b("example.com"))
        assertEquals("example.com", b("www.example.com"))
        assertEquals("example.com", b("a.b.c.example.com"))
        assertEquals("example.co.uk", b("shop.example.co.uk"))
        assertEquals("example.com.au", b("www.example.com.au"))
        assertNull(b("localhost"))
        assertNull(b(null))
    }

    @Test
    fun `impersonation fires on decoration but not on the real brand`() {
        val i = LinkSafety::impersonationOf
        // The genuine article must never be flagged.
        assertNull(i("paypal.com"))
        assertNull(i("www.paypal.com"))
        assertNull(i("google.com"))
        // Brand as a prefix, suffix or subdomain of somebody else's domain.
        assertEquals("paypal", i("paypal-secure.top"))
        assertEquals("paypal", i("secure-paypal-verify.xyz"))
        assertEquals("paypal", i("paypal.evil-host.com"))
        assertEquals("netflix", i("netflix-billing.click"))
        // Unrelated domains stay clean.
        assertNull(i("myrecon.xyz"))
        assertNull(i("github.com"))
    }

    @Test
    fun `host extraction is robust`() {
        val h = LinkSafety::hostOf
        assertEquals("example.com", h("https://example.com/a/b?c=d"))
        assertEquals("example.com", h("https://WWW.Example.COM"))
        assertEquals("example.com", h("example.com"))
        assertNull(h("not a url at all"))
        assertNull(h(null))
    }

    @Test
    fun `wifi and crypto payloads warn without touching the network`() = runBlocking {
        val wifi = LinkSafety.analyse("WIFI:S:FreeAirportWiFi;T:nopass;;")
        assertEquals(LinkSafety.Kind.WifiCredentials, wifi.kind)
        assertTrue("wifi should warn", wifi.signals.isNotEmpty())

        val btc = LinkSafety.analyse("bitcoin:1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa?amount=0.5")
        assertEquals(LinkSafety.Kind.Crypto, btc.kind)
        assertEquals(LinkSafety.Verdict.Caution, btc.verdict)
        assertTrue(btc.signals.any { it.detail.contains("cannot be reversed") })
    }

    // ── End to end, against live domains ─────────────────────────

    @Test
    fun `an established domain reads as safe`() = runBlocking {
        val r = LinkSafety.analyse("https://github.com")
        println("github.com -> ${r.verdict} score=${r.riskScore} age=${r.ageDays}d registrar=${r.registrar}")
        r.signals.forEach { println("   ${it.weight.toString().padStart(4)}  ${it.label}") }

        assertEquals("github.com", r.host)
        assertNotNull("registration date should resolve", r.registered)
        assertTrue("github is old", (r.ageDays ?: 0) > 5000)
        assertEquals(LinkSafety.Verdict.Safe, r.verdict)
        assertTrue("age should lower the score", r.signals.any { it.weight < 0 })
    }

    @Test
    fun `a lookalike host on a cheap tld reads as dangerous`() = runBlocking {
        // Not registered — the point is that shape alone is damning enough.
        val r = LinkSafety.analyse("https://secure-paypal-verify.top/login")
        println("lookalike -> ${r.verdict} score=${r.riskScore}")
        r.signals.forEach { println("   ${it.weight.toString().padStart(4)}  ${it.label}") }

        assertEquals(LinkSafety.Verdict.Dangerous, r.verdict)
        assertTrue("impersonation must be caught", r.signals.any { it.label.contains("paypal") })
        assertTrue("cheap TLD must be caught", r.signals.any { it.label.contains(".top") })
    }

    @Test
    fun `a raw ip destination is called out`() = runBlocking {
        val r = LinkSafety.analyse("http://203.0.113.10/verify")
        println("raw ip -> ${r.verdict} score=${r.riskScore}")
        assertTrue("bare IP must be flagged", r.signals.any { it.label.contains("IP address") })
        assertTrue("plain http must be flagged", r.signals.any { it.label.contains("Not encrypted") })
        assertNotEquals(LinkSafety.Verdict.Safe, r.verdict)
    }

    @Test
    fun `every signal explains itself`() = runBlocking {
        val r = LinkSafety.analyse("https://secure-paypal-verify.top")
        r.signals.forEach {
            assertTrue("signal '${it.label}' has no explanation", it.detail.length > 20)
            assertTrue("signal '${it.label}' has no label", it.label.isNotBlank())
        }
        // Highest-weight signal must lead, since it drives the verdict.
        val weights = r.signals.map { it.weight }
        assertEquals(weights.sortedDescending(), weights)
    }
}
