"""Generate one published, schema-shaped content record for each inventory route.

Copy is deliberately cautious: platform matches are leads to verify, private
accounts are out of scope, and live deletion procedures are linked to official
service pages rather than guessed from stale UI instructions.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
TODAY = date.today().isoformat()
REVIEWER = "Codex editorial pass"
CTA = {"label": "Search a public username with MyRecon", "href": "/"}
MYRECON = "https://www.myrecon.xyz/"

PLATFORM_NAMES = {
    "instagram": "Instagram", "tiktok": "TikTok", "x-twitter": "X / Twitter", "reddit": "Reddit",
    "telegram": "Telegram", "youtube": "YouTube", "facebook": "Facebook", "linkedin": "LinkedIn",
    "snapchat": "Snapchat", "pinterest": "Pinterest", "discord": "Discord", "twitch": "Twitch",
    "github": "GitHub", "spotify": "Spotify", "steam": "Steam", "threads": "Threads",
    "bluesky": "Bluesky", "mastodon": "Mastodon", "tumblr": "Tumblr", "medium": "Medium",
    "quora": "Quora", "vimeo": "Vimeo", "dailymotion": "Dailymotion", "behance": "Behance",
    "dribbble": "Dribbble", "deviantart": "DeviantArt", "figma": "Figma", "soundcloud": "SoundCloud",
    "substack": "Substack", "patreon": "Patreon", "fiverr": "Fiverr", "upwork": "Upwork",
    "goodreads": "Goodreads", "letterboxd": "Letterboxd", "lastfm": "Last.fm", "roblox": "Roblox",
    "epic-games": "Epic Games", "xbox": "Xbox", "playstation-network": "PlayStation Network",
    "hacker-news": "Hacker News", "stack-overflow": "Stack Overflow", "keybase": "Keybase",
    "kaggle": "Kaggle", "gravatar": "Gravatar", "venmo": "Venmo", "cash-app": "Cash App",
    "etsy": "Etsy", "ebay": "eBay", "amazon": "Amazon", "flickr": "Flickr", "500px": "500px",
    "strava": "Strava", "duolingo": "Duolingo", "wattpad": "Wattpad", "airbnb": "Airbnb",
    "kick": "Kick", "duo": "Duo", "minecraft": "Minecraft", "itchio": "itch.io",
    "bandcamp": "Bandcamp", "deezer": "Deezer", "researchgate": "ResearchGate", "orcid": "ORCID",
    "gumroad": "Gumroad", "ko-fi": "Ko-fi", "unsplash": "Unsplash", "producthunt": "Product Hunt",
    "opensea": "OpenSea", "peerlist": "Peerlist", "lemmy": "Lemmy", "artstation": "ArtStation",
    "devto": "DEV Community", "thingiverse": "Thingiverse",
}

PLATFORM_URLS = {
    "Instagram": "https://www.instagram.com/", "TikTok": "https://www.tiktok.com/", "X": "https://x.com/",
    "Reddit": "https://www.reddit.com/", "Telegram": "https://telegram.org/", "YouTube": "https://www.youtube.com/",
    "Facebook": "https://www.facebook.com/", "LinkedIn": "https://www.linkedin.com/", "Snapchat": "https://www.snapchat.com/",
    "Pinterest": "https://www.pinterest.com/", "Discord": "https://discord.com/", "Twitch": "https://www.twitch.tv/",
    "X / Twitter": "https://x.com/",
    "GitHub": "https://github.com/", "Spotify": "https://open.spotify.com/", "Steam": "https://steamcommunity.com/",
    "Threads": "https://www.threads.net/", "Bluesky": "https://bsky.app/", "Mastodon": "https://joinmastodon.org/",
    "Tumblr": "https://www.tumblr.com/", "Medium": "https://medium.com/", "Quora": "https://www.quora.com/",
    "Vimeo": "https://vimeo.com/", "Dailymotion": "https://www.dailymotion.com/", "Behance": "https://www.behance.net/",
    "Dribbble": "https://dribbble.com/", "DeviantArt": "https://www.deviantart.com/", "Figma": "https://www.figma.com/",
    "SoundCloud": "https://soundcloud.com/", "Substack": "https://substack.com/", "Patreon": "https://www.patreon.com/",
    "Fiverr": "https://www.fiverr.com/", "Upwork": "https://www.upwork.com/", "Goodreads": "https://www.goodreads.com/",
    "Letterboxd": "https://letterboxd.com/", "Last.fm": "https://www.last.fm/", "Roblox": "https://www.roblox.com/",
    "Epic Games": "https://www.epicgames.com/", "Xbox": "https://www.xbox.com/", "PlayStation Network": "https://www.playstation.com/",
    "Hacker News": "https://news.ycombinator.com/", "Stack Overflow": "https://stackoverflow.com/", "Keybase": "https://keybase.io/",
    "Kaggle": "https://www.kaggle.com/", "Gravatar": "https://gravatar.com/", "Venmo": "https://venmo.com/",
    "Cash App": "https://cash.app/", "Etsy": "https://www.etsy.com/", "eBay": "https://www.ebay.com/",
    "Amazon": "https://www.amazon.com/", "Flickr": "https://www.flickr.com/", "500px": "https://500px.com/",
    "Strava": "https://www.strava.com/", "Duolingo": "https://www.duolingo.com/", "Wattpad": "https://www.wattpad.com/",
    "Airbnb": "https://www.airbnb.com/", "Kick": "https://kick.com/", "Duo": "https://duo.com/",
    "Minecraft": "https://www.minecraft.net/", "itch.io": "https://itch.io/", "Bandcamp": "https://bandcamp.com/",
    "Deezer": "https://www.deezer.com/", "ResearchGate": "https://www.researchgate.net/", "ORCID": "https://orcid.org/",
    "Gumroad": "https://gumroad.com/", "Ko-fi": "https://ko-fi.com/", "Unsplash": "https://unsplash.com/",
    "Product Hunt": "https://www.producthunt.com/", "OpenSea": "https://opensea.io/", "Peerlist": "https://peerlist.io/",
    "Lemmy": "https://join-lemmy.org/", "ArtStation": "https://www.artstation.com/", "DEV Community": "https://dev.to/",
    "Thingiverse": "https://www.thingiverse.com/",
}

ENTITY_NAMES = {
    "account": "account", "activity": "activity page", "username": "username", "channel": "channel",
    "profile": "profile", "author": "author page", "publication": "publication", "board": "board",
    "user": "user profile", "streamer": "streamer page", "creator": "creator page", "gamertag": "gamertag",
    "portfolio": "portfolio", "shop": "shop", "seller": "seller page", "artist": "artist page",
    "researcher": "researcher record", "photographer": "photographer page", "maker": "maker page",
    "developer": "developer page", "player": "player name", "reviewer": "reviewer profile",
}

TARGET_ROUTE_INFO = {
    "roblox-user": ("Roblox", "user profile", "Roblox usernames and display names are different fields; check the resolved account name rather than relying on a display-name search."),
    "amazon-author-profile": ("Amazon", "author page", "Amazon author pages and contributor profiles are different public surfaces. Confirm that the destination is the intended author page and not a product listing or a namesake."),
    "roblox-profile": ("Roblox", "player profile", "A player name, display name, and profile URL may not be interchangeable. Open the official profile before recording a match."),
    "pinterest-board": ("Pinterest", "board", "A Pinterest username lookup checks a profile handle, not a particular board title. Use the platform's own board search when you need a named board."),
    "pinterest-profile": ("Pinterest", "profile", "Pinterest usernames and board names describe different public surfaces. Confirm whether the result is a profile or a board before citing it."),
    "vimeo-user": ("Vimeo", "user profile", "Vimeo public pages may use custom profile names and video URLs. Confirm the account page itself instead of treating a video result as a user match."),
    "vimeo-profile": ("Vimeo", "profile", "A public video can appear without establishing who controls the uploader account. Confirm the profile page and its visible links."),
    "discord-user": ("Discord", "user profile", "Discord does not provide a general public people directory. A username search cannot reveal private accounts, server membership, or a person's identity."),
    "discord-username": ("Discord", "username", "Discord account identifiers and profile visibility depend on current platform settings. This guide does not search private users or server membership."),
    "kick-streamer": ("Kick", "streamer page", "A channel name can change and a stream may be unavailable when checked. Verify the public creator page and its linked profile details."),
    "duo-profile": ("Duo", "service profile", "Duo commonly refers to Cisco's enterprise authentication service, not a public social directory. This route cannot promise a public user search; if you meant Duolingo, use its separate profile page."),
    "patreon-creator": ("Patreon", "creator page", "Creator pages and membership content are not the same thing. Review only public page details; paid or member-only content is outside this lookup."),
    "patreon-profile": ("Patreon", "profile", "A public creator page can link to other services, but membership areas and private account details are not public username evidence."),
    "medium-author": ("Medium", "author page", "Medium author pages can be separate from publication pages. Check the author's own profile and distinguish it from a similarly named publication."),
    "medium-publication": ("Medium", "publication", "A Medium publication is an editorial destination, not an individual author profile. Confirm the publication page and its listed editors separately."),
    "threads-account": ("Threads", "account", "A Threads account may share a handle with Instagram, but matching names alone do not establish that the accounts have the same owner."),
    "steam-profile": ("Steam", "profile", "Steam profiles can use a custom URL or a changing display name. Compare the resolved profile identifier and public profile details, not just a name."),
    "behance-portfolio": ("Behance", "portfolio", "A Behance portfolio is a creative-work page. Compare the displayed portfolio and its own profile links; an image or name match alone is weak evidence."),
    "telegram-username": ("Telegram", "username", "A public username can point to a person, bot, or channel. Treat the account type as part of the evidence and do not attempt to identify a private user."),
    "telegram-channel": ("Telegram", "channel", "Telegram channel names and usernames can differ from personal handles. Review the channel's public description and avoid inferring who runs it without corroboration."),
    "x-twitter-account": ("X / Twitter", "account", "X handles can be renamed and reassigned. Check the current profile URL and dated public context before treating a match as continuous ownership."),
    "mastodon-account": ("Mastodon", "account", "Mastodon identities include a server as well as a handle. Search the exact domain-qualified address and confirm the user's current instance."),
    "bluesky-profile": ("Bluesky", "profile", "Bluesky handles can be domain-based and may change. Confirm the resolved profile and the handle shown on the service."),
    "reddit-activity": ("Reddit", "public activity page", "Reddit usernames are not proof of identity, and deleted or removed content can complicate old search results. Review the live public profile."),
    "reddit-profile": ("Reddit", "profile", "A profile match can point to public posts or comments, but those contributions may be edited, removed, or misattributed in search snippets."),
    "steam-community-group": ("Steam", "community group", "A Steam group and a personal profile are different public entities. Check the group page itself and do not infer its members' identities."),
}

COMPARATORS = {
    "sherlock": ("Sherlock", "https://github.com/sherlock-project/sherlock", "CLI", "An open-source command-line username search project.", "A local, scriptable workflow and its documented site checks."),
    "social-searcher": ("Social Searcher", "https://www.social-searcher.com/", "web", "A web service for searching public social and web mentions.", "Search-engine-style discovery for public mentions and supported sources."),
    "namechk": ("Namechk", "https://namechk.com/", "web", "A web-based username and domain availability checker.", "A quick availability-oriented view of names across listed services."),
    "maigret": ("Maigret", "https://github.com/soxoj/maigret", "CLI", "An open-source username OSINT project with a documented site database.", "A command-line investigation and reporting workflow."),
    "usersearch": ("UserSearch", "https://usersearch.org/", "web", "A web-based search service for public username and profile leads.", "A browser-first search surface; check the provider's current scope and terms."),
    "whatsmyname": ("WhatsMyName", "https://github.com/WebBreacher/WhatsMyName", "mixed", "An open-source username search project and site list.", "A community-maintained site list and analyst-controlled workflow."),
    "knowem": ("KnowEm", "https://knowem.com/", "web", "A web service for checking names across social networks and web properties.", "Brand and username availability checks across its current listed services."),
    "spiderfoot": ("SpiderFoot", "https://github.com/smicallef/spiderfoot", "mixed", "An open-source OSINT automation tool with a broad module workflow.", "Configurable, multi-source OSINT collection for analyst-led investigations."),
    "osint-industries": ("OSINT Industries", "https://www.osint.industries/", "web", "A web-based OSINT investigation service.", "Its currently documented investigation modules and account workflow."),
    "social-catfish": ("Social Catfish", "https://socialcatfish.com/", "web", "A people-search and identity-verification service.", "A people-search workflow that may use inputs beyond a username."),
    "spokeo": ("Spokeo", "https://www.spokeo.com/", "web", "A people-search service that organizes public-record and online information.", "People-search reports and the provider's current source coverage."),
    "pipl": ("Pipl", "https://pipl.com/", "web", "An identity-resolution and data service for business use.", "A business identity-data workflow whose access and scope should be confirmed with the provider."),
    "epieos": ("Epieos", "https://epieos.com/", "web", "An OSINT platform for public digital-information research.", "Its current investigation tools and access requirements, as documented by Epieos."),
    "osint-combine": ("OSINT Combine", "https://www.osintcombine.com/", "web", "An OSINT training and tools provider.", "Its curated training and investigation resources, rather than a single username-only check."),
    "seon": ("SEON", "https://seon.io/", "mixed", "A fraud-prevention platform that documents digital-footprint signals and APIs.", "Business risk and digital-footprint signals integrated into fraud workflows."),
    "blackbird": ("Blackbird", "https://github.com/p1ngul1n0/blackbird", "CLI", "An open-source username OSINT project.", "A local investigator workflow and its current documented platform list."),
    "userrecon": ("UserRecon", "https://github.com/thelinuxchoice/userrecon", "CLI", "An open-source username enumeration script.", "A command-line workflow whose repository activity and site behavior should be checked."),
    "osint-framework": ("OSINT Framework", "https://osintframework.com/", "web", "A directory of OSINT resources organized by investigation task.", "A curated starting point for choosing other research tools."),
    "recon-ng": ("Recon-ng", "https://github.com/lanmaster53/recon-ng", "CLI", "An open-source modular reconnaissance framework.", "A configurable framework with modules and an analyst-managed workflow."),
    "phoneinfoga": ("PhoneInfoga", "https://github.com/sundowndev/phoneinfoga", "CLI", "An open-source tool focused on phone-number research.", "Phone-number-oriented checks, which are a different starting input from a username."),
    "namecheckup": ("Namecheckup", "https://namecheckup.com/", "web", "A web-based username availability checking service.", "A browser-based name-availability view across its current service list."),
    "maltego": ("Maltego", "https://www.maltego.com/", "mixed", "An investigation platform for linking entities and data sources.", "Analyst-built relationship graphs and configurable data integrations."),
    "lampyre": ("Lampyre", "https://lampyre.io/", "desktop", "An OSINT and data-analysis platform.", "Desktop investigation workflows and its documented data-source integrations."),
    "usernamecheck": ("UsernameCheck", "https://usernamecheck.com/", "web", "A web-based username search and availability service.", "A quick browser check across the provider's current service list."),
    "ghunt": ("GHunt", "https://github.com/mxrch/GHunt", "CLI", "An open-source project for authorized research into Google-account traces.", "A Google-account-focused workflow, not a general cross-platform username sweep."),
}

GUIDE_ANGLES = {
    "how-to-find-hidden-social-media-accounts": "A handle search can only surface public, supported pages; it cannot establish that an account is hidden or reveal a private profile.",
    "reverse-email-lookup-techniques": "An email address is personal data, so limit checks to an address you own or are authorized to assess and never use password-reset flows to enumerate accounts.",
    "reverse-username-search-workflow": "A useful workflow separates candidate discovery from checking the live profile and recording enough context to reproduce the observation.",
    "digital-footprint-audit-checklist": "A personal audit works best when it starts from identifiers you control and records both what appears and which surfaces could not be checked.",
    "cross-platform-entity-resolution": "Cross-platform linking should combine independent public clues and preserve uncertainty instead of equating a reused handle with one person.",
    "verify-osint-account-matches": "Verification means opening each candidate source, recording observable details, and checking whether independent evidence supports the proposed link.",
    "username-reuse-privacy-risks": "Reusing one handle can make accounts easier to connect, but correlation still needs evidence and should not be treated as proof of identity.",
    "find-old-online-accounts": "For a self-audit, begin with old email receipts, password-manager entries, and public handles you remember, then use official recovery pages.",
    "identify-impersonation-accounts": "Impersonation triage should compare the account with the person's or brand's verified channels and preserve URLs before reporting it.",
    "public-profile-evidence-logging": "A compact evidence log records the canonical page, observation time, visible fields, and limits without collecting unrelated personal details.",
    "search-operators-for-social-profiles": "Search operators can narrow public web results, but indexing is incomplete and snippets may be stale or detached from the current page.",
    "account-enumeration-false-positives": "A response code, generic placeholder, or blocked request is not enough to confirm an account; distinguish unknown from a verified match.",
    "handle-variations-and-aliases": "Test only plausible spelling and punctuation variants derived from the supplied handle, and keep every variation labeled as a separate candidate.",
    "investigate-public-github-exposure": "A repository, commit, or public profile can expose different information; confirm the source page and avoid treating a contribution as account ownership proof.",
    "discover-public-forum-activity": "Forum searches can return quoted text, deleted threads, or matching names, so open the original post and note its date and author context.",
    "link-social-profiles-without-overclaiming": "A public bio link or shared website is stronger context than a matching handle, but even several clues may not prove a person's identity.",
    "osint-investigation-workflow": "A defensible workflow sets a lawful purpose, scope, stop conditions, and evidence notes before any public-source search begins.",
    "privacy-audit-for-families": "A family audit should be coordinated with the account owner, use age-appropriate consent, and focus on reducing unnecessary exposure.",
    "brand-impersonation-monitoring": "Brand monitoring should prioritize official handles, lookalike spellings, and a repeatable report path instead of engaging suspicious accounts.",
    "breach-exposure-vs-public-profiles": "A publicly visible profile and a breach notification describe different exposure types and require separate verification and response steps.",
    "protect-researcher-notes": "Investigation notes should contain only necessary evidence, restrict access, and follow a defined retention and deletion schedule.",
    "responsible-public-data-collection": "Public availability does not remove privacy, terms-of-service, or data-minimization obligations; collect only what the stated task needs.",
    "account-discovery-without-scraping": "A small, manual workflow can use official search and visible public pages without automating access or bypassing service controls.",
    "triage-uncertain-identity-matches": "Triage should preserve confirmed, rejected, and unresolved candidates separately and explain which evidence supports each decision.",
    "build-a-repeatable-footprint-audit": "A repeatable audit uses the same authorized identifiers, date-stamped source list, and consistent outcome labels on each pass.",
    "how-to-find-someone-on-all-social-media": "No single search covers every network; a useful public sweep combines known handles with direct checks and records gaps explicitly.",
    "find-hidden-dating-profiles-by-email": "Email-based dating-account checks can expose sensitive relationship data, so do not enumerate another person's accounts or use recovery prompts; use consent-based, direct communication.",
    "reverse-lookup-phone-number-free-osint": "Phone numbers can be reassigned and linked to sensitive records; use only your own or authorized number and avoid publishing location or identity guesses.",
    "how-to-find-an-exs-secret-account": "Searching an ex-partner's accounts can cross privacy boundaries; this guide limits itself to public information and recommends direct communication or support for safety concerns.",
    "trace-anonymous-telegram-username": "A Telegram handle can identify a public channel or profile but does not justify unmasking an anonymous person or probing private groups.",
    "find-linked-email-addresses-from-username": "Only treat an email as linked when the account owner has published it; do not infer addresses through login, recovery, or verification endpoints.",
    "find-social-profiles-by-full-name": "Common names produce many unrelated profiles; narrow results with a voluntarily public city, organization, or self-linked site and retain ambiguity.",
    "find-public-profiles-by-phone-number": "A phone lookup should begin with an authorized number and a clear purpose, while avoiding sensitive inferences from weak directory matches.",
    "find-business-social-media-profiles": "For a business, start from its official website and verified listings, then compare branding and outbound links before treating a profile as official.",
    "find-creator-profiles-by-username": "Creator pages may be brand names rather than personal accounts; compare portfolios and self-published links rather than assuming a legal identity.",
    "search-usernames-across-social-platforms": "A username sweep produces candidate URLs, so inspect the current page and keep unavailable or restricted sites marked unknown.",
    "use-reverse-image-search-for-profiles": "Image search can find copied or syndicated images, but a shared photo does not prove account ownership and can involve sensitive biometric data.",
    "verify-social-media-profile-ownership": "Ownership checks should rely on direct self-links or an account owner's confirmation, not a name, avatar, or location that many people can share.",
    "distinguish-same-name-social-accounts": "Separate lookalike accounts by their platform IDs, page history, self-links, and dates; do not merge people because their names match.",
    "document-public-web-findings": "A useful record preserves the exact public URL and timestamp, summarizes only relevant visible facts, and avoids storing unnecessary personal data.",
    "track-public-username-changes": "A handle change can break old links or allow reassignment, so date each observation and avoid implying one person controlled every version.",
    "username-search-vs-email-search": "Username and email searches expose different kinds of public clues; choose the least sensitive input that can answer your authorized question.",
    "reduce-public-social-media-footprint": "Exposure reduction starts with account owners reviewing visibility, removing stale details, and using each platform's own privacy controls.",
    "audit-social-media-before-job-search": "A self-audit before a job search should focus on accounts you control, review audience settings, and avoid deleting context impulsively.",
    "protect-family-public-profile-exposure": "Family protection is strongest when the person shown in a profile participates in decisions about photos, names, and visibility.",
    "preserve-osint-evidence-chain": "A basic evidence chain records where a public artifact came from, when it was collected, who handled it, and whether it later changed.",
    "passive-osint-vs-active-collection": "Passive review of already public material differs from contacting accounts, joining communities, or triggering platform actions; define that boundary first.",
    "validate-a-user-search-result": "Validation asks whether the destination is a real, current profile and what evidence supports the match, not whether a tool returned a positive string.",
    "how-to-audit-username-reuse": "A username reuse audit is most defensible when each service result is confirmed independently and the report separates correlation from attribution.",
}

BROKERS = {
    "whitepages": ("Whitepages", "https://www.whitepages.com/", "https://www.whitepages.com/data-policy"),
    "spokeo": ("Spokeo", "https://www.spokeo.com/", "https://www.spokeo.com/optout"),
    "beenverified": ("BeenVerified", "https://www.beenverified.com/", "https://www.beenverified.com/f/optout/search"),
    "fastpeoplesearch": ("FastPeopleSearch", "https://www.fastpeoplesearch.com/", "https://www.fastpeoplesearch.com/optout"),
    "intelius": ("Intelius", "https://www.intelius.com/", "https://www.intelius.com/opt-out/"),
    "radaris": ("Radaris", "https://radaris.com/", "https://radaris.com/control/privacy"),
    "nuwber": ("Nuwber", "https://nuwber.com/", "https://nuwber.com/removal/link"),
    "truepeoplesearch": ("TruePeopleSearch", "https://www.truepeoplesearch.com/", "https://www.truepeoplesearch.com/removal"),
    "familytreenow": ("FamilyTreeNow", "https://www.familytreenow.com/", "https://www.familytreenow.com/optout"),
    "truthfinder": ("TruthFinder", "https://www.truthfinder.com/", "https://www.truthfinder.com/opt-out/"),
    "instant-checkmate": ("Instant Checkmate", "https://www.instantcheckmate.com/", "https://www.instantcheckmate.com/opt-out/"),
    "peoplefinders": ("PeopleFinders", "https://www.peoplefinders.com/", "https://www.peoplefinders.com/opt-out"),
    "peekyou": ("PeekYou", "https://www.peekyou.com/", "https://www.peekyou.com/about/contact/optout/"),
    "peoplewhiz": ("PeopleWhiz", "https://www.peoplewhiz.com/", "https://www.peoplewhiz.com/remove-my-info"),
    "socialcatfish": ("Social Catfish", "https://socialcatfish.com/", "https://socialcatfish.com/opt-out/"),
}

ACCOUNT_HELP = {
    "instagram": "https://help.instagram.com/", "tiktok": "https://support.tiktok.com/",
    "facebook": "https://www.facebook.com/help/", "reddit": "https://support.reddithelp.com/",
    "x": "https://help.x.com/", "snapchat": "https://help.snapchat.com/",
    "linkedin": "https://www.linkedin.com/help/linkedin/", "discord": "https://support.discord.com/",
    "telegram": "https://telegram.org/faq", "pinterest": "https://help.pinterest.com/",
    "twitch": "https://help.twitch.tv/", "steam": "https://help.steampowered.com/",
    "roblox": "https://en.help.roblox.com/", "spotify": "https://support.spotify.com/",
    "github": "https://docs.github.com/en/account-and-profile/", "quora": "https://help.quora.com/",
    "tumblr": "https://help.tumblr.com/", "medium": "https://help.medium.com/",
    "whatsapp": "https://faq.whatsapp.com/", "substack": "https://support.substack.com/",
    "bluesky": "https://bsky.social/about/support", "mastodon": "https://docs.joinmastodon.org/user/profile/",
}

PRIVACY_ROUTE_SERVICE = {
    "delete-whitepages-info": "whitepages", "opt-out-spokeo": "spokeo", "opt-out-of-spokeo": "spokeo",
    "remove-beenverified-record": "beenverified", "opt-out-of-beenverified": "beenverified",
    "delete-fastpeoplesearch": "fastpeoplesearch", "remove-intelius-profile": "intelius",
    "opt-out-radaris": "radaris", "delete-nuwber-record": "nuwber", "opt-out-of-whitepages": "whitepages",
    "remove-from-truepeoplesearch": "truepeoplesearch", "opt-out-familytreenow": "familytreenow",
    "opt-out-truthfinder": "truthfinder", "opt-out-instant-checkmate": "instant-checkmate",
    "remove-from-peoplefinders": "peoplefinders", "remove-from-peekyou": "peekyou",
    "opt-out-peoplewhiz": "peoplewhiz", "opt-out-socialcatfish": "socialcatfish",
}

GOOGLE_ROUTES = {"remove-personal-info-from-google-audit", "request-google-search-removal", "remove-address-from-search-engines"}
GOOGLE_REMOVAL = "https://support.google.com/websearch/answer/9673730"


def words_title(value: str) -> str:
    special = {"osint": "OSINT", "api": "API", "x": "X", "orcid": "ORCID", "kofi": "Ko-fi", "github": "GitHub", "youtube": "YouTube", "tiktok": "TikTok", "last.fm": "Last.fm", "500px": "500px"}
    return " ".join(special.get(word.casefold(), word.capitalize()) for word in re.split(r"\s+", value.strip()))


def keyword_for(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip()


def seo_title(keyword: str) -> str:
    base = words_title(keyword)
    if len(base) <= 49:
        base += " | MyRecon"
    if len(base) > 60:
        base = base[:60].rsplit(" ", 1)[0]
    return base


def common(kind: str, slug: str, keyword: str, title: str, description: str, h1: str, intro: str, sections: list[dict], sources: list[str]) -> dict:
    return {
        "kind": kind,
        "slug": slug,
        "status": "published",
        "title": title,
        "description": description,
        "h1": h1,
        "focus_keyword": keyword,
        "intro": intro,
        "sections": sections,
        "sources": list(dict.fromkeys(sources)),
        "reviewed_at": TODAY,
        "modified_at": TODAY,
        "reviewer": REVIEWER,
        "cta": CTA,
    }


def faq_items(items: list[tuple[str, str]]) -> list[dict]:
    return [{"question": q, "answer": a} for q, a in items]


def target_platform(slug: str) -> tuple[str, str, str, str]:
    if slug in TARGET_ROUTE_INFO:
        name, entity, note = TARGET_ROUTE_INFO[slug]
    else:
        parts = slug.split("-")
        suffixes = sorted(ENTITY_NAMES, key=len, reverse=True)
        entity_key = next((suffix for suffix in suffixes if parts[-len(suffix.split("-")): ] == suffix.split("-")), "profile")
        stem = "-".join(parts[:-len(entity_key.split("-"))])
        name = PLATFORM_NAMES.get(stem, words_title(stem.replace("-", " ")))
        entity = ENTITY_NAMES[entity_key]
        note = f"The {name} {entity} is a distinct public page type; confirm that the resolved URL actually belongs to that page rather than a similarly named post, group, or search result."
    official_url = PLATFORM_URLS.get(name, MYRECON)
    return name, entity, note, official_url


def load_standard_catalogue() -> set[str]:
    path = REPO / "backend" / "data" / "platforms_full.json"
    if not path.exists():
        return set()
    records = json.loads(path.read_text(encoding="utf-8"))
    return {str(record.get("name", "")).strip().casefold() for record in records if isinstance(record, dict)}


CATALOGUE = load_standard_catalogue()


def is_catalogued(name: str) -> bool:
    aliases = {"x / twitter": {"x", "twitter"}, "playstation network": {"playstation network", "playstation"}}
    candidates = aliases.get(name.casefold(), {name.casefold()})
    return bool(CATALOGUE.intersection(candidates))


def target_record(row: dict) -> dict:
    slug, keyword = row["url"].rsplit("/", 1)[-1], row["focus_keyword"]
    name, entity, note, official = target_platform(slug)
    catalogued = is_catalogued(name)
    support = (
        f"The checked-in MyRecon standard catalogue lists {name}. This is a username-level check, not a guarantee that every request will resolve: service changes, rate limits, privacy controls, or temporary blocks can leave a result unknown."
        if catalogued else
        f"The checked-in MyRecon standard catalogue does not list a direct {name} check. Use {name}'s official search or profile pages manually and treat MyRecon results on other sites as unrelated leads, not confirmation of a {name} account."
    )
    if entity in {"board", "publication", "channel"}:
        support += f" A username sweep checks profile handles where available; it does not by itself verify a named {entity}."
    privacy = f"A public {name} {entity} can show only the fields its owner and the service make visible, such as a chosen name, image, biography, posts, or outbound links. Private areas and access-controlled content are outside a public lookup."
    false_positive = f"A reused or renamed handle, a similarly named {entity}, a redirect, or a stale search snippet can create a false lead on {name}. Open the official destination and compare independent public context before attributing it to anyone."
    intro = f"{words_title(keyword)} starts with a candidate handle, but a matching string is only a lead. This {name}-focused page explains how to check the relevant {entity}, what a public result can and cannot show, and how to keep a possible match separate from an identity claim."
    title = seo_title(keyword)
    description = f"Check {name} {entity} results for {keyword}. Learn what public pages can reveal and where coverage stops; start a careful username search with MyRecon."
    if len(description) > 160:
        description = f"{words_title(keyword)}. Check public profile limits and verify results with MyRecon."
    h1 = f"Find a public {name} {entity} by username"
    sections = [
        {"heading": f"What a public {name} {entity} can show", "body": f"Use the official page to confirm the account type, current handle, and information the owner chose to publish. {note} A username result is a starting point for a self-audit or authorized review, not a complete record of the person behind an account."},
        {"heading": f"Coverage and limits for {name}", "body": f"{support} A missing or blocked result cannot establish that no account exists. Do not work around login walls, access controls, rate limits, or service restrictions to force a response."},
        {"heading": "Verify a candidate before you rely on it", "body": f"Open the canonical {name} page, note the URL and observation date, and compare one or more independent details that are voluntarily public. {false_positive} Keep uncertain and unavailable outcomes marked as unknown."},
    ]
    steps = [
        f"Open {official} and use its own public profile search or the exact handle URL when the service documents one. Search only a username you own or are authorized to review; this guide does not cover private-account discovery.",
        f"Open the candidate {entity} page and confirm the destination is a current {name} account, not a generic error, unrelated result, or search-engine snippet. Save the canonical URL and the date if you need a reproducible self-audit.",
        f"Compare a separate, voluntarily public clue such as a self-linked site or matching biography before drawing a conclusion. A handle alone can be shared or reassigned, and blocked checks should stay unknown rather than being recorded as a negative.",
    ]
    record = common("target", slug, keyword, title, description, h1, intro, sections, [official, MYRECON])
    record.update({
        "faq": faq_items([
            (f"Can a {name} username match prove who owns it?", f"No. Handles can be shared, changed, or reassigned. Open the public {entity} and look for independent, voluntarily published context before making an attribution; if evidence is inconclusive, leave the match unresolved."),
            (f"Does this find private {name} profiles?", f"No. This workflow is limited to supported checks and information available on public pages. Private accounts, login-only material, blocked requests, and hidden membership data are not exposed by a username lookup."),
            (f"What should I do if a {name} result is unavailable?", f"Record the check as unavailable or unknown, then use {name}'s official search directly if appropriate. A timeout, redirect, or access block is not proof that the profile is absent."),
        ]),
        "platform": {"name": name, "official_url": official, "public_lookup": support, "limitations": f"Coverage depends on the current {name} interface and supported public checks. Private settings, authentication, rate limits, or technical failures can prevent verification; a missing result is not proof of absence.", "privacy_overview": privacy, "false_positive_note": false_positive},
        "manual_steps": steps,
        "scan_trigger": "username",
    })
    return record


def guide_record(row: dict) -> dict:
    slug, keyword = row["url"].rsplit("/", 1)[-1], row["focus_keyword"]
    angle = GUIDE_ANGLES[slug]
    intro = f"{words_title(keyword)} is best handled as a narrow, documented question rather than a hunt for every possible connection. {angle} This guide gives a repeatable way to check public information, note uncertainty, and stop when the available evidence is not enough."
    title = seo_title(keyword)
    description = f"Learn {keyword} with a focused, privacy-aware workflow. Verify public sources, keep uncertainty visible, and start an authorized username self-audit with MyRecon."
    if len(description) > 160:
        description = f"{words_title(keyword)}. Check public sources, verify matches, and try a careful MyRecon username search."
    h1 = words_title(keyword)
    sections = [
        {"heading": "Define the question and permission", "body": f"Before searching, state what {keyword} needs to answer and which public sources are relevant. {angle} Use identifiers supplied by the account owner or covered by your authorization, and set a stopping point so a narrow review does not expand into unnecessary data collection."},
        {"heading": "Check original public sources", "body": f"Start with an official platform search or canonical page, then open each candidate instead of relying on snippets or copied directories. Record the source URL, date, visible context, and any login wall, block, or ambiguity that limits what you could confirm about {keyword}."},
        {"heading": "Keep conclusions proportional to the evidence", "body": f"Separate confirmed public observations from possibilities and unknowns. A shared handle, name, image, or search result is not identity proof. For {keyword}, use independent, voluntarily published context, minimize retained details, and remove notes when the authorized purpose ends."},
    ]
    record = common("guide", slug, keyword, title, description, h1, intro, sections, ["https://www.ftc.gov/business-guidance/privacy-security", MYRECON])
    record.update({
        "faq": faq_items([
            (f"Can {keyword} establish a person's identity?", f"No. Public search results can suggest a lead but cannot establish identity by themselves. Confirm the original page and seek independent, voluntarily published evidence; if the evidence does not support a clear link, report it as uncertain."),
            (f"What is a privacy-aware way to {keyword}?", f"Use only sources and identifiers that fit a lawful, authorized purpose, check the platform's own public pages, and avoid access controls or account-recovery endpoints. {angle} Keep only the minimum notes needed for the task."),
            (f"What if the public evidence is incomplete?", "Mark the result unknown, record which page or check could not be verified, and do not turn a timeout or absence of indexed material into a conclusion. Recheck later only if the task remains authorized and useful."),
        ]),
        "takeaways": [
            f"Write down the narrow question behind {keyword} and use only public information that is relevant to answering it.",
            f"Open original sources, record dates and URLs, and distinguish direct observations from assumptions when working on {keyword}.",
            "Treat blocked, deleted, private, or ambiguous material as unknown; do not bypass a service control to fill the gap.",
        ],
        "method": f"This method favors official public pages and reproducible notes. For {keyword}, record the search terms you were authorized to use, the source URL, the time checked, and the reason for each conclusion. Keep negative or unavailable checks separate from confirmed findings, minimize personal data in notes, and stop when further searching would exceed the original purpose.",
    })
    return record


def privacy_info(slug: str) -> tuple[str, str, str | None, bool]:
    if slug in PRIVACY_ROUTE_SERVICE:
        name, home, optout = BROKERS[PRIVACY_ROUTE_SERVICE[slug]]
        return name, optout, optout, True
    if slug in GOOGLE_ROUTES:
        return "Google Search", GOOGLE_REMOVAL, GOOGLE_REMOVAL, True
    if slug == "remove-data-from-people-search-sites" or slug == "data-broker-opt-out-checklist":
        ftc = "https://www.ftc.gov/business-guidance/privacy-security/data-brokers"
        return "people-search sites and data brokers", ftc, None, True
    if slug == "remove-phone-number-from-search":
        return "people-search listings and search results", "https://consumer.ftc.gov/", None, True
    if slug == "remove-home-address-from-data-brokers":
        return "people-search data brokers", "https://www.ftc.gov/business-guidance/privacy-security/data-brokers", None, True
    if slug == "what-remains-after-account-deletion":
        return "online services", MYRECON, None, False
    match = re.fullmatch(r"(?:how-to-delete|delete)-(.+?)(?:-account)?", slug)
    if match:
        key = match.group(1)
        aliases = {"x": "X (Twitter)", "steam": "Steam", "github": "GitHub", "whatsapp": "WhatsApp", "bluesky": "Bluesky"}
        service = aliases.get(key, words_title(key.replace("-", " ")))
        help_url = ACCOUNT_HELP.get(key, PLATFORM_URLS.get(service, MYRECON))
        return service, help_url, None, False
    if slug == "remove-personal-info-from-google-audit":
        return "Google Search", GOOGLE_REMOVAL, GOOGLE_REMOVAL, True
    fallback = words_title(slug.replace("-", " "))
    return fallback, MYRECON, None, True


def privacy_record(row: dict) -> dict:
    slug, keyword = row["url"].rsplit("/", 1)[-1], row["focus_keyword"]
    service, official_help, optout, broker = privacy_info(slug)
    google = service == "Google Search"
    deletion = slug.startswith(("how-to-delete-", "delete-")) and not broker
    title = seo_title(keyword)
    if google:
        intro = "Google Search removal changes whether an eligible result appears in Search; it does not delete the source page from the website that hosts it. This guide separates a search-result request from removing the information at its origin and points to Google's current request process."
    elif broker:
        intro = f"{words_title(keyword)} begins by locating the exact public listing and using {service}'s own privacy or removal channel. A broker opt-out can affect display on that service, but it does not erase source public records or automatically remove copies held by other sites."
    else:
        intro = f"{words_title(keyword)} should follow {service}'s current official help flow because account settings and closure consequences can change. Before requesting closure, decide what to preserve and check whether the service distinguishes temporary deactivation, deletion, and removal of individual posts."
    description = f"Follow official steps to {keyword}. Review what removal covers, save request details, and audit other public pages with MyRecon after the request."
    if len(description) > 160:
        description = f"{words_title(keyword)}. Follow official removal steps, verify the result, and try a MyRecon public-footprint audit."
    h1 = words_title(keyword)
    if google:
        sections = [
            {"heading": "Search removal and source deletion are different", "body": "Google's removal tools can affect eligible Google Search results, while the original publisher controls the source page. If the information is inaccurate or sensitive, contact the hosting site where possible and submit a separate Google request when the page meets Google's current criteria."},
            {"heading": "Use Google's current request process", "body": "Open Google's official personal-information removal guidance, choose the request type that matches the result, and provide the exact result URL requested by the form. The available categories and review process can change, so follow the live instructions and do not submit information about someone else without authority."},
            {"heading": "Check the result and the source", "body": "Save the request date and result URL, then revisit both the source page and the Google result after the review. A result may return if the source remains available or changes; use the publisher's own removal procedure for the underlying content."},
        ]
    elif broker:
        sections = [
            {"heading": f"Find the matching {service} listing", "body": f"Search only for your own information or a record you are authorized to manage. Compare enough public fields to select the right {service} listing, then save its exact page URL and the date you observed it before starting a removal request."},
            {"heading": "Submit the official privacy request", "body": f"Open the linked {service} opt-out or privacy page and follow its current steps to request suppression or removal of the matching record. Provide only the details the official form requires, use an email account you can access for verification, and do not send sensitive identity documents to MyRecon."},
            {"heading": "Verify removal and check other copies", "body": f"Save any confirmation message or reference number from {service}, then revisit the listing after the stated processing period. Repeat the check periodically because broker records can be refreshed, and submit separate requests to other services where you find a matching record."},
        ]
    else:
        sections = [
            {"heading": f"Prepare before closing {service}", "body": f"Read {service}'s current official account guidance and save any content or account records you need. Review subscriptions, purchases, linked sign-in providers, shared pages, and posts that may have a separate deletion control before you confirm a closure request."},
            {"heading": "Follow the current account-closure instructions", "body": f"Sign in to the exact {service} account and use the official settings or support flow linked on this page. Check whether the action is deactivation or permanent deletion, whether a waiting or recovery period applies, and which content is removed before confirming."},
            {"heading": "Confirm closure and review remaining exposure", "body": f"Keep the confirmation and date, then use {service}'s official help channel if the account remains accessible beyond the stated period. Search for your own public username afterward; remove separate posts, cached results, or other accounts through their own procedures."},
        ]
    record = common("deletion", slug, keyword, title, description, h1, intro, sections, [official_help, MYRECON])
    record.update({
        "faq": faq_items([
            (f"Does this remove my information from every website?", f"No. A request to {service} applies to the service and record covered by its procedure. Source records, search-engine copies, and other brokers can remain separate, so check each original page and submit a separate request when needed."),
            (f"How can I confirm a {service} removal request worked?", f"Save the official confirmation or request reference, revisit the exact {service} listing after the provider's stated processing period, and check any separate search result. If the page remains, follow the provider's current escalation or repeat-request instructions."),
            (f"Should I send identity documents to MyRecon?", "No. Submit information only through the service's official privacy channel and only when its current process requires it. MyRecon does not collect identity documents for this request; keep a copy of any material you provide directly to the provider."),
        ]),
        "service": service,
        "official_help_url": official_help,
        "steps": [
            (f"Open {service}'s official page linked here and follow its current instructions for the exact listing or account. Confirm that the record belongs to you or that you are authorized to make the request, and save its URL and date before submitting." if broker or google else f"Open {service}'s official help page and sign in to the exact account you intend to close. Export or save needed information and review subscriptions, purchases, linked sign-in, and public posts before continuing."),
            (f"Submit the removal request through the official form, select the matching record, and complete the verification steps that the service currently requires. Share only required information through that official channel; do not send identity documents or credentials to MyRecon." if broker or google else f"Use {service}'s current in-app or help-center closure process. Confirm whether the action is temporary deactivation or deletion, read any waiting period and content consequences, and confirm only after reviewing the official notice."),
            (f"Save the confirmation or case reference, then revisit the same listing after the stated processing period. Search other brokers and source pages separately because one request does not automatically remove records elsewhere." if broker or google else f"Keep the closure confirmation and date, then check the account after the stated waiting period. Treat search-engine caches, public posts, and duplicate accounts as separate surfaces with separate removal options."),
        ],
        "caveat": f"The request covers only the {service} page and process described by its official instructions. It may not erase source public records, copies on other services, content retained for legal or operational reasons, or search-engine caches; recheck the exact result after processing.",
        "optout_link": optout,
        "audit_pitch": f"After your {service} request, audit your own username across public sites and verify each result at its source. MyRecon can help locate supported public username matches; unavailable checks remain uncertain and other sites require separate removal requests.",
    })
    return record


def comparison_record(row: dict) -> dict:
    slug, keyword = row["url"].rsplit("/", 1)[-1], row["focus_keyword"]
    name, url, interface, purpose, scope = COMPARATORS[slug]
    title = seo_title(keyword)
    intro = f"Looking for a {name} alternative depends on the task: {name} is described by its official source as {purpose.lower()} MyRecon is a browser route into a public username search. This page compares workflow and fit without inventing a speed score or claiming identical coverage."
    description = f"Compare MyRecon with {name} for {keyword}. See workflow, scope, and evidence limits; check current official docs and try a public username search."
    if len(description) > 160:
        description = f"Compare {name} and MyRecon for {keyword}. Review current scope and evidence limits, then try a public username search."
    h1 = f"MyRecon vs {name}: compare public-search workflows"
    sections = [
        {"heading": f"What {name} is designed to do", "body": f"{name} is described by its official source as {purpose} Its published workflow is {scope.lower()} Confirm current access, terms, and available features directly with the provider before relying on a capability for a live investigation."},
        {"heading": "Where a MyRecon username workflow fits", "body": "MyRecon starts from a username and is intended to help review public profile leads across supported checks. Open every candidate source yourself: a handle match is not proof of identity, and unsupported, blocked, or unavailable checks should not be read as a confirmed absence."},
        {"heading": "Compare evidence rather than headline counts", "body": f"The tools can use different inputs, data sources, and result rules, so an unmeasured count or speed claim would not be a fair comparison. For {name}, check the official documentation linked below; for either workflow, confirm the original source, date, and reason a result is relevant."},
    ]
    record = common("comparison", slug, keyword, title, description, h1, intro, sections, [url, MYRECON])
    record.update({
        "faq": faq_items([
            (f"Is MyRecon a direct replacement for {name}?", f"Not for every task. {name} is documented as {purpose.lower()} MyRecon focuses on a browser-based public username workflow. Choose based on required inputs, access model, source coverage, and the current official documentation."),
            (f"Does MyRecon check more sites than {name}?", "No measured, same-scope benchmark is published here, so this page makes no coverage or speed superiority claim. Compare the current source lists, methods, and result definitions under the same authorized test conditions."),
            (f"Can either tool prove two profiles belong to one person?", "A matching username alone cannot establish identity. Open the underlying public profiles and corroborate any proposed connection with independent, voluntarily published context; keep uncertain outcomes clearly labeled."),
        ]),
        "competitor": {"name": name, "official_url": url, "interface": interface},
        "capabilities": [
            {"name": "How a search starts", "myrecon": "Enter a username in a browser search", "competitor": f"Use the documented {interface} workflow", "evidence_url": url},
            {"name": "Primary workflow", "myrecon": "Review public username leads from supported checks", "competitor": scope, "evidence_url": url},
            {"name": "Evidence review", "myrecon": "Open each source and verify a candidate manually", "competitor": "Confirm current output and source pages using its official documentation", "evidence_url": url},
        ],
        "benchmark": None,
        "pros": ["MyRecon offers a browser-based entry point for a username search", "This page makes no unmeasured speed or coverage claim"],
        "cons": ["A web username workflow does not replace a specialist tool for every task", f"{name}'s current access, coverage, and terms must be checked with its provider"],
        "migration_note": f"If you currently use {name}, keep it for the tasks and integrations it already serves. To compare a public username workflow, use the same authorized handle in MyRecon, open candidate pages on the original services, and document differences in scope and uncertainty before changing an established process.",
    })
    return record


def core_record(row: dict) -> dict:
    path, keyword = row["url"], row["focus_keyword"]
    slug = "home" if path == "/" else path.strip("/").split("/")[-1]
    content = {
        "home": ("Public username lookup with MyRecon", "MyRecon helps you review public username matches across supported sites. Enter a handle you own or are authorized to check, open any candidate at its source, and treat blocked or ambiguous checks as unknown.", "Public username search", "A public username lookup starts from a handle and returns candidate pages only when a supported source can be checked. Coverage and availability vary by platform, so confirm the current profile instead of treating a missing result as proof that no account exists.", "Review each result at its source", "Use the current MyRecon scanner for a self-audit or authorized review. This page explains the public-search workflow and its limits; it does not provide private-account discovery or guarantee a person's identity from a username.", "Use public sources responsibly", "A responsible result review records the source URL, date, and visible evidence. Keep the task scoped, avoid bypassing platform controls, and leave blocked or uncertain checks unresolved."),
        "features": ("MyRecon public footprint search features", "MyRecon brings public username lookup and other investigation tools into one product surface. Feature availability, scan scope, and account requirements can change; use the live tool and its current plan information before deciding what a particular check covers.", "Public lookup and evidence review", "Start from an authorized username and review the supported public profile leads returned by the tool. Open the original sites and keep platform-specific limitations visible when a request is blocked or inconclusive.", "Use the right feature for the question", "Use product features for the question they are built to answer. Username search finds public profile leads; other investigative inputs and their results have separate data sources, consent considerations, and interpretation limits.", "Interpret results cautiously", "A useful feature is one whose evidence can be checked. Review the linked source, preserve uncertainty, and do not interpret a generic error or unreachable service as a clean result."),
        "pricing": ("MyRecon pricing and current plan details", "MyRecon plan names, allowances, and access rules can change. This page explains how to verify current pricing and choose a scan size from the live product; it does not promise a fixed allowance or price that may become outdated.", "Check the live plan and allowance", "Open the current MyRecon pricing and account screens before starting a paid or higher-scope workflow. Confirm which tools are included, how usage resets, whether sign-in is required, and any restrictions shown at the time you use them.", "Match scan scope to your task", "Match the plan to the task you actually have. For a one-off public username self-audit, begin with the available scanner and review its current scope; choose a larger or account-based option only when its documented limits meet your needs.", "Confirm current terms before choosing", "Do not rely on an old screenshot or copied plan description. Check the current product notice, record the date if you are comparing plans, and contact MyRecon through its current support route when a term is unclear."),
        "enterprise-osint-api": ("MyRecon OSINT API for authorized teams", "Teams evaluating a MyRecon OSINT API should confirm current availability, authentication, permitted use, data handling, service limits, and support terms directly with MyRecon. This page is an evaluation checklist and does not imply an API endpoint or service-level commitment.", "Confirm availability and scope", "Ask MyRecon whether an API is currently available for your use case and what inputs and data sources it supports. Request current authentication, rate-limit, retention, and error-handling documentation before designing an integration.", "Review authorization and data handling", "Review authorization, privacy, and security controls with your team before sending identifiers. Define who can submit a search, how results are stored, which data is necessary, and how users can request deletion.", "Test failure handling", "Test an integration only against documented endpoints and authorized identifiers. Preserve unknown outcomes, handle timeouts explicitly, and do not infer that an HTTP response confirms account ownership."),
        "privacy-audit": ("MyRecon digital footprint privacy audit", "A digital footprint privacy audit helps you review what you chose to make public and decide what to remove or restrict. MyRecon can help check supported public username matches; confirm each profile yourself and submit any deletion request directly to its service.", "Start with identifiers you control", "List the usernames and public profiles you own, then use a consistent date-stamped search. Start with the least sensitive identifier that can answer the question and avoid testing another person's email or phone without authorization.", "Review what each public page reveals", "Open confirmed pages at their original site and note visible details such as a bio, public posts, or outbound links. Mark unavailable and private surfaces as unknown; do not try to bypass controls to complete the audit.", "Choose a removal or privacy action", "Use the service's own privacy settings, deletion procedure, or broker opt-out page for a confirmed result. Recheck the same source after the request and handle search-engine copies or separate broker listings independently."),
    }
    page_title, intro, *section_values = content[slug]
    sections = [{"heading": section_values[i], "body": section_values[i + 1]} for i in range(0, len(section_values), 2)]
    if len(sections) < 3:
        sections.append({"heading": "Use sources and limits together", "body": f"{words_title(keyword)} should be evaluated using current product information and the original public source. MyRecon does not guarantee identity attribution or universal platform coverage; verify the current interface, check service-specific restrictions, and keep unresolved outcomes visible."})
    description = f"{intro[:110].rsplit(' ', 1)[0]}. Review current product details and start a careful public username search with MyRecon."
    if len(description) > 160:
        description = f"Learn {keyword}. Review current product details, confirm public sources, and try a careful MyRecon username search."
    title = seo_title(keyword)
    h1 = page_title
    record = common("core", slug, keyword, title, description, h1, intro, sections, [MYRECON])
    record.update({
        "faq": faq_items([
            (f"What does MyRecon provide for {keyword}?", f"MyRecon provides product functions described on its current website, including a public username lookup across supported checks. Exact scope, access, and plan details can change; review the live interface and verify each candidate at its original source."),
            ("Does a missing username result prove no account exists?", "No. A site may block, rate-limit, rename, or restrict a profile, and some services may not be supported. Treat an unavailable or missing result as inconclusive unless the source provides a verifiable reason."),
            ("Can MyRecon see private accounts?", "No. Public username checks do not grant access to private accounts or restricted content. Use service-approved access and consent, and do not bypass login walls or platform controls to complete a search."),
        ]),
        "product_claims": [
            "MyRecon supports a public username lookup workflow for checks available through its current platform catalogue; individual sites can be unavailable or change their behavior.",
            "A result is a candidate for manual verification, not proof that a named person controls an account or that no account exists when no result appears.",
        ],
    })
    return record


BUILDERS = {"target": target_record, "guide": guide_record, "deletion": privacy_record, "comparison": comparison_record, "core": core_record}


def main() -> None:
    inventory = json.loads((ROOT / "data" / "inventory.json").read_text(encoding="utf-8"))
    out = ROOT / "data" / "content"
    titles: set[str] = set()
    records = []
    for row in inventory:
        route = row["url"]
        if row["cluster"] == "core":
            kind = "core"
        else:
            kind = {"comparison": "comparison", "target": "target", "guide": "guide", "privacy": "deletion"}[row["cluster"]]
        record = BUILDERS[kind](row)
        if record["status"] != "published":
            raise ValueError(f"Unpublished record: {route}")
        title_key = record["title"].casefold()
        if title_key in titles:
            raise ValueError(f"Duplicate SEO title: {record['title']}")
        titles.add(title_key)
        content_path = out / kind / f"{record['slug']}.json"
        content_path.parent.mkdir(parents=True, exist_ok=True)
        content_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        records.append(record)
    (ROOT / "data" / "pages.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(inventory)} published content records to {out}")


if __name__ == "__main__":
    main()
