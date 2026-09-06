package com.aryan.myrecon.data

import java.net.URLEncoder

/**
 * The query catalogue behind Deep Search.
 *
 * A dork is just a search with operators in it, and which operators are used
 * decides whether a hit means anything. `site:reddit.com/user/bob` can only
 * match a URL under `/user/`, so a result really is that account's page.
 * `site:reddit.com "bob"` matches any thread where somebody typed the word —
 * still worth seeing, but it is a mention, not an account. The plan keeps the
 * two apart by section rather than mixing them into one list of "findings".
 *
 * Two things come out of here:
 *
 *   • The **executed** queries — a budget the app actually runs through
 *     [WebSearch], ordered so the precise ones are spent first. The budget is
 *     small on purpose: every query is an HTTP request from someone's phone,
 *     spaced to stay under the engines' patience.
 *   • The **full plan** — every query in the catalogue, rendered as a link the
 *     user can tap to run in their own browser against Google, which no
 *     keyless client can reach. This is the escape hatch when the in-app
 *     engines rate-limit, and it is also simply more thorough than any budget
 *     could be.
 */
object DorkPlan {

    /**
     * A result grouping.
     *
     * Sections exist so that "a LinkedIn profile page" and "a forum thread
     * that says your name" cannot be presented as the same kind of fact.
     */
    enum class Section(val label: String, val blurb: String) {
        Professional(
            "Professional & LinkedIn",
            "Work history, company pages and professional directories.",
        ),
        Social(
            "Social profiles",
            "Accounts on the large consumer platforms.",
        ),
        InstagramFootprint(
            "Instagram footprint",
            "Instagram pages that a search engine has actually indexed.",
        ),
        Discussions(
            "Comments & discussions",
            "Places this handle has posted or been replied to in public.",
        ),
        News(
            "News & press",
            "Articles, interviews and announcements naming this person.",
        ),
        Research(
            "Publications & research",
            "Papers, preprints and academic profiles.",
        ),
        Records(
            "Companies & public records",
            "Company filings and official registers.",
        ),
        Documents(
            "Documents & pastes",
            "Files and paste sites carrying the term.",
        ),
        Mentions(
            "Other web mentions",
            "Pages that mention the target without being a profile.",
        ),
    }

    /**
     * One query in the plan.
     *
     * [executed] marks the ones inside the app's budget, so the UI can show
     * what was run and what is only offered as a link — a distinction that
     * matters when a section comes back empty.
     */
    data class Query(
        val text: String,
        val section: Section,
        val executed: Boolean = false,
    ) {
        val google: String get() = "https://www.google.com/search?q=" + enc(text)
        val duck: String get() = "https://duckduckgo.com/?q=" + enc(text)
        val bing: String get() = "https://www.bing.com/search?q=" + enc(text)
    }

    private fun enc(s: String): String = URLEncoder.encode(s, "UTF-8")

    /**
     * How many queries the app runs itself.
     *
     * Chosen against the throttle in [WebSearch]: at ~750 ms apart this lands
     * a full run in roughly the same time as the platform sweep, which is what
     * the progress UI is already sized for.
     */
    const val NAME_BUDGET = 16
    const val HANDLE_BUDGET = 18

    // ── Name plans ───────────────────────────────────────────────

