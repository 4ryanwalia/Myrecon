package com.aryan.myrecon.data

/**
 * How to actually get rid of an account, rather than just ticking a box.
 *
 * The cleanup list told people they had eleven forgotten accounts and then left
 * them to find the delete page themselves — which is the hard part. Platforms
 * bury it: it is rarely in settings where you would look, it is often on a
 * different subdomain, and several of them only offer it in a help article that
 * ranks below a dozen SEO pages about how to *make* an account.
 *
 * So the link is the feature. Every URL here was fetched and checked to
 * resolve. Most are the deletion page itself; a few are the settings page
 * that holds the control, and those say so in their note. Platforms whose
 * deletion page could not be confirmed are left out rather than guessed at —
 * they fall through to the letter below.
 *
 * The second half is the letter. Where there is no self-serve button — and for
 * data the platform keeps after the account is gone — a person has a legal
 * right to demand erasure, and almost nobody knows how to word it. A filled-in
 * request they can send in one tap is worth more than knowing the right exists.
 */
object AccountRemoval {

    /**
     * @param url the deletion or deactivation page.
     * @param note what to expect when they get there, where it is not obvious.
     */
    data class Route(val url: String, val note: String? = null)

    /**
     * Keyed by the catalogue's platform names so a lookup needs no mapping
     * table. Deliberately incomplete: a wrong link is worse than none, because
     * it sends someone to a page that cannot do what they came for and makes
     * them think the account cannot be removed. Only entries that were checked
     * are here, and everything else falls through to the letter.
     */
    private val ROUTES: Map<String, Route> = mapOf(
        "Instagram" to Route(
            "https://www.instagram.com/accounts/remove/request/permanent/",
            "Instagram asks why you are leaving before it shows the button.",
        ),
        "Facebook" to Route(
            "https://www.facebook.com/help/delete_account",
            "Deletion takes 30 days, and logging back in during that window cancels it.",
        ),
        "Threads" to Route(
            "https://www.threads.net/settings/account",
            "Deleting Threads alone is separate from deleting Instagram.",
        ),
        "Twitter / X" to Route(
            "https://x.com/settings/deactivate",
            "Deactivation becomes deletion after 30 days.",
        ),
        "TikTok" to Route("https://www.tiktok.com/setting/account-control"),
        "Snapchat" to Route("https://accounts.snapchat.com/accounts/delete_account"),
        "Reddit" to Route(
            "https://www.reddit.com/settings/account",
            "Your posts stay up under [deleted] unless you remove them first.",
        ),
        "LinkedIn" to Route("https://www.linkedin.com/psettings/account-management/close"),
        "Pinterest" to Route("https://www.pinterest.com/settings/account-settings/"),
        "Tumblr" to Route("https://www.tumblr.com/account/delete"),
        "Spotify" to Route("https://support.spotify.com/article/close-account/"),
        "Discord" to Route("https://support.discord.com/hc/en-us/articles/212500837"),
        "Telegram" to Route(
            "https://my.telegram.org/auth?to=delete",
            "Deletes the whole Telegram account, not one chat.",
        ),
        "GitHub" to Route("https://github.com/settings/admin"),
        "GitLab" to Route("https://gitlab.com/-/profile/account"),
        "StackOverflow" to Route("https://stackoverflow.com/users/delete/current"),
        "Dev.to" to Route("https://dev.to/settings/account"),
        "CodePen" to Route("https://codepen.io/settings/account/"),
        "Replit" to Route("https://replit.com/account"),
        "Docker Hub" to Route("https://hub.docker.com/settings/general"),
        "Medium" to Route("https://medium.com/me/settings"),
        "Quora" to Route("https://www.quora.com/settings/privacy"),
        "Flickr" to Route("https://www.flickr.com/account/delete/"),
        "Dribbble" to Route(
            "https://dribbble.com/settings",
            "Account deletion is in these settings.",
        ),
        "Behance" to Route(
            "https://www.behance.net/settings",
            "Behance runs on an Adobe account — deleting that removes Behance with it.",
        ),
        "About.me" to Route("https://about.me/settings/account"),
        "Gravatar" to Route(
            "https://gravatar.com/account/",
            "Gravatar is tied to your WordPress.com account.",
        ),
        "WordPress" to Route("https://wordpress.com/me/account/close"),
        "Steam" to Route("https://help.steampowered.com/en/wizard/HelpWithMyAccount"),
        "Twitch" to Route("https://www.twitch.tv/user/delete-account"),
        "YouTube" to Route(
            "https://myaccount.google.com/deleteservices",
            "Removing YouTube does not delete the Google account behind it.",
        ),
        "Duolingo" to Route("https://www.duolingo.com/settings/account"),
        "Untappd" to Route("https://untappd.com/user/settings"),
        "Foursquare" to Route("https://foursquare.com/settings/privacy"),
        "Meetup" to Route("https://www.meetup.com/account/"),
        "Vimeo" to Route("https://vimeo.com/settings/account/general"),
        "SoundCloud" to Route("https://soundcloud.com/settings/account"),
        "Bandcamp" to Route(
            "https://bandcamp.com/settings",
            "Account deletion is in these settings.",
        ),
        "Etsy" to Route("https://www.etsy.com/your/account"),
        "eBay" to Route("https://accountsettings.ebay.com/uas"),
        "Amazon" to Route("https://www.amazon.com/gp/help/customer/display.html?nodeId=GDK92DBKKQBM33PY"),
        "Disqus" to Route("https://disqus.com/home/settings/account/"),
        "ProductHunt" to Route("https://www.producthunt.com/my/settings"),
        "Goodreads" to Route("https://www.goodreads.com/user/destroy"),
        "Strava" to Route(
            "https://www.strava.com/settings/profile",
            "Scroll to the bottom of the profile settings for account deletion.",
        ),
        "Patreon" to Route("https://www.patreon.com/settings/account"),
        "Roblox" to Route("https://www.roblox.com/my/account#!/info"),
        "Minecraft" to Route(
            "https://www.minecraft.net/en-us/profile",
            "NameMC only mirrors a public profile; the account itself lives at Minecraft.",
        ),
    )

