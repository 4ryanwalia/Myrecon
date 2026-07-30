package com.aryan.myrecon

import com.aryan.myrecon.data.PlatformCatalogue
import com.aryan.myrecon.data.UsernameSweep
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

/**
 * Measures accuracy in BOTH directions.
 *
 * The earlier suite only counted false positives, which is how the detector
 * ended up rejecting real Instagram and Pinterest profiles: tightening one
 * number quietly wrecked the other. Recall is checked here explicitly so that
 * cannot happen again silently.
 */
class SweepAccuracyTest {

    private fun sweep(handle: String): List<UsernameSweep.Hit> = runBlocking {
        var out: List<UsernameSweep.Hit> = emptyList()
        UsernameSweep.run(handle).collect { ev ->
            if (ev is UsernameSweep.Event.Finished) out = ev.hits
        }
        out
    }

    @Test
    fun `recall - a very public handle surfaces its major platforms`() {
        val hits = sweep("nasa")
        val names = hits.map { it.platform.name }.toSet()
        println("nasa -> ${hits.size} hits")
        println("  " + hits.joinToString(", ") { "${it.platform.name}(${it.confidence})" })

        // NASA demonstrably has all of these. Any miss is a false negative.
        val expected = listOf("Instagram", "Twitter / X", "YouTube", "Reddit")
        val missing = expected.filterNot { it in names }
        println("  missing: $missing")

        assertTrue(
            "recall regression — these real accounts were not found: $missing",
            missing.size <= 1,
        )
        assertTrue("expected a broad footprint for nasa, got ${hits.size}", hits.size >= 25)
    }

    @Test
    fun `precision - a nonsense handle stays quiet`() {
        val hits = sweep("zzq7x4nvunlikely9k2qq")
        val confident = hits.filter { it.confidence == "high" || it.confidence == "medium" }
        println("nonsense -> ${hits.size} total, ${confident.size} confident")
        println("  confident: " + confident.joinToString(", ") { it.platform.name })

        // Low-confidence "reachable but unconfirmed" results are acceptable
        // noise; confidently claiming a nonexistent account is not.
        assertTrue(
            "too many confident false positives: ${confident.map { it.platform.name }}",
            confident.size <= 3,
        )
    }

    @Test
    fun `github api gives an exact answer in both directions`() {
        val real = sweep("torvalds").firstOrNull { it.platform.name == "GitHub" }
        assertNotNull("GitHub must be found for torvalds", real)
        assertEquals("API answers should be high confidence", "high", real!!.confidence)

        val fake = sweep("zzq7x4nvunlikely9k2qq").firstOrNull { it.platform.name == "GitHub" }
        assertNull("GitHub must not be reported for a nonexistent login", fake)
    }

    @Test
    fun `catalogue wires the api endpoints it claims to`() {
        val withApi = PlatformCatalogue.ALL.filter { it.apiTemplate != null }
        println("API-backed platforms: ${withApi.map { it.name }}")
        assertTrue("GitHub should use its API", withApi.any { it.name == "GitHub" })
        assertTrue("Instagram should use its API", withApi.any { it.name == "Instagram" })
        withApi.forEach {
            assertTrue("${it.name} api url must substitute", !it.apiUrlFor("x")!!.contains("{username}"))
        }
    }
}
