package com.aryan.myrecon

import com.aryan.myrecon.data.PlatformCatalogue
import com.aryan.myrecon.data.UsernameSweep
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Which platforms answer for a handle that cannot exist.
 *
 * A platform that reports a hit for three unrelated nonsense strings is not
 * finding anything — it serves a page for any input, and every result it has
 * ever produced was noise. That is measurable rather than arguable, and it is
 * the only honest way to decide which entries in the catalogue can be trusted.
 *
 * Three handles rather than one, because a single string can collide: short or
 * word-like handles get registered by real people, and one lucky match would
 * condemn a platform that works perfectly.
 */
class SweepNoiseTest {

    /**
     * Unregistered, but shaped like handles people actually have.
     *
     * The first version of this used twenty-one character strings, which
     * several platforms reject as *invalid* rather than *not found* — a
     * different code path that made them look stricter than they are. Twelve
     * lowercase letters is an ordinary handle, so what comes back is the real
     * not-found behaviour.
     */
    private val nonsense = listOf(
        "mravnkithlow",
        "zelbufcrandy",
        "qhinrelvasto",
    )

    private fun sweep(handle: String): List<UsernameSweep.Hit> = runBlocking {
        var out: List<UsernameSweep.Hit> = emptyList()
        UsernameSweep.run(handle).collect { ev ->
            if (ev is UsernameSweep.Event.Finished) out = ev.hits
        }
        out
    }

    @Test
    fun `report which platforms answer for handles that cannot exist`() {
        val perHandle = nonsense.associateWith { sweep(it) }

        perHandle.forEach { (handle, hits) ->
            println("$handle -> ${hits.size} hits")
        }

        // Present for every one of the three: cannot tell a real account from
        // an imaginary one, whatever confidence it claims.
        val always = perHandle.values
            .map { hits -> hits.map { it.platform.name }.toSet() }
            .reduce { a, b -> a intersect b }
            .sorted()

        val echoing = PlatformCatalogue.ECHOES_HANDLE
        println()
        println("ANSWERS FOR ALL THREE NONSENSE HANDLES (${always.size}):")
        always.forEach { name ->
            val bands = perHandle.values.mapNotNull { hits ->
                hits.firstOrNull { it.platform.name == name }?.confidence
            }
            val marked = if (name in echoing) "  [already marked]" else ""
            println("  $name  ${bands.joinToString("/")}$marked")
        }

        val unmarked = always.filterNot { it in echoing }
        println()
        println("NOT YET MARKED (${unmarked.size}): ${unmarked.joinToString(", ")}")

        // What is enforced is the part that harms someone: no platform may
        // claim confidence about a handle that cannot exist. Which platforms
        // merely answer is reported rather than asserted, because that number
        // moves with what the platforms themselves do and a build breaking
        // because Tumblr changed its 404 page teaches nobody anything.
        val confidentlyWrong = always.filter { name ->
            perHandle.values.all { hits ->
                hits.firstOrNull { it.platform.name == name }
                    ?.confidence in setOf("high", "medium")
            }
        }
        assertTrue(
            "these claim a real account for a handle nobody owns: $confidentlyWrong",
            confidentlyWrong.isEmpty(),
        )
        assertTrue(perHandle.values.all { it.size < PlatformCatalogue.size })
    }
}
