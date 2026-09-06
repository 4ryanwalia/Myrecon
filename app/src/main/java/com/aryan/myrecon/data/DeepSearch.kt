package com.aryan.myrecon.data

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.channelFlow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.Dispatchers

/**
 * Deep Search — one query in, everything public that answers it out.
 *
 * The tool has two modes and picks between them from the input, because the
 * two questions are genuinely different:
 *
 *   **A name** ("Satya Nadella") asks *who is this person*. That is answered by
 *   records that tie a name to an identity — Wikidata, which publishes a
 *   person's LinkedIn ID outright, GitHub's full-name index, ORCID's registry —
 *   and then by a professional-first sweep of the indexed web.
 *
 *   **A handle** ("torvalds") asks *where has this account been*. That is
 *   answered by dorking: path-scoped queries that can only match the account's
 *   own pages, then mention-level queries across the places people comment.
 *
 * What this deliberately does **not** do is turn one into the other. Deriving
 * `satyanadella` from "Satya Nadella" and reporting whoever registered that
 * handle is how a tool ends up confidently naming the wrong person; the
 * investigation orchestrator removed exactly that feature for exactly that
 * reason, and it is not coming back in through this door. A name search finds
 * pages that carry the name. A handle search finds pages that carry the
 * handle. Neither is upgraded into a claim about a person.
 *
 * Runs entirely on the device against keyless sources.
 */
object DeepSearch {

    enum class Mode(val label: String) { Name("Name"), Handle("Handle") }

    /** Hits that landed in one section. */
    data class SectionResult(
        val section: DorkPlan.Section,
        val hits: List<WebSearch.Hit>,
    )

    /**
     * An account a structured source named, as opposed to one a search engine
     * turned up. Carried separately because the evidence is different in kind.
     */
    data class Account(
        val platform: String,
        val url: String,
        val handle: String?,
        val detail: String,
        val avatar: String?,
        /** Which registry said so — shown, so the claim can be traced. */
        val source: String,
    )

    data class Result(
        val subject: String,
        val mode: Mode,
        /** Wikidata entries matching the name. Candidates, never conclusions. */
        val people: List<PersonIntel.Person> = emptyList(),
        /** Keybase's signed cross-platform proofs, for a handle. */
        val identity: KeybaseIntel.Identity? = null,
        val accounts: List<Account> = emptyList(),
        val sections: List<SectionResult> = emptyList(),
        /** Every query in the plan, run or not, as tap-to-run browser links. */
        val plan: List<DorkPlan.Query> = emptyList(),
        val queriesRun: Int = 0,
        val hits: Int = 0,
        /** Set when the keyless engines stopped answering mid-run. */
        val engineNote: String? = null,
        val notes: List<String> = emptyList(),
    )

    sealed interface Event {
        data class Progress(
            val phase: String,
            val detail: String,
            val percent: Int,
            val found: Int,
        ) : Event

        data class Finished(val result: Result) : Event
    }

    /**
     * Which question was asked.
     *
     * Whitespace is the signal. "Satya Nadella" is a name; `satyanadella` is a
     * handle; `@satyanadella` is a handle said explicitly. Nothing cleverer is
     * needed and anything cleverer would be wrong more often — a single word
     * typed into an OSINT tool is overwhelmingly a handle.
     */
    fun detectMode(input: String): Mode {
        val s = input.trim()
        if (s.startsWith("@")) return Mode.Handle
        return if (s.contains(' ')) Mode.Name else Mode.Handle
    }

