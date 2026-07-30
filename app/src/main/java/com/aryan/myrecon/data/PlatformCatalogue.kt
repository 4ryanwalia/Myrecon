package com.aryan.myrecon.data

/**
 * The platforms checked for a username.
 *
 * Generated from backend/modules/username_checker.py so the app and the server
 * agree on what "118 platforms" means. Regenerate rather than hand-edit if the
 * server list changes, or the two will silently drift apart.
 */
data class PlatformDef(
    val name: String,
    val template: String,
    val okStatus: Int,
    val category: String,
    /**
     * A JSON endpoint that answers 200 when the account exists and 404 when it
     * does not. Where one exists it is used instead of scraping HTML, because
     * it is unambiguous — GitHub's API is a clean yes/no where its web page
     * needs guesswork.
     */
    val apiTemplate: String? = null,
    /** Extra headers the API needs (Instagram requires an app id). */
    val apiHeaders: Map<String, String> = emptyMap(),
) {
    fun urlFor(username: String): String = template.replace("{username}", username)
    fun apiUrlFor(username: String): String? = apiTemplate?.replace("{username}", username)
}

object PlatformCatalogue {

    private data class P(val n: String, val u: String, val s: Int)

    private fun group(category: String, vararg items: P) =
        items.map { p ->
            val api = API_ENDPOINTS[p.n]
            PlatformDef(
                name = p.n, template = p.u, okStatus = p.s, category = category,
                apiTemplate = api?.first, apiHeaders = api?.second ?: emptyMap(),
            )
        }

    /**
     * Platforms with a public JSON endpoint that gives an unambiguous answer.
     *
     * Verified by hand: GitHub returns 200 for a real login and 404 otherwise.
     * Instagram's web_profile_info is included because its HTML page is
     * useless for detection — it serves a byte-identical 593 KB shell whether
     * or not the account exists, so scraping it can only ever guess. The API
     * rate-limits datacentre addresses, but this runs on a phone, where a
     * residential address is far less likely to be throttled.
     */
    private val API_ENDPOINTS: Map<String, Pair<String, Map<String, String>>> = mapOf(
        "GitHub" to ("https://api.github.com/users/{username}" to emptyMap()),
        "Instagram" to (
            "https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
                to mapOf("X-IG-App-ID" to "936619743392459")
            ),
        "Reddit" to ("https://www.reddit.com/user/{username}/about.json" to emptyMap()),
    )

