package com.aryan.myrecon

import com.aryan.myrecon.data.DeepSearch
import com.aryan.myrecon.data.DorkPlan
import com.aryan.myrecon.data.PersonIntel
import com.aryan.myrecon.data.WebSearch
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

/**
 * Deep Search.
 *
 * The offline half pins the property the whole feature rests on: a hit is only
 * shown if it satisfies the query that claims to have found it. Bing's keyless
 * endpoint answers a query it dislikes with ten results for something else
 * entirely — measured, not hypothetical — so without that check the Instagram
 * section would happily fill up with React tutorials.
 *
 * The live half follows the convention the sweep test set: the question is
 * whether these sources answer an unauthenticated phone at all, and no fixture
 * can answer that.
 */
class DeepSearchTest {

    // ── Mode ─────────────────────────────────────────────────────

    @Test
    fun `mode follows whitespace, and an at-sign forces a handle`() {
        assertEquals(DeepSearch.Mode.Name, DeepSearch.detectMode("Satya Nadella"))
        assertEquals(DeepSearch.Mode.Name, DeepSearch.detectMode("  linus torvalds  "))
        assertEquals(DeepSearch.Mode.Handle, DeepSearch.detectMode("torvalds"))
        assertEquals(DeepSearch.Mode.Handle, DeepSearch.detectMode("john.smith"))
        assertEquals(DeepSearch.Mode.Handle, DeepSearch.detectMode("@torvalds"))
    }

    // ── Query constraints ────────────────────────────────────────

    @Test
    fun `constraints are read off the query text`() {
        val c = WebSearch.constraintsOf("site:linkedin.com/in \"Satya Nadella\"")
        assertEquals("linkedin.com", c.site)
        assertEquals("/in", c.sitePath)
        assertEquals(listOf("Satya Nadella"), c.phrases)
        assertNull(c.filetype)

        val f = WebSearch.constraintsOf("\"torvalds\" filetype:pdf")
        assertEquals("pdf", f.filetype)
        assertNull(f.site)
    }

    @Test
    fun `a hit from the wrong host is rejected`() {
        val c = WebSearch.constraintsOf("site:instagram.com \"cristiano\"")
        // The actual shape of Bing's off-topic answer, verified while building.
        assertFalse(c.accepts("https://react.dev/", "React", "The library for web UIs"))
        assertFalse(
            c.accepts(
                "https://www.tiktok.com/@cristiano",
                "cristiano on TikTok", "cristiano posts",
            )
        )
        assertTrue(
            c.accepts(
                "https://www.instagram.com/cristiano/",
                "Cristiano Ronaldo (@cristiano)", "Instagram profile",
            )
        )
    }

    @Test
    fun `a path-scoped query rejects a hit outside that path`() {
        val c = WebSearch.constraintsOf("site:reddit.com/user/spez")
        assertFalse(c.accepts("https://www.reddit.com/r/announcements/comments/x", "t", "s"))
        assertTrue(c.accepts("https://www.reddit.com/user/spez/", "spez", "overview"))
    }

    @Test
    fun `a required phrase must actually appear somewhere`() {
        val c = WebSearch.constraintsOf("site:reddit.com \"u/spez\"")
        assertFalse(c.accepts("https://www.reddit.com/r/pics/comments/abc", "Pics", "cat photo"))
        // Punctuation around the phrase must not defeat the match.
        assertTrue(
            c.accepts(
                "https://www.reddit.com/r/pics/comments/abc",
                "Pics", "as u/spez: said in the thread",
            )
        )
    }

    @Test
    fun `the url counts as evidence when the snippet is boilerplate`() {
        // Profile pages routinely carry the term in the path and nowhere in the
        // text the engine returns, so the URL has to be part of the haystack.
        val c = WebSearch.constraintsOf("\"torvalds\"")
        assertTrue(c.accepts("https://github.com/torvalds", "GitHub", "Follow their code"))
        assertFalse(c.accepts("https://github.com/octocat", "GitHub", "Follow their code"))
    }

    @Test
    fun `search engine result pages are never findings`() {
        val c = WebSearch.constraintsOf("\"torvalds\"")
        assertFalse(c.accepts("https://www.bing.com/search?q=torvalds", "torvalds - Bing", ""))
        assertFalse(c.accepts("https://duckduckgo.com/?q=torvalds", "torvalds at DuckDuckGo", ""))
    }

    // ── Plans ────────────────────────────────────────────────────

    @Test
    fun `every executed query can be verified against its own results`() {
        listOf(DorkPlan.forName("Satya Nadella"), DorkPlan.forHandle("torvalds")).forEach { plan ->
            plan.filter { it.executed }.forEach { q ->
                val c = WebSearch.constraintsOf(q.text)
                assertTrue(
                    "unverifiable query would be executed: ${q.text}",
                    c.site != null || c.phrases.isNotEmpty() || c.filetype != null,
                )
            }
        }
    }