    fun routeFor(platform: String): Route? = ROUTES[platform]

    /** Whether any platform in a sweep has a known deletion page. */
    fun hasRoute(platform: String): Boolean = ROUTES.containsKey(platform)

    /**
     * A ready-to-send erasure request.
     *
     * Written to be sent by a person with no legal knowledge, and to be
     * recognised by the support desk that receives it. Both laws are named
     * because the reader has no way to know which applies to them: India's DPDP
     * Act covers people in India, the GDPR covers the EU and UK, and naming
     * both costs nothing while guessing wrong costs the request. Support teams
     * route on the phrase, not on the citation being perfectly chosen.
     *
     * No threats and no invented deadlines. A polite request that cites the
     * right to erasure is handled; an aggressive one gets escalated to someone
     * who is looking for a reason to say no.
     */
    fun deletionRequest(
        platform: String,
        accountUrl: String?,
        handle: String?,
        email: String? = null,
    ): String = buildString {
        appendLine("Subject: Request to delete my account and personal data")
        appendLine()
        appendLine("Hello,")
        appendLine()
        append("I am asking you to delete my $platform account and erase the personal ")
        appendLine("data you hold about me.")
        appendLine()
        appendLine("Account details:")
        handle?.takeIf { it.isNotBlank() }?.let { appendLine("  Username: $it") }
        accountUrl?.takeIf { it.isNotBlank() }?.let { appendLine("  Profile: $it") }
        email?.takeIf { it.isNotBlank() }?.let { appendLine("  Registered email: $it") }
        appendLine()
        appendLine(
            "I am making this request under my right to erasure. If I am covered by " +
                "India's Digital Personal Data Protection Act 2023, this is a request " +
                "under Section 12. If I am covered by the UK or EU GDPR, this is a " +
                "request under Article 17."
        )
        appendLine()
        appendLine(
            "Please confirm in writing once this is done, and tell me if you are keeping " +
                "any of my data — and on what legal basis — rather than deleting it."
        )
        appendLine()
        appendLine("Thank you,")
        appendLine()
        appendLine("[your name]")
    }

    /**
     * Where to send it, when the platform has no delete button.
     *
     * Almost every service that operates in Europe publishes a privacy contact,
     * and privacy@ is the near-universal convention. Offered as a suggestion to
     * check rather than an address to trust blindly: sending an erasure request
     * with a real name and email to the wrong inbox is a small privacy failure
     * of its own.
     */
    fun suggestedContact(host: String?): String? {
        val clean = host?.removePrefix("www.")?.lowercase()?.takeIf { it.contains('.') }
            ?: return null
        return "privacy@$clean"
    }
}