    /**
     * Queries for a person's name.
     *
     * Ordered professional-first. Someone searching a full name is nearly
     * always after the working identity — where they work, what they do — and
     * LinkedIn is where that lives, so the budget is spent there before it
     * reaches general mentions.
     */
    fun forName(raw: String): List<Query> {
        val n = raw.trim()
        val q = "\"" + n + "\""
        val plan = mutableListOf<Query>()

        fun add(section: Section, vararg queries: String) {
            queries.forEach { plan += Query(it, section) }
        }

        // LinkedIn twice on purpose. The path-scoped form is the precise one,
        // but the engines that answer us honour `site:` inconsistently, and the
        // loose form is what actually surfaced /in/satyanadella when tested.
        add(
            Section.Professional,
            "site:linkedin.com/in $q",
            "$q linkedin",
            "site:linkedin.com $q",
            "site:crunchbase.com $q",
            "site:about.me $q",
            "site:theorg.com $q",
            "site:xing.com $q",
            "site:wellfound.com $q",
            "site:muckrack.com $q",
            "site:rocketreach.co $q",
            "site:zoominfo.com $q",
        )

        add(
            Section.Social,
            "site:instagram.com $q",
            "site:facebook.com $q",
            "site:x.com $q",
            "site:youtube.com $q",
            "site:tiktok.com $q",
            "site:threads.net $q",
            "site:reddit.com $q",
            "site:medium.com $q",
            "site:pinterest.com $q",
        )

        add(
            Section.News,
            "$q interview",
            "$q news",
            "$q press release",
            "$q profile biography",
        )

        add(
            Section.Research,
            "site:researchgate.net $q",
            "site:orcid.org $q",
            "site:scholar.google.com $q",
            "site:academia.edu $q",
            "site:arxiv.org $q",
            "site:ssrn.com $q",
        )

        add(
            Section.Records,
            "site:opencorporates.com $q",
            "site:sec.gov $q",
            "site:zaubacorp.com $q",
            "site:gov.uk $q",
        )

        add(
            Section.Documents,
            "$q filetype:pdf",
            "$q resume filetype:pdf",
            "$q cv filetype:pdf",
        )

        // Interleave so the budget covers several sections rather than eleven
        // professional queries and nothing else. The first entry of each
        // section is tried before the second entry of any of them.
        return budget(plan, NAME_BUDGET)
    }

    // ── Handle plans ─────────────────────────────────────────────

    /**
     * Queries for a handle.
     *
     * The Instagram section is the one people ask for and the one that needs
     * the most care. Comment *bodies* on Instagram are not in any public
     * index — reading them takes a logged-in session, which this app does not
     * have and will not fake. What is indexed, and what these queries reach,
     * is the profile page itself, post and reel pages whose caption or mention
     * text carries the handle, and pages elsewhere on the web that link to or
     * embed `instagram.com/<handle>`. That is a real footprint; it is not the
     * comment history, and the UI says so rather than letting the section
     * imply otherwise.
     */
    fun forHandle(raw: String): List<Query> {
        val h = raw.trim().removePrefix("@")
        val q = "\"" + h + "\""
        val at = "\"@" + h + "\""
        val plan = mutableListOf<Query>()

        fun add(section: Section, vararg queries: String) {
            queries.forEach { plan += Query(it, section) }
        }

        // Path-scoped: a hit can only be that account's own page.
        add(
            Section.Social,
            "site:instagram.com/$h",
            "site:x.com/$h",
            "site:tiktok.com/@$h",
            "site:youtube.com/@$h",
            "site:reddit.com/user/$h",
            "site:github.com/$h",
            "site:medium.com/@$h",
            "site:pinterest.com/$h",
            "site:facebook.com/$h",
            "site:threads.net/@$h",
        )

        add(
            Section.Professional,
            "site:linkedin.com/in/$h",
            "site:about.me/$h",
            "site:behance.net/$h",
            "site:dribbble.com/$h",
        )

        add(
            Section.InstagramFootprint,
            "site:instagram.com $at",
            "site:instagram.com/p $q",
            "site:instagram.com/reel $q",
            "\"instagram.com/$h\"",
            // Third-party Instagram viewers. Offered as links only — they
            // appear and disappear constantly and are never worth an HTTP
            // request from the budget, but when one is alive it is the closest
            // a keyless search gets to post-level detail.
            "site:picuki.com $q",
            "site:imginn.com $q",
        )

        add(
            Section.Discussions,
            "site:reddit.com \"u/$h\"",
            "site:news.ycombinator.com $q",
            "site:disqus.com $q",
            "site:x.com $at",
            "site:youtube.com $at",
            "site:stackoverflow.com $q",
            "site:quora.com $q",
            "site:github.com $at",
        )

        add(
            Section.Documents,
            "site:pastebin.com $q",
            "site:gist.github.com $q",
            "$q filetype:pdf",
            "site:scribd.com $q",
        )

        add(
            Section.Mentions,
            "$at profile",
            "$q username",
        )

        return budget(plan, HANDLE_BUDGET)
    }

