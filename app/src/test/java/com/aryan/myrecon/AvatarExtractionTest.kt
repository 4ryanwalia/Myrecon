package com.aryan.myrecon

import com.aryan.myrecon.data.UsernameSweep
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

/**
 * Verifies profile pictures are actually recovered, and that placeholders and
 * broken URLs are rejected rather than shown as if they were real.
 */
class AvatarExtractionTest {

    private fun sweep(handle: String): List<UsernameSweep.Hit> = runBlocking {
        var out: List<UsernameSweep.Hit> = emptyList()
        UsernameSweep.run(handle).collect { ev ->
            if (ev is UsernameSweep.Event.Finished) out = ev.hits
        }
        out
    }

    @Test
    fun `a broad sweep recovers real avatar urls`() {
        val hits = sweep("nasa")
        val withAvatar = hits.filter { !it.avatar.isNullOrBlank() }

        println("avatars: ${withAvatar.size} of ${hits.size} hits")
        withAvatar.take(12).forEach {
            println("  ${it.platform.name.padEnd(16)} ${it.avatar}")
        }

        assertTrue(
            "expected avatars from at least a few platforms, got ${withAvatar.size}",
            withAvatar.size >= 5,
        )
        // Every URL handed to the image loader must be absolute and loadable.
        withAvatar.forEach {
            val a = it.avatar!!
            assertTrue("${it.platform.name} avatar is not http(s): $a", a.startsWith("http"))
            assertFalse("${it.platform.name} avatar has an unescaped entity", a.contains("&amp;"))
            assertFalse("${it.platform.name} avatar has a doubled query string",
                a.substringAfter('?', "").contains('?'))
            // A leftover \\uXXXX escape means the CDN will reject the query.
            assertFalse("${it.platform.name} avatar has a raw unicode escape: $a", a.contains("\\u"))
            // Site logos must have been filtered out, not passed through.
            listOf("ogimage", "opengraph", "og.png").forEach { junk ->
                assertFalse(
                    "${it.platform.name} returned site artwork, not an avatar: $a",
                    junk in a.lowercase(),
                )
            }
        }
    }

    @Test
    fun `github api yields an avatar and a display name`() {
        val gh = sweep("torvalds").firstOrNull { it.platform.name == "GitHub" }
        assertNotNull("GitHub should be found", gh)
        println("github avatar = ${gh!!.avatar}")
        println("github name   = ${gh.displayName}")
        assertNotNull("GitHub's API exposes avatar_url", gh.avatar)
        assertTrue(
            "expected a githubusercontent avatar, got ${gh.avatar}",
            gh.avatar!!.contains("githubusercontent", ignoreCase = true),
        )
    }

    @Test
    fun `placeholder avatars are discarded`() {
        // DeviantArt serves default_group.gif for accounts with no picture; a
        // stock image must not be presented as the person's own.
        val hits = sweep("nasa")
        hits.forEach { h ->
            val a = h.avatar?.lowercase() ?: return@forEach
            listOf("default", "placeholder", "anonymous", "noavatar").forEach { marker ->
                assertFalse(
                    "${h.platform.name} kept a placeholder avatar: ${h.avatar}",
                    marker in a,
                )
            }
        }
    }
}
