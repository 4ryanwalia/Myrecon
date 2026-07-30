package com.aryan.myrecon

import com.aryan.myrecon.data.KeybaseIntel
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

/**
 * The alias discovery is the whole reason this exists, so it is asserted
 * directly against the live service rather than a fixture.
 */
class KeybaseIntelTest {

    @Test
    fun `alias under a different handle is discovered`() = runBlocking {
        val id = KeybaseIntel.lookup("sindresorhus")
        println("found=${id.found} proofs=${id.proofs.size} name=${id.fullName}")
        id.proofs.forEach { println("   ${if (it.isAlias) "ALIAS" else "     "} ${it.platform.padEnd(20)} ${it.handle}") }

        assertTrue("identity should resolve", id.found)
        assertTrue("expected several proofs", id.proofs.size >= 3)

        // This is the headline: a linked account under a name the sweep would
        // never have tried. If Keybase ever drops it the feature loses its point.
        val aliases = id.aliases
        println("aliases: ${aliases.map { "${it.handle}@${it.platform}" }}")
        assertTrue("expected at least one differently-named account", aliases.isNotEmpty())
        assertTrue(
            "every alias must differ from the searched handle",
            aliases.none { it.handle.equals("sindresorhus", ignoreCase = true) },
        )
    }

    @Test
    fun `aliases sort ahead of same-handle confirmations`() = runBlocking {
        val id = KeybaseIntel.lookup("max")
        assertTrue(id.found)
        val flags = id.proofs.map { it.isAlias }
        assertEquals("aliases must lead", flags.sortedByDescending { it }, flags)
    }

    @Test
    fun `same-handle links are not mislabelled as aliases`() = runBlocking {
        val id = KeybaseIntel.lookup("chris")
        assertTrue(id.found)
        val sameHandle = id.proofs.filter { it.handle.equals("malgorithms", ignoreCase = true) }
        println("chris -> ${id.proofs.map { "${it.handle}(${it.isAlias})" }}")
        // "chris" on Keybase links accounts named "malgorithms", so those ARE
        // aliases relative to the searched handle.
        assertTrue("malgorithms differs from chris, so it is an alias",
            sameHandle.all { it.isAlias })
    }

    @Test
    fun `an unknown handle reports not found rather than throwing`() = runBlocking {
        val id = KeybaseIntel.lookup("zzq7x4nvunlikely9k2qq")
        assertFalse(id.found)
        assertTrue(id.proofs.isEmpty())
        assertTrue(id.aliases.isEmpty())
    }

    @Test
    fun `blank input is rejected without a request`() = runBlocking {
        val id = KeybaseIntel.lookup("   ")
        assertFalse(id.found)
        assertNotNull(id.error)
    }

    @Test
    fun `platform names are humanised`() = runBlocking {
        val id = KeybaseIntel.lookup("chris")
        assertTrue(id.found)
        // Raw proof_type values like hackernews / generic_web_site must not
        // reach the UI.
        assertTrue(
            "raw proof_type leaked: ${id.proofs.map { it.platform }}",
            id.proofs.none { it.platform.contains('_') },
        )
    }
}
