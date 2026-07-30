package com.aryan.myrecon

import com.aryan.myrecon.data.PlatformCatalogue
import com.aryan.myrecon.data.UsernameSweep
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import kotlin.system.measureTimeMillis

/**
 * Proves the sweep can run client-side at all, and measures what it costs.
 *
 * Runs against the live platforms on purpose: the entire question is whether
 * 118 real hosts can be probed from a client in acceptable time with an
 * acceptable false-positive rate, and no fixture can answer that.
 */
class UsernameSweepTest {

    @Test
    fun `catalogue is well formed`() {
        val all = PlatformCatalogue.ALL
        println("catalogue: ${all.size} platforms across ${all.map { it.category }.distinct().size} categories")
        assertTrue("expected 100+ platforms", all.size >= 100)
        assertEquals("names must be unique", all.size, all.map { it.name }.distinct().size)
        all.forEach { p ->
            assertTrue("${p.name} template must contain {username}", p.template.contains("{username}"))
            assertTrue("${p.name} must be https", p.template.startsWith("https://"))
            assertFalse("${p.name} url must substitute", p.urlFor("abc").contains("{username}"))
        }
    }

    @Test
    fun `sweep finds a well known handle and reports progress throughout`() = runBlocking {
        var progressEvents = 0
        var finished: UsernameSweep.Event.Finished? = null
        var lastChecked = 0

        val elapsed = measureTimeMillis {
            UsernameSweep.run("torvalds").collect { ev ->
                when (ev) {
                    is UsernameSweep.Event.Progress -> {
                        progressEvents++
                        assertTrue("checked must not go backwards", ev.checked >= lastChecked - 16)
                        lastChecked = maxOf(lastChecked, ev.checked)
                        assertEquals(PlatformCatalogue.size, ev.total)
                    }
                    is UsernameSweep.Event.Finished -> finished = ev
                }
            }
        }

        val hits = finished?.hits.orEmpty()
        println("sweep took ${elapsed}ms, ${progressEvents} progress events, ${hits.size} hits")
        println("found: " + hits.take(15).joinToString(", ") { "${it.platform.name}(${it.confidence})" })

        assertNotNull("a Finished event must always arrive", finished)
        assertEquals("every platform must report", PlatformCatalogue.size, progressEvents)
        assertTrue("torvalds should exist somewhere", hits.isNotEmpty())
        assertTrue(
            "GitHub is the one certainty for this handle",
            hits.any { it.platform.name == "GitHub" },
        )
        // Under two minutes is the bar for something a person waits on.
        assertTrue("sweep took too long: ${elapsed}ms", elapsed < 120_000)
        // High-confidence hits must sort first.
        val bands = hits.map { it.confidence }
        assertEquals(bands.sortedByDescending { it == "high" }, bands)
    }

    @Test
    fun `a handle nobody owns yields few or no hits`() = runBlocking {
        var finished: UsernameSweep.Event.Finished? = null
        UsernameSweep.run("zzq7x4nvunlikely9k2qq").collect { ev ->
            if (ev is UsernameSweep.Event.Finished) finished = ev
        }
        val hits = finished?.hits.orEmpty()
        val confident = hits.filter { it.confidence == "high" || it.confidence == "medium" }
        println("nonsense handle: ${hits.size} total, ${confident.size} confident -> ${confident.map { it.platform.name }}")
        assertNotNull(finished)

        // Counts CONFIDENT hits, not the raw total.
        //
        // The sweep now reports platforms that were reachable and showed no
        // error as low confidence rather than discarding them. That is
        // deliberate: rejecting everything unconfirmed is what previously hid
        // real Instagram and Pinterest profiles, because those render
        // client-side and their HTML never names the account holder. A
        // low-confidence row the user can dismiss is a better failure than a
        // real account silently missing.
        assertTrue(
            "too many confident false positives: ${confident.map { it.platform.name }}",
            confident.size <= 3,
        )
    }

    @Test
    fun `empty handle is rejected`() {
        try {
            runBlocking { UsernameSweep.run("   ").collect { } }
            fail("expected an exception for an empty handle")
        } catch (e: IllegalArgumentException) {
            assertTrue(e.message!!.contains("empty", ignoreCase = true))
        }
    }
}