    /**
     * Mark the first [n] queries as executed, taking them round-robin across
     * sections so no single section can eat the whole budget.
     *
     * Queries the engines cannot verify are never executed: [WebSearch] would
     * refuse them anyway, and a plan entry that is offered as a link is still
     * useful in a browser where Google will answer it.
     */
    private fun budget(plan: List<Query>, n: Int): List<Query> {
        val bySection = plan.groupBy { it.section }
        val order = mutableListOf<Query>()
        var round = 0
        while (order.size < plan.size) {
            var added = false
            bySection.values.forEach { qs ->
                qs.getOrNull(round)?.let { order += it; added = true }
            }
            if (!added) break
            round++
        }

        val chosen = order.filter { runnable(it.text) }.take(n).map { it.text }.toSet()
        return plan.map { if (it.text in chosen) it.copy(executed = true) else it }
    }

    /**
     * A query is runnable only if a result can be checked against it.
     *
     * Bing's keyless endpoint answers a query it dislikes with ten results for
     * something else, so a query carrying no `site:`, no quoted phrase and no
     * `filetype:` would accept that garbage wholesale. Such a query is offered
     * as a browser link and never run in-app.
     */
    fun runnable(text: String): Boolean {
        val c = WebSearch.constraintsOf(text)
        return c.site != null || c.phrases.isNotEmpty() || c.filetype != null
    }

    // ── Result placement ─────────────────────────────────────────

    /**
     * Section a hit belongs in, by host.
     *
     * The host wins over the query that found it: a linkedin.com URL turned up
     * by a news query is still a professional profile, and filing it under
     * "news" because of how it was reached would be an accident of the plan
     * rather than a property of the result.
     */
    private val HOST_SECTIONS: List<Pair<Section, List<String>>> = listOf(
        Section.Professional to listOf(
            "linkedin.com", "xing.com", "about.me", "crunchbase.com", "wellfound.com",
            "angel.co", "theorg.com", "muckrack.com", "rocketreach.co", "zoominfo.com",
            "glassdoor.com", "f6s.com", "behance.net", "dribbble.com", "apollo.io",
        ),
        Section.InstagramFootprint to listOf(
            "instagram.com", "picuki.com", "imginn.com", "dumpor.com", "pixwox.com",
        ),
        Section.Social to listOf(
            "facebook.com", "x.com", "twitter.com", "tiktok.com", "youtube.com",
            "youtu.be", "threads.net", "pinterest.com", "snapchat.com", "vk.com",
            "tumblr.com", "flickr.com", "mastodon.social", "bsky.app",
        ),
        Section.Discussions to listOf(
            "reddit.com", "news.ycombinator.com", "disqus.com", "quora.com",
            "stackoverflow.com", "stackexchange.com", "superuser.com", "serverfault.com",
            "forum.xda-developers.com", "community.spiceworks.com",
        ),
        Section.Research to listOf(
            "researchgate.net", "orcid.org", "scholar.google.com", "academia.edu",
            "arxiv.org", "ssrn.com", "semanticscholar.org", "pubmed.ncbi.nlm.nih.gov",
            "doi.org", "springer.com", "sciencedirect.com",
        ),
        Section.Records to listOf(
            "opencorporates.com", "sec.gov", "zaubacorp.com", "gov.uk",
            "companieshouse.gov.uk", "tofler.in",
        ),
        // Press and reference. Without these a Wikipedia article turned up by
        // the query `"<name>" linkedin` files itself under Professional, which
        // reads as a professional directory listing and is not one.
        Section.News to listOf(
            "wikipedia.org", "britannica.com", "forbes.com", "reuters.com",
            "bloomberg.com", "nytimes.com", "wsj.com", "ft.com", "bbc.com",
            "bbc.co.uk", "cnbc.com", "cnn.com", "theguardian.com",
            "businessinsider.com", "techcrunch.com", "theverge.com", "wired.com",
            "indiatimes.com", "hindustantimes.com", "thehindu.com", "ndtv.com",
            "livemint.com", "business-standard.com",
        ),
        Section.Documents to listOf(
            "pastebin.com", "gist.github.com", "scribd.com", "slideshare.net",
            "throwbin.io", "controlc.com",
        ),
    )

    fun sectionFor(host: String, fallback: Section): Section {
        val h = host.removePrefix("www.")
        HOST_SECTIONS.forEach { (section, hosts) ->
            if (hosts.any { h == it || h.endsWith(".$it") }) return section
        }
        return fallback
    }
}
