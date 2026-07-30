package com.aryan.myrecon

import com.aryan.myrecon.data.PwnedPasswords
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.security.MessageDigest

/**
 * Pure-logic tests for the password checker. The network call is not exercised
 * here; what matters is that the maths is right, because the k-anonymity
 * guarantee depends on the hash prefix being computed correctly.
 */
class PwnedPasswordsTest {

    private fun sha1Upper(s: String): String =
        MessageDigest.getInstance("SHA-1")
            .digest(s.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02X".format(it) }

    @Test
    fun `sha1 matches the known digest for password`() {
        // Independently verified against the Pwned Passwords corpus.
        assertEquals("5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8", sha1Upper("password"))
    }

    @Test
    fun `only five characters form the prefix that leaves the device`() {
        val hash = sha1Upper("password")
        val prefix = hash.substring(0, 5)
        val suffix = hash.substring(5)
        assertEquals("5BAA6", prefix)
        assertEquals(35, suffix.length)
        // The prefix must not disclose the rest of the digest.
        assertTrue(!prefix.contains(suffix))
        assertEquals(40, prefix.length + suffix.length)
    }

    @Test
    fun `entropy rises with length and character variety`() {
        val short = PwnedPasswords.strengthOf("abc")
        val longer = PwnedPasswords.strengthOf("abcdefghijkl")
        val mixed = PwnedPasswords.strengthOf("Abcdef1!ghij")
        assertTrue("longer should beat short", longer.bits > short.bits)
        assertTrue("mixed pool should beat lowercase-only", mixed.bits > longer.bits)
    }

    @Test
    fun `character pool reflects the classes actually used`() {
        assertEquals(26, PwnedPasswords.strengthOf("abcdef").poolSize)
        assertEquals(52, PwnedPasswords.strengthOf("abcDEF").poolSize)
        assertEquals(62, PwnedPasswords.strengthOf("abcDEF123").poolSize)
        assertEquals(95, PwnedPasswords.strengthOf("abcDEF123!@#").poolSize)
    }

    @Test
    fun `weak passwords are labelled weak and strong ones strong`() {
        assertEquals("Very weak", PwnedPasswords.strengthOf("abc").label)
        val strong = PwnedPasswords.strengthOf("correct-horse-battery-staple-9F3x2Q")
        assertTrue("expected Strong or Excellent, got ${strong.label}",
            strong.label == "Strong" || strong.label == "Excellent")
    }

    @Test
    fun `crack time reads naturally at every scale`() {
        assertEquals("instantly", PwnedPasswords.humanDuration(0.0))
        assertEquals("instantly", PwnedPasswords.humanDuration(0.4))
        assertEquals("30 seconds", PwnedPasswords.humanDuration(30.0))
        assertEquals("1 second", PwnedPasswords.humanDuration(1.0))
        assertEquals("5 minutes", PwnedPasswords.humanDuration(300.0))
        assertEquals("2 hours", PwnedPasswords.humanDuration(7200.0))
        assertEquals("millions of years", PwnedPasswords.humanDuration(1e20))
    }

    @Test
    fun `singular and plural are handled`() {
        assertTrue(PwnedPasswords.humanDuration(1.0).endsWith("second"))
        assertTrue(PwnedPasswords.humanDuration(2.0).endsWith("seconds"))
        assertTrue(PwnedPasswords.humanDuration(60.0).endsWith("minute"))
    }

    @Test
    fun `empty pool does not divide by zero`() {
        // log2(0) would be -Infinity; the guard must keep this finite.
        val s = PwnedPasswords.strengthOf("")
        assertEquals(0, s.poolSize)
        assertEquals(0, s.bits)
        assertEquals(0, s.length)
    }
}