    @Test
    fun `budgets are respected and spread across sections`() {
        val name = DorkPlan.forName("Satya Nadella")
        val handle = DorkPlan.forHandle("torvalds")

        assertEquals(DorkPlan.NAME_BUDGET, name.count { it.executed })
        assertEquals(DorkPlan.HANDLE_BUDGET, handle.count { it.executed })
        assertTrue("plan should be larger than the budget", name.size > DorkPlan.NAME_BUDGET)

        // Round-robin means no single section may eat the budget.
        val sections = handle.filter { it.executed }.map { it.section }.distinct()
        assertTrue("expected several sections in the budget, got $sections", sections.size >= 4)
        assertTrue(
            "the Instagram footprint must actually run",
            DorkPlan.Section.InstagramFootprint in sections,
        )
    }

    @Test
    fun `the handle plan substitutes and stays quoted`() {
        val plan = DorkPlan.forHandle("@torvalds")
        assertTrue(plan.none { it.text.contains("@@") })
        assertTrue(plan.any { it.text == "site:instagram.com/torvalds" })
        assertTrue(plan.any { it.text == "site:reddit.com \"u/torvalds\"" })
        assertTrue(plan.any { it.text == "site:linkedin.com/in/torvalds" })
        plan.forEach { assertTrue("query must name the handle: ${it.text}", "torvalds" in it.text) }
    }

    @Test
    fun `the host decides the section, not the query that found it`() {
        assertEquals(
            DorkPlan.Section.Professional,
            DorkPlan.sectionFor("www.linkedin.com", DorkPlan.Section.News),
        )
        assertEquals(
            DorkPlan.Section.InstagramFootprint,
            DorkPlan.sectionFor("instagram.com", DorkPlan.Section.Social),
        )
        assertEquals(
            DorkPlan.Section.Mentions,
            DorkPlan.sectionFor("some-blog.example", DorkPlan.Section.Mentions),
        )
    }

    // ── Live sources ─────────────────────────────────────────────

    @Test
    fun `wikidata turns a name into a linkedin profile`() = runBlocking {
        val people = PersonIntel.wikidata("Satya Nadella")
        assertTrue("expected at least one person entry", people.isNotEmpty())
        val p = people.first()
        println("wikidata: ${p.name} — ${p.description}")
        println("  links: ${p.links.map { it.label + "=" + it.handle }}")
        println("  facts: ${p.facts}")

        val linkedin = p.links.firstOrNull { it.label == "LinkedIn" }
        assertNotNull("Wikidata publishes P6634 for this person", linkedin)
        assertTrue(linkedin!!.url.startsWith("https://www.linkedin.com/in/"))
        assertTrue("expected an employer or occupation", p.facts.isNotEmpty())
    }

    @Test
    fun `github finds accounts by the name on the profile`() = runBlocking {
        val devs = PersonIntel.github("Linus Torvalds", limit = 2)
        println("github: ${devs.map { it.login + " (" + it.name + ")" }}")
        assertTrue(devs.isNotEmpty())
        assertTrue("torvalds should rank for his own name", devs.any { it.login == "torvalds" })
    }

    @Test
    fun `a deep search completes and reports its own limits`() = runBlocking {
        var finished: DeepSearch.Result? = null
        var progressEvents = 0

        DeepSearch.run("torvalds").collect { ev ->
            when (ev) {
                is DeepSearch.Event.Progress -> {
                    progressEvents++
                    assertTrue(ev.percent in 0..99)
                }
                is DeepSearch.Event.Finished -> finished = ev.result
            }
        }

        val r = requireNonNull(finished)
        println("deep search: ${r.hits} pages across ${r.sections.size} sections")
        r.sections.forEach { s -> println("  ${s.section.label}: ${s.hits.size}") }
        r.engineNote?.let { println("  engines: $it") }

        assertTrue("progress must be streamed", progressEvents >= DorkPlan.HANDLE_BUDGET)
        assertEquals(DeepSearch.Mode.Handle, r.mode)
        assertEquals(DorkPlan.HANDLE_BUDGET, r.queriesRun)
        assertTrue("the plan is always returned", r.plan.size > DorkPlan.HANDLE_BUDGET)

        // The Instagram limitation must be stated whether or not anything was
        // found, because an empty section is exactly when someone assumes the
        // app checked and there was nothing there.
        assertTrue(
            "the Instagram caveat must always be reported",
            r.notes.any { "comment text is not in any public search index" in it },
        )

        // Whatever came back must satisfy the query that produced it.
        r.sections.flatMap { it.hits }.forEach { hit ->
            assertTrue(
                "unverified hit survived: ${hit.url} from ${hit.query}",
                WebSearch.constraintsOf(hit.query).accepts(hit.url, hit.title, hit.snippet),
            )
        }
    }

    private fun <T> requireNonNull(v: T?): T {
        assertNotNull("the search must finish", v)
        return v!!
    }
}
