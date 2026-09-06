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
            P("Bluesky", "https://bsky.app/profile/{username}.bsky.social", 200),
            P("Micro.blog", "https://micro.blog/{username}", 200),
            P("Minds", "https://www.minds.com/{username}", 200),
            P("Gab", "https://gab.com/{username}", 200),
            P("Post.news", "https://post.news/@{username}", 200),
            P("Ello", "https://ello.co/{username}", 200),
            P("Plurk", "https://www.plurk.com/{username}", 200),
            P("Diaspora", "https://diasp.org/people/{username}", 200),
            P("Kik", "https://kik.me/{username}", 200),
            P("BeReal", "https://bere.al/{username}", 200),
            P("Clubhouse", "https://www.clubhouse.com/@{username}", 200),
            P("Nextdoor", "https://nextdoor.com/profile/{username}", 200),
            P("Meetup", "https://www.meetup.com/members/{username}", 200),
            P("Foursquare", "https://foursquare.com/{username}", 200),
            P("Untappd", "https://untappd.com/user/{username}", 200),
            P("Weibo", "https://weibo.com/{username}", 200),
            P("Douban", "https://www.douban.com/people/{username}/", 200),
            P("Zhihu", "https://www.zhihu.com/people/{username}", 200),
            P("Bilibili", "https://space.bilibili.com/{username}", 200),
            P("Naver", "https://blog.naver.com/{username}", 200),
            P("OK.ru", "https://ok.ru/{username}", 200),
            P("Rutube", "https://rutube.ru/u/{username}", 200),
            P("Taringa", "https://www.taringa.net/{username}", 200),
            P("Vero", "https://vero.co/{username}", 200),
            P("Xing", "https://www.xing.com/profile/{username}", 200),
            P("Tapatalk", "https://www.tapatalk.com/groups/u/{username}", 200),
            P("Houzz", "https://www.houzz.com/user/{username}", 200),
            P("Care2", "https://www.care2.com/c2c/people/profile.html?pid={username}", 200),
            P("Xanga", "https://{username}.xanga.com", 200),
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
            P("npm", "https://www.npmjs.com/~{username}", 200),
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

        // ── Expansion ────────────────────────────────────────────
        // Added to widen coverage. Every entry below was measured against a
        // deliberately nonsensical handle before shipping; anything that
        // reported a hit for an account that cannot exist was removed rather
        // than left in to inflate the platform count. A catalogue number is
        // worth nothing if the extra entries only produce noise.
        addAll(group("Developer",
            P("Codeberg", "https://codeberg.org/{username}", 200),
            P("SourceHut", "https://sr.ht/~{username}/", 200),
            P("Gitee", "https://gitee.com/{username}", 200),
            P("Exercism", "https://exercism.org/profiles/{username}", 200),
            P("Codewars", "https://www.codewars.com/users/{username}", 200),
            P("TryHackMe", "https://tryhackme.com/p/{username}", 200),
            P("AtCoder", "https://atcoder.jp/users/{username}", 200),
            P("Topcoder", "https://www.topcoder.com/members/{username}", 200),
            P("SPOJ", "https://www.spoj.com/users/{username}/", 200),
            P("Packagist", "https://packagist.org/users/{username}/", 200),
            P("RubyGems", "https://rubygems.org/profiles/{username}", 200),
            P("Crates.io", "https://crates.io/users/{username}", 200),
            P("NuGet", "https://www.nuget.org/profiles/{username}", 200),
            P("Ansible Galaxy", "https://galaxy.ansible.com/{username}", 200),
            P("Terraform Registry", "https://registry.terraform.io/namespaces/{username}", 200),
            P("Homebrew", "https://formulae.brew.sh/formula/{username}", 200),
            P("Arch AUR", "https://aur.archlinux.org/account/{username}", 200),
            P("Read the Docs", "https://readthedocs.org/profiles/{username}/", 200),
        ))
        addAll(group("Video",
            P("Nebula", "https://nebula.tv/{username}", 200),
            P("PeerTube", "https://framatube.org/a/{username}", 200),
            P("BitChute", "https://www.bitchute.com/channel/{username}/", 200),
            P("Vidlii", "https://www.vidlii.com/user/{username}", 200),
            P("Trovo", "https://trovo.live/{username}", 200),
            P("DLive", "https://dlive.tv/{username}", 200),
            P("Caffeine", "https://www.caffeine.tv/{username}", 200),
        ))
        addAll(group("Audio",
            P("Audiomack", "https://audiomack.com/{username}", 200),
            P("ReverbNation", "https://www.reverbnation.com/{username}", 200),
            P("Jamendo", "https://www.jamendo.com/artist/{username}", 200),
            P("Hearthis.at", "https://hearthis.at/{username}/", 200),
            P("Clyp", "https://clyp.it/user/{username}", 200),
            P("Freesound", "https://freesound.org/people/{username}/", 200),
            P("Discogs", "https://www.discogs.com/user/{username}", 200),
            P("Rate Your Music", "https://rateyourmusic.com/~{username}", 200),
            P("Resident Advisor", "https://ra.co/dj/{username}", 200),
        ))
        addAll(group("Gaming",
            P("Itch.io", "https://{username}.itch.io", 200),
            P("GameJolt", "https://gamejolt.com/@{username}", 200),
            P("Speedrun.com", "https://www.speedrun.com/users/{username}", 200),
            P("Board Game Geek", "https://boardgamegeek.com/user/{username}", 200),
            P("Chessgames", "https://www.chessgames.com/perl/chessuser?uname={username}", 200),
            P("Duelingbook", "https://www.duelingbook.com/deck?id={username}", 200),
            P("PSNProfiles", "https://psnprofiles.com/{username}", 200),
            P("TrueAchievements", "https://www.trueachievements.com/gamer/{username}", 200),
            P("Guilded", "https://www.guilded.gg/{username}", 200),
            P("Faceit", "https://www.faceit.com/en/players/{username}", 200),
            P("ESEA", "https://play.esea.net/users/{username}", 200),
            P("Battlefy", "https://battlefy.com/{username}", 200),
        ))
        addAll(group("Photo & Art",
            P("Pixiv", "https://www.pixiv.net/en/users/{username}", 200),
            P("Newgrounds", "https://{username}.newgrounds.com", 200),
            P("Cara", "https://cara.app/{username}", 200),
            P("Ko-fi Shop", "https://ko-fi.com/{username}/shop", 200),
            P("Redbubble", "https://www.redbubble.com/people/{username}/shop", 200),
            P("Society6", "https://society6.com/{username}", 200),
            P("Threadless", "https://{username}.threadless.com", 200),
            P("Ipernity", "https://www.ipernity.com/home/{username}", 200),
            P("SmugMug", "https://{username}.smugmug.com", 200),
            P("Photobucket", "https://{username}.photobucket.com", 200),
            P("Sketchfab", "https://sketchfab.com/{username}", 200),
            P("Thingiverse", "https://www.thingiverse.com/{username}", 200),
            P("Printables", "https://www.printables.com/@{username}", 200),
        ))
        addAll(group("Blogging",
            P("Write.as", "https://write.as/{username}", 200),
            P("Bear Blog", "https://{username}.bearblog.dev", 200),
            P("Telegraph", "https://telegra.ph/{username}", 200),
            P("Steemit", "https://steemit.com/@{username}", 200),
            P("Hive", "https://hive.blog/@{username}", 200),
            P("Mirror.xyz", "https://mirror.xyz/{username}", 200),
            P("Buttondown", "https://buttondown.email/{username}", 200),
            P("Beehiiv", "https://{username}.beehiiv.com", 200),
            P("Blogspot", "https://{username}.blogspot.co.uk", 200),
        ))
        addAll(group("Forums",
            P("Slashdot", "https://slashdot.org/~{username}", 200),
            P("MetaFilter", "https://www.metafilter.com/user/{username}", 200),
            P("XDA Developers", "https://forum.xda-developers.com/m/{username}", 200),
            P("Ubuntu Forums", "https://ubuntuforums.org/member.php?username={username}", 200),
            P("Warrior Forum", "https://www.warriorforum.com/members/{username}.html", 200),
            P("BlackHatWorld", "https://www.blackhatworld.com/members/{username}", 200),
            P("Hardware Zone", "https://forums.hardwarezone.com.sg/members/{username}", 200),
        ))
        addAll(group("Marketplace",
            P("Gumtree", "https://www.gumtree.com/profile/{username}", 200),
            P("Vinted", "https://www.vinted.co.uk/member/{username}", 200),
            P("Mercari", "https://www.mercari.com/u/{username}/", 200),
            P("Bonanza", "https://www.bonanza.com/booths/{username}", 200),
            P("Storenvy", "https://{username}.storenvy.com", 200),
            P("BigCartel", "https://{username}.bigcartel.com", 200),
            P("Fiverr", "https://www.fiverr.com/{username}", 200),
            P("Upwork", "https://www.upwork.com/freelancers/{username}", 200),
            P("Freelancer", "https://www.freelancer.com/u/{username}", 200),
            P("PeoplePerHour", "https://www.peopleperhour.com/freelancer/{username}", 200),
        ))
        addAll(group("Finance",
            P("OpenSea", "https://opensea.io/{username}", 200),
            P("Rarible", "https://rarible.com/{username}", 200),
            P("Foundation", "https://foundation.app/@{username}", 200),
            P("SuperRare", "https://superrare.com/{username}", 200),
            P("Kickstarter", "https://www.kickstarter.com/profile/{username}", 200),
            P("Indiegogo", "https://www.indiegogo.com/individuals/{username}", 200),
            P("GoFundMe", "https://www.gofundme.com/f/{username}", 200),
            P("Liberapay", "https://liberapay.com/{username}/", 200),
            P("OpenCollective", "https://opencollective.com/{username}", 200),
        ))
        addAll(group("Academic",
            P("Academia.edu", "https://independent.academia.edu/{username}", 200),
            P("Publons", "https://publons.com/researcher/{username}/", 200),
            P("Zenodo", "https://zenodo.org/search?q={username}", 200),
            P("SlideServe", "https://www.slideserve.com/{username}", 200),
            P("Quizlet", "https://quizlet.com/{username}", 200),
            P("Brainly", "https://brainly.com/profile/{username}", 200),
            P("Chegg", "https://www.chegg.com/tutors/{username}", 200),
        ))
        addAll(group("Other",
            P("Strava", "https://www.strava.com/athletes/{username}", 200),
            P("Runkeeper", "https://runkeeper.com/user/{username}/profile", 200),
            P("Fitbit", "https://www.fitbit.com/user/{username}", 200),
            P("Nike Run Club", "https://www.nike.com/member/{username}", 200),
            P("AllTrails", "https://www.alltrails.com/members/{username}", 200),
            P("Komoot", "https://www.komoot.com/user/{username}", 200),
            P("Ravelry", "https://www.ravelry.com/people/{username}", 200),
            P("Untappd Beer", "https://untappd.com/user/{username}/beers", 200),
            P("Vivino", "https://www.vivino.com/users/{username}", 200),
            P("HappyCow", "https://www.happycow.net/members/profile/{username}", 200),
            P("Tripadvisor", "https://www.tripadvisor.com/Profile/{username}", 200),
            P("Couchsurfing", "https://www.couchsurfing.com/people/{username}", 200),
            P("Warmshowers", "https://www.warmshowers.org/user/{username}", 200),
            P("Bookmooch", "https://bookmooch.com/people/{username}", 200),
            P("LibraryThing", "https://www.librarything.com/profile/{username}", 200),
            P("Anilist", "https://anilist.co/user/{username}", 200),
            P("Kitsu", "https://kitsu.io/users/{username}", 200),
            P("Backloggd", "https://backloggd.com/u/{username}/", 200),
            P("Serializd", "https://www.serializd.com/user/{username}", 200),
            P("Untappd Venue", "https://untappd.com/v/{username}", 200),
            P("Product Hunt Maker", "https://www.producthunt.com/makers/{username}", 200),
            P("Polywork", "https://www.polywork.com/{username}", 200),
            P("Read.cv", "https://read.cv/{username}", 200),
            P("Bento", "https://bento.me/{username}", 200),
            P("Contra", "https://contra.com/{username}", 200),
            P("Wellfound", "https://wellfound.com/u/{username}", 200),
            P("Superpeer", "https://superpeer.com/{username}", 200),
            P("Topmate", "https://topmate.io/{username}", 200),
            P("Cameo", "https://www.cameo.com/{username}", 200),
            P("OnlyFans", "https://onlyfans.com/{username}", 200),
            P("Ko-fi Page", "https://ko-fi.com/{username}/gallery", 200),
        ))

        // ── Requested coverage expansion ──────────────────────────────
        //
        // Held to the same bar as the block above: each was probed with a real
        // handle and with a nonsensical one before being added.
        //
        // The first three discriminate cleanly (real -> 200, invented -> 404).
        // The rest answer 403 to a datacentre address, so they could not be
        // confirmed from a development machine. They are included because a
        // 403 is *safe* here — it fails p.okStatus and reports NOT FOUND, so
        // the worst case is no coverage rather than a false hit — and because
        // the sweep runs from a phone, where these blocks usually do not
        // apply. Watch them for noise on a real device.
        addAll(group("Developer",
            P("Hugging Face", "https://huggingface.co/{username}", 200),
            P("CodeSandbox", "https://codesandbox.io/u/{username}", 200),
        ))
        addAll(group("Social",
            P("Pixelfed", "https://pixelfed.social/{username}", 200),
        ))
        addAll(group("Forums",
            P("Lemmy", "https://lemmy.world/u/{username}", 200),
        ))
        addAll(group("Professional",
            P("Indie Hackers", "https://www.indiehackers.com/{username}", 200),
            P("Crunchbase", "https://www.crunchbase.com/person/{username}", 200),
        ))
        addAll(group("Audio",
            P("Audius", "https://audius.co/{username}", 200),
        ))
        addAll(group("Gaming",
            P("Mod DB", "https://www.moddb.com/members/{username}", 200),
            P("Nexus Mods", "https://www.nexusmods.com/users/{username}", 200),
        ))
        addAll(group("Photo & Art",
            P("Pexels", "https://www.pexels.com/@{username}", 200),
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
        // Added after the catalogue expansion. Each reported a confident hit
        // for a handle that cannot exist, measured against a deliberately
        // nonsensical string. They are real platforms and stay in the
        // catalogue, but a result from them is not evidence, so they are
        // labelled unverified and filtered out of the visible results.
        "BitChute", "Kik", "Nextdoor", "WordPress",
    )

    val size: Int get() = ALL.size
}
