package com.aryan.myrecon

import com.aryan.myrecon.data.LinkSafety
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

/**
 * The QR scanner's reading of what a code actually is.
 *
 * The offline half pins classification, which is where the real bug was: a
 * `upi://pay` code — the most-scanned kind of QR in India, and the one that
 * literally moves money — was falling through to "plain text" and getting no
 * analysis at all.
 */
class QrSafetyTest {

    // ── Classification ───────────────────────────────────────────

    @Test
    fun `payment codes are recognised rather than treated as text`() {
        listOf(
            "upi://pay?pa=merchant@okhdfcbank&pn=Chai%20Stall&am=40&cu=INR",
            "UPI://PAY?pa=someone@ybl",
            "phonepe://pay?pa=x@ybl",
            "paytmmp://cash_wallet?pa=y@paytm",
        ).forEach {
            assertEquals("should be Payment: $it", LinkSafety.Kind.Payment, LinkSafety.classify(it))
        }
    }

    @Test
    fun `the other kinds still classify as they did`() {
        assertEquals(LinkSafety.Kind.Url, LinkSafety.classify("https://example.com/x"))
        assertEquals(LinkSafety.Kind.Url, LinkSafety.classify("example.com/x"))
        assertEquals(LinkSafety.Kind.WifiCredentials, LinkSafety.classify("WIFI:S:Cafe;T:WPA;P:pw;;"))
        assertEquals(LinkSafety.Kind.ContactCard, LinkSafety.classify("BEGIN:VCARD\nFN:A\nEND:VCARD"))
        assertEquals(LinkSafety.Kind.PhoneOrSms, LinkSafety.classify("tel:+911234567890"))
        assertEquals(LinkSafety.Kind.Crypto, LinkSafety.classify("bitcoin:1A1zP1eP5Q"))
        assertEquals(LinkSafety.Kind.PlainText, LinkSafety.classify("table 14"))
    }

    // ── Payee parsing ────────────────────────────────────────────

    @Test
    fun `a upi request yields who is paid and how much`() {
        val p = LinkSafety.parsePayee(
            "upi://pay?pa=merchant@okhdfcbank&pn=Chai%20Stall&am=40&cu=INR&tn=Two%20teas"
        )
        assertNotNull(p)
        assertEquals("merchant@okhdfcbank", p!!.address)
        assertEquals("Chai Stall", p.name)
        assertEquals("40", p.amount)
        assertEquals("INR", p.currency)
        assertEquals("Two teas", p.note)
    }

    @Test
    fun `an open-ended request parses with no amount`() {
        val p = LinkSafety.parsePayee("upi://pay?pa=shop@ybl&pn=Shop")
        assertNotNull(p)
        assertNull("amount must stay null, not empty string", p!!.amount)
    }

    @Test
    fun `a malformed payment code does not crash the parser`() {
        assertNull(LinkSafety.parsePayee("upi://pay"))
        assertNull(LinkSafety.parsePayee("upi://pay?am=40"))   // no payee at all
    }

    @Test
    fun `a payment report warns that scanning cannot receive money`() = runBlocking {
        val r = LinkSafety.analyse("upi://pay?pa=scam@ybl&pn=Refund%20Dept&am=4999&cu=INR")

        assertEquals(LinkSafety.Kind.Payment, r.kind)
        assertNotNull("the payee must reach the report", r.payee)
        assertEquals("scam@ybl", r.payee!!.address)

        // Never green. Nothing that moves money should carry a safe verdict.
        assertNotEquals(LinkSafety.Verdict.Safe, r.verdict)

        // The line that actually prevents the most common UPI fraud.
        assertTrue(
            "must state that a scan cannot receive money",
            r.signals.any { it.label.contains("never receives money", ignoreCase = true) },
        )
    }

    // ── Destination naming ───────────────────────────────────────

    @Test
    fun `a youtube link is described as a video, not just a url`() = runBlocking {
        val r = LinkSafety.analyse("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        println("destination: ${r.destination?.what} — ${r.destination?.title}")
        assertEquals(LinkSafety.Kind.Url, r.kind)
        assertNotNull("a known host must be named", r.destination)
        assertTrue(
            "expected a YouTube description, got ${r.destination?.what}",
            r.destination!!.what.contains("YouTube"),
        )
    }

    @Test
    fun `an ordinary well-known site is not flagged as dangerous`() = runBlocking {
        // The false-positive guard. A decade-old domain over https with no
        // redirect games must never come back as anything but benign.
        val r = LinkSafety.analyse("https://en.wikipedia.org/wiki/QR_code")
        println("wikipedia verdict=${r.verdict} score=${r.riskScore} signals=${r.signals.map { it.label }}")
        assertNotEquals(LinkSafety.Verdict.Dangerous, r.verdict)
        assertTrue("score should be low for a benign site, was ${r.riskScore}", r.riskScore < 25)
    }
}
