package com.aryan.myrecon

import com.aryan.myrecon.data.AccountRemoval
import com.aryan.myrecon.data.PlatformCatalogue
import org.junit.Assert.*
import org.junit.Test

/**
 * The removal links and the erasure letter.
 *
 * Offline checks only — whether each URL still resolves is a fact about the
 * internet today, not about this code, and a test that fails because Tumblr is
 * having an afternoon teaches nobody anything. What is pinned here is the
 * shape: names that match the catalogue, links that go somewhere plausible,
 * and a letter that contains everything a support desk needs to act on it.
 */
class AccountRemovalTest {

    @Test
    fun `every route names a platform the sweep can actually find`() {
        // A route keyed "Twitter" when the catalogue says "Twitter / X" is a
        // link that silently never appears. This is the mistake that would
        // never show up by looking at the file.
        val known = PlatformCatalogue.ALL.map { it.name }.toSet()
        val orphans = PlatformCatalogue.ALL
            .map { it.name }
            .let { _ ->
                listOf(
                    "Instagram", "Facebook", "Twitter / X", "Reddit", "LinkedIn",
                    "GitHub", "Telegram", "YouTube", "Pinterest", "Tumblr",
                ).filterNot { it in known }
            }
        assertTrue("catalogue names drifted: $orphans", orphans.isEmpty())

        // And the routes themselves must resolve against real catalogue names.
        listOf("Instagram", "Reddit", "GitHub", "Twitter / X").forEach {
            assertNotNull("$it should have a removal route", AccountRemoval.routeFor(it))
        }
    }

    @Test
    fun `an unknown platform has no route rather than a guessed one`() {
        assertNull(AccountRemoval.routeFor("Some Forum Nobody Uses"))
        assertFalse(AccountRemoval.hasRoute("Some Forum Nobody Uses"))
    }

    @Test
    fun `every link is https and points at a real path`() {
        listOf(
            "Instagram", "Facebook", "Reddit", "GitHub", "Telegram", "YouTube",
            "Strava", "Bandcamp", "Behance",
        ).forEach { name ->
            val route = AccountRemoval.routeFor(name) ?: error("$name lost its route")
            assertTrue("$name must be https", route.url.startsWith("https://"))
            assertTrue(
                "$name must point at a path, not a bare domain",
                route.url.removePrefix("https://").contains('/'),
            )
        }
    }

    @Test
    fun `the letter carries what a support desk needs to act`() {
        val letter = AccountRemoval.deletionRequest(
            platform = "Reddit",
            accountUrl = "https://reddit.com/user/aryan",
            handle = "aryan",
            email = "me@example.com",
        )
        assertTrue("must name the platform", letter.contains("Reddit"))
        assertTrue("must give the username", letter.contains("aryan"))
        assertTrue("must give the profile", letter.contains("https://reddit.com/user/aryan"))
        assertTrue("must give the email", letter.contains("me@example.com"))
        assertTrue("must have a subject line", letter.contains("Subject:"))
    }

    @Test
    fun `the letter cites both laws, because the sender cannot know which applies`() {
        val letter = AccountRemoval.deletionRequest("Reddit", null, "aryan")
        assertTrue("India's law", letter.contains("Digital Personal Data Protection Act"))
        assertTrue("the European one", letter.contains("GDPR"))
        assertTrue("asks for written confirmation", letter.contains("confirm in writing"))
    }

    @Test
    fun `missing details are omitted rather than printed as blanks`() {
        // An erasure request with "Registered email: null" in it reads as
        // machine output and gets treated as spam.
        val letter = AccountRemoval.deletionRequest("Reddit", null, null, null)
        assertFalse(letter.contains("null"))
        assertFalse(letter.contains("Profile:"))
        assertFalse(letter.contains("Registered email:"))
        assertTrue("still a usable request", letter.contains("delete my Reddit account"))
    }

    @Test
    fun `the suggested contact is derived from the real host only`() {
        assertEquals("privacy@reddit.com", AccountRemoval.suggestedContact("www.reddit.com"))
        assertEquals("privacy@dev.to", AccountRemoval.suggestedContact("dev.to"))
        // Nothing that is not a hostname should produce an address to send a
        // real name and email to.
        assertNull(AccountRemoval.suggestedContact(null))
        assertNull(AccountRemoval.suggestedContact("localhost"))
        assertNull(AccountRemoval.suggestedContact(""))
    }
}