    /**
     * Run a deep search, streaming progress.
     *
     * Ordered so the cheap, high-value structured sources answer first: by the
     * time the query budget is a third spent there is already an identity card
     * on screen, and the rest fills in underneath it.
     */
    fun run(input: String): Flow<Event> = channelFlow {
        val subject = input.trim().removePrefix("@").trim()
        val mode = detectMode(input)
        WebSearch.newSession()

        val plan = if (mode == Mode.Name) DorkPlan.forName(subject) else DorkPlan.forHandle(subject)
        val toRun = plan.filter { it.executed }
        // Structured lookups plus one step per query, so the bar tracks work
        // done rather than jumping at the end.
        val steps = toRun.size + if (mode == Mode.Name) 3 else 1
        var step = 0
        var found = 0

        suspend fun progress(phase: String, detail: String) {
            send(Event.Progress(phase, detail, (step * 100 / steps).coerceIn(0, 99), found))
        }

        var people: List<PersonIntel.Person> = emptyList()
        var identity: KeybaseIntel.Identity? = null
        val accounts = mutableListOf<Account>()

        if (mode == Mode.Name) {
            progress("Identity records", "Wikidata — public figure entries…")
            people = runCatching { PersonIntel.wikidata(subject) }.getOrDefault(emptyList())
            found += people.sumOf { it.links.size }
            step++

            progress("Identity records", "GitHub — accounts using this name…")
            runCatching { PersonIntel.github(subject) }.getOrDefault(emptyList()).forEach { d ->
                accounts += Account(
                    platform = "GitHub",
                    url = d.url,
                    handle = d.login,
                    detail = listOfNotNull(
                        d.name, d.company?.removePrefix("@"), d.location, d.bio,
                    ).joinToString(" · ").ifBlank { "GitHub account" },
                    avatar = d.avatar,
                    source = "GitHub full-name search",
                )
            }
            found += accounts.size
            step++

            progress("Identity records", "ORCID — research registry…")
            runCatching { PersonIntel.orcid(subject) }.getOrDefault(emptyList()).forEach { r ->
                accounts += Account(
                    platform = "ORCID",
                    url = r.url,
                    handle = r.orcid,
                    detail = (r.institutions.joinToString(", ").ifBlank { "Registered researcher" }),
                    avatar = null,
                    source = "ORCID public registry",
                )
            }
            step++
        } else {
            progress("Identity records", "Keybase — signed cross-platform proofs…")
            // A Keybase account with no proofs on it has nothing to say here.
            // The card's whole claim is "these accounts are signed for by the
            // same key", and "0 verified links" states that claim emptily.
            identity = runCatching { KeybaseIntel.lookup(subject) }.getOrNull()
                ?.takeIf { it.found && it.proofs.isNotEmpty() }
            found += identity?.proofs?.size ?: 0
            step++
        }

        // Wikidata already resolved the person's own accounts; promote them so
        // they sit with the other accounts rather than only inside the card.
        people.firstOrNull()?.links?.forEach { link ->
            accounts += Account(
                platform = link.label,
                url = link.url,
                handle = link.handle,
                detail = "Listed on this person's Wikidata entry",
                avatar = null,
                source = "Wikidata",
            )
        }

        val collected = mutableMapOf<DorkPlan.Section, MutableList<WebSearch.Hit>>()
        val seen = mutableSetOf<String>()

        for (query in toRun) {
            progress("Searching", query.text)
            val hits = runCatching { WebSearch.search(query.text) }.getOrDefault(emptyList())
            hits.forEach { hit ->
                val key = hit.url.trimEnd('/').lowercase()
                if (!seen.add(key)) return@forEach
                val section = DorkPlan.sectionFor(hit.host, query.section)
                collected.getOrPut(section) { mutableListOf() } += hit
                found++
            }
            step++
        }

        val sections = DorkPlan.Section.entries
            .mapNotNull { s -> collected[s]?.takeIf { it.isNotEmpty() }?.let { SectionResult(s, it) } }

        val engines = WebSearch.availableEngines()
        val engineNote = when {
            engines.isEmpty() ->
                "Both keyless search engines stopped answering this device part-way through " +
                    "the run — they rate-limit by address. The queries below still work: tap " +
                    "any of them to run it in your browser, where Google will answer."
            engines.size < WebSearch.Engine.entries.size ->
                "DuckDuckGo rate-limited this device during the run, so the rest of the " +
                    "queries went to Bing. Tap any query to re-run it in your browser."
            else -> null
        }

        send(
            Event.Finished(
                Result(
                    subject = subject,
                    mode = mode,
                    people = people,
                    identity = identity,
                    accounts = accounts.distinctBy { it.url.trimEnd('/').lowercase() },
                    sections = sections,
                    plan = plan,
                    queriesRun = toRun.size,
                    hits = sections.sumOf { it.hits.size },
                    engineNote = engineNote,
                    notes = notes(mode) + situational(mode, sections),
                )
            )
        )
    }.flowOn(Dispatchers.IO)

    /**
     * Notes that depend on how the run actually went.
     *
     * A handle search that surfaced no profile pages has not shown that the
     * accounts do not exist — the path-scoped queries it relies on are the ones
     * the fallback engine handles worst. The Username tool answers that question
     * properly, by asking each platform directly, so the result points at it
     * rather than leaving an empty section to be read as an all-clear.
     */
    private fun situational(mode: Mode, sections: List<SectionResult>): List<String> {
        if (mode != Mode.Handle) return emptyList()
        val profiles = sections.any {
            it.section == DorkPlan.Section.Social || it.section == DorkPlan.Section.Professional
        }
        if (profiles) return emptyList()
        return listOf(
            "No profile pages came back for this handle. That is a statement about " +
                "what search engines have indexed, not about what exists — the Username " +
                "tool asks each of the " + PlatformCatalogue.size + " platforms directly " +
                "and is the better answer to \"does this account exist\"."
        )
    }

    /**
     * What this search cannot see.
     *
     * Stated in the result rather than buried in a help page, because the gap
     * between what an OSINT tool appears to have checked and what it actually
     * checked is where people draw wrong conclusions.
     */
    private fun notes(mode: Mode): List<String> = buildList {
        add(
            "Everything here is a page a search engine has indexed. An absent result " +
                "means not indexed, which is not the same as not existing."
        )
        if (mode == Mode.Name) {
            add(
                "Records matched on a name are candidates, not identifications. Several " +
                    "people share most names — read the description on each entry before " +
                    "treating it as the right person."
            )
            add(
                "LinkedIn serves most profiles only to signed-in visitors, so a profile " +
                    "can exist and still not appear here. Wikidata's LinkedIn identifier is " +
                    "the reliable path when the person has an entry."
            )
        } else {
            add(
                "Instagram comment text is not in any public search index — reading it " +
                    "needs a signed-in session, which this app does not have and will not " +
                    "fake. What the Instagram section finds is the indexed footprint: the " +
                    "profile page, post and reel pages whose caption or mentions carry the " +
                    "handle, and pages elsewhere that link to it."
            )
            add(
                "Reddit, Hacker News and Disqus are the platforms whose comments genuinely " +
                    "are indexed, which is why the discussion section leans on them."
            )
            add(
                "Accounts sharing a handle are frequently unrelated people. Treat this as a " +
                    "set of pages using the same name, not one person's history."
            )
        }
    }
}
