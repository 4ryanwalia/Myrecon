package com.aryan.myrecon

import com.aryan.myrecon.data.ReportText
import com.aryan.myrecon.data.SavedProfile
import org.junit.Assert.*
import org.junit.Test

/**
 * The text that leaves the phone.
 *
 * A shared report is the only part of this app that other people read, often
 * without ever seeing the app itself — a parent, a landlord, a police station.
 * So it has to stand on its own: say what was checked, when, what was found,
 * and how sure the answer is. These pin the parts that would be quietly wrong
 * rather than visibly broken.
 */
class ReportTextTest {

    private fun profile(platform: String, confidence: String) = SavedProfile(
        platform = platform,
        category = "Social",
        url = "https://$platform.example/user",
        confidence = confidence,
    )

    @Test
    fun `a sweep report names what was searched and when`() {
        val text = ReportText.forSweep(
            "aryan",
            listOf(profile("github", "high"), profile("reddit", "low")),
        )
        assertTrue("must name the handle", text.contains("@aryan"))
        assertTrue("must be dated", text.contains("Checked on"))
        assertTrue("must say where it came from", text.contains("public sources"))
    }

    @Test
    fun `confidence is grouped, not flattened into one list`() {
        // The failure this prevents is a reader treating a maybe as a
        // certainty, which is the whole risk of forwarding one of these.
        val text = ReportText.forSweep(
            "aryan",
            listOf(
                profile("reddit", "low"),
                profile("github", "high"),
                profile("gitlab", "medium"),
            ),
        )
        val certain = text.indexOf("Almost certainly")
        val likely = text.indexOf("Likely")
        val possible = text.indexOf("Possible, unconfirmed")

        assertTrue("all three bands must appear", certain >= 0 && likely >= 0 && possible >= 0)
        assertTrue("strongest evidence must come first", certain < likely && likely < possible)
        assertTrue("github belongs above reddit", text.indexOf("github") < text.indexOf("reddit"))
    }

    @Test
    fun `an empty sweep says so rather than looking truncated`() {
        val text = ReportText.forSweep("nobodyatall", emptyList())
        assertTrue(text.contains("No accounts were found"))
        // The caveat has to survive even when there is nothing to caveat.
        assertTrue(text.contains("evidence, not proof"))
    }

    @Test
    fun `every report carries the caveat that results are not proof`() {
        val text = ReportText.forLines(
            "Domain check",
            "example.com",
            listOf("Registered" to listOf("2001-01-01")),
        )
        assertTrue(text.contains("evidence, not proof"))
        assertTrue(text.contains("myrecon.xyz"))
    }

    @Test
    fun `empty sections are dropped instead of leaving bare headings`() {
        val text = ReportText.forLines(
            "Domain check",
            "example.com",
            listOf(
                "Registered" to listOf("2001-01-01"),
                "Mail servers" to emptyList(),
            ),
        )
        assertTrue(text.contains("Registered"))
        assertFalse("an empty section must not print its heading", text.contains("Mail servers"))
    }
}