    val ALL: List<PlatformDef> = buildList {
        addAll(group("Social",
            P("Twitter / X", "https://x.com/{username}", 200),
            P("Instagram", "https://www.instagram.com/{username}/", 200),
            P("Facebook", "https://www.facebook.com/{username}", 200),
            P("TikTok", "https://www.tiktok.com/@{username}", 200),
            P("Snapchat", "https://www.snapchat.com/add/{username}", 200),
            P("Tumblr", "https://{username}.tumblr.com", 200),
            P("Pinterest", "https://www.pinterest.com/{username}/", 200),
            P("Flickr", "https://www.flickr.com/people/{username}/", 200),
            P("VK", "https://vk.com/{username}", 200),
            P("Mastodon", "https://mastodon.social/@{username}", 200),
            P("Threads", "https://www.threads.net/@{username}", 200),
        ))
        addAll(group("Professional",
            P("LinkedIn", "https://www.linkedin.com/in/{username}", 200),
            P("About.me", "https://about.me/{username}", 200),
            P("Behance", "https://www.behance.net/{username}", 200),
            P("Dribbble", "https://dribbble.com/{username}", 200),
            P("AngelList", "https://angel.co/u/{username}", 200),
            P("Gravatar", "https://en.gravatar.com/{username}", 200),
        ))
        addAll(group("Developer",
            P("GitHub", "https://github.com/{username}", 200),
            P("GitLab", "https://gitlab.com/{username}", 200),
            P("Bitbucket", "https://bitbucket.org/{username}/", 200),
            P("CodePen", "https://codepen.io/{username}", 200),
            P("Replit", "https://replit.com/@{username}", 200),
            P("StackOverflow", "https://stackoverflow.com/users/{username}", 200),
            P("Dev.to", "https://dev.to/{username}", 200),
            P("Hashnode", "https://hashnode.com/@{username}", 200),
            P("HackerRank", "https://www.hackerrank.com/{username}", 200),
            P("LeetCode", "https://leetcode.com/{username}/", 200),
            P("Codeforces", "https://codeforces.com/profile/{username}", 200),
            P("Kaggle", "https://www.kaggle.com/{username}", 200),
            P("npm", "https://www.npmjs.com/~{username}", 200),
            P("PyPI", "https://pypi.org/user/{username}/", 200),
            P("Docker Hub", "https://hub.docker.com/u/{username}", 200),
            P("Gist", "https://gist.github.com/{username}", 200),
            P("Glitch", "https://glitch.com/@{username}", 200),
            P("Launchpad", "https://launchpad.net/~{username}", 200),
            P("SourceForge", "https://sourceforge.net/u/{username}/", 200),
            P("CoderWall", "https://coderwall.com/{username}", 200),
        ))
        addAll(group("Forums",
            P("Reddit", "https://www.reddit.com/user/{username}", 200),
            P("Quora", "https://www.quora.com/profile/{username}", 200),
            P("Hacker News", "https://news.ycombinator.com/user?id={username}", 200),
            P("Disqus", "https://disqus.com/by/{username}/", 200),
            P("ProductHunt", "https://www.producthunt.com/@{username}", 200),
            P("Lobsters", "https://lobste.rs/u/{username}", 200),
            P("Discourse (Meta)", "https://meta.discourse.org/u/{username}", 200),
        ))
        addAll(group("Video",
            P("YouTube", "https://www.youtube.com/@{username}", 200),
            P("Twitch", "https://www.twitch.tv/{username}", 200),
            P("Vimeo", "https://vimeo.com/{username}", 200),
            P("DailyMotion", "https://www.dailymotion.com/{username}", 200),
            P("Rumble", "https://rumble.com/user/{username}", 200),
            P("Odysee", "https://odysee.com/@{username}", 200),
            P("Kick", "https://kick.com/{username}", 200),
        ))
        addAll(group("Audio",
            P("SoundCloud", "https://soundcloud.com/{username}", 200),
            P("Bandcamp", "https://{username}.bandcamp.com", 200),
            P("Spotify", "https://open.spotify.com/user/{username}", 200),
            P("MixCloud", "https://www.mixcloud.com/{username}/", 200),
            P("Last.fm", "https://www.last.fm/user/{username}", 200),
            P("Genius", "https://genius.com/{username}", 200),
        ))
        addAll(group("Gaming",
            P("Steam", "https://steamcommunity.com/id/{username}", 200),
            P("Chess.com", "https://www.chess.com/member/{username}", 200),
            P("Lichess", "https://lichess.org/@/{username}", 200),
            P("Roblox", "https://www.roblox.com/user.aspx?username={username}", 200),
            P("Osu!", "https://osu.ppy.sh/users/{username}", 200),
            P("Minecraft", "https://namemc.com/profile/{username}", 200),
            P("Fortnite Tracker", "https://fortnitetracker.com/profile/all/{username}", 200),
            P("Xbox Gamertag", "https://xboxgamertag.com/search/{username}", 200),
        ))
        addAll(group("Photo & Art",
            P("500px", "https://500px.com/p/{username}", 200),
            P("DeviantArt", "https://www.deviantart.com/{username}", 200),
            P("ArtStation", "https://www.artstation.com/{username}", 200),
            P("Unsplash", "https://unsplash.com/@{username}", 200),
            P("Imgur", "https://imgur.com/user/{username}", 200),
            P("VSCO", "https://vsco.co/{username}/gallery", 200),
            P("Giphy", "https://giphy.com/{username}", 200),
        ))
        addAll(group("Blogging",
            P("Medium", "https://medium.com/@{username}", 200),
            P("WordPress", "https://{username}.wordpress.com", 200),
            P("Blogger", "https://{username}.blogspot.com", 200),
            P("Substack", "https://{username}.substack.com", 200),
            P("Wattpad", "https://www.wattpad.com/user/{username}", 200),
            P("LiveJournal", "https://{username}.livejournal.com", 200),
            P("Ghost", "https://{username}.ghost.io", 200),
            P("Hashnode Blog", "https://{username}.hashnode.dev", 200),
        ))
        addAll(group("Finance",
            P("TradingView", "https://www.tradingview.com/u/{username}/", 200),
            P("CoinMarketCap", "https://coinmarketcap.com/community/profile/{username}/", 200),
        ))
        addAll(group("Messaging",
            P("Telegram", "https://t.me/{username}", 200),
            P("Keybase", "https://keybase.io/{username}", 200),
        ))
        addAll(group("Academic",
            P("ResearchGate", "https://www.researchgate.net/profile/{username}", 200),
            P("ORCID", "https://orcid.org/{username}", 200),
        ))
        addAll(group("Marketplace",
            P("Etsy", "https://www.etsy.com/shop/{username}", 200),
            P("eBay", "https://www.ebay.com/usr/{username}", 200),
            P("Poshmark", "https://poshmark.com/closet/{username}", 200),
            P("Depop", "https://www.depop.com/{username}/", 200),
            P("OKCupid", "https://www.okcupid.com/profile/{username}", 200),
        ))
        addAll(group("Paste",
            P("Pastebin", "https://pastebin.com/u/{username}", 200),
        ))
        addAll(group("Other",
            P("Linktree", "https://linktr.ee/{username}", 200),
            P("Carrd", "https://{username}.carrd.co", 200),
            P("Bio.link", "https://bio.link/{username}", 200),
            P("Beacons", "https://beacons.ai/{username}", 200),
            P("Buymeacoffee", "https://buymeacoffee.com/{username}", 200),
            P("Ko-fi", "https://ko-fi.com/{username}", 200),
            P("Patreon", "https://www.patreon.com/{username}", 200),
            P("Gumroad", "https://gumroad.com/{username}", 200),
            P("Notion", "https://{username}.notion.site", 200),
            P("Calendly", "https://calendly.com/{username}", 200),
            P("Trello", "https://trello.com/{username}", 200),
            P("SlideShare", "https://www.slideshare.net/{username}", 200),
            P("Scribd", "https://www.scribd.com/{username}", 200),
            P("Issuu", "https://issuu.com/{username}", 200),
            P("Instructables", "https://www.instructables.com/member/{username}/", 200),
            P("Hackaday", "https://hackaday.io/{username}", 200),
            P("Goodreads", "https://www.goodreads.com/{username}", 200),
            P("MyAnimeList", "https://myanimelist.net/profile/{username}", 200),
            P("Letterboxd", "https://letterboxd.com/{username}/", 200),
            P("Trakt", "https://trakt.tv/users/{username}", 200),
            P("Duolingo", "https://www.duolingo.com/profile/{username}", 200),
            P("Codecademy", "https://www.codecademy.com/profiles/{username}", 200),
            P("FreeCodeCamp", "https://www.freecodecamp.org/{username}", 200),
            P("HackerOne", "https://hackerone.com/{username}", 200),
            P("BugCrowd", "https://bugcrowd.com/{username}", 200),
        ))
    }

    /**
     * Platforms that expose a verifiable link rather than only a display name —
     * a signed proof, a commit email, a DNS record. A hit on one of these is
     * stronger evidence of common control than a matching handle elsewhere.
     */
    val CORROBORATING = setOf("GitHub", "Keybase", "GitLab", "StackOverflow", "ORCID")

    /**
     * Platforms that serve a page for *any* handle and echo it back, so the
     * usual "does the page name its owner?" test cannot separate a real profile
     * from a placeholder. Telegram, for instance, titles the page
     * "Telegram: Contact @<anything>" whether or not the account exists.
     *
     * Measured, not guessed: these are what survived as false positives when a
     * deliberately nonsensical handle was swept across the full catalogue.
     * Results here are reported as unverified rather than found — the evidence
     * genuinely does not support either claim.
     */
    val ECHOES_HANDLE = setOf(
        "Telegram", "Medium", "Duolingo", "MixCloud", "Hashnode Blog",
        "Notion", "Beacons", "Carrd", "Bio.link",
        // Added after the recall fix: these render the searched handle inside a
        // "no results for X" page, so the handle-mention signal fires for
        // accounts that do not exist.
        "Giphy", "HackerRank", "Trakt",
    )

    val size: Int get() = ALL.size
}
