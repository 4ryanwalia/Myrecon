"""
╔══════════════════════════════════════════════════════════════╗
║  OSINT DORK DATABASE — 300+ Structured Google Dork Queries  ║
║  Dynamic replacement of {username} and {email} at runtime   ║
╚══════════════════════════════════════════════════════════════╝
"""


# ──────────────────────────────────────────────────────────────
#  USERNAME-BASED DORKS
# ──────────────────────────────────────────────────────────────

USERNAME_DORKS: list[str] = [
    # ── Social Media ──────────────────────────────────────────
    'site:twitter.com "{username}"',
    'site:x.com "{username}"',
    'site:instagram.com "{username}"',
    'site:facebook.com "{username}"',
    'site:tiktok.com "@{username}"',
    'site:snapchat.com "{username}"',
    'site:tumblr.com "{username}"',
    'site:pinterest.com "{username}"',
    'site:flickr.com "{username}"',
    'site:vk.com "{username}"',
    'site:mastodon.social "{username}"',
    'site:threads.net "{username}"',
    'site:bluesky.social "{username}"',
    'site:weibo.com "{username}"',
    'site:ok.ru "{username}"',
    'site:myspace.com "{username}"',
    'site:tagged.com "{username}"',
    'site:minds.com "{username}"',
    'site:gab.com "{username}"',
    'site:parler.com "{username}"',
    'site:truthsocial.com "{username}"',
    'site:gettr.com "{username}"',

    # ── Professional / Career ─────────────────────────────────
    'site:linkedin.com/in "{username}"',
    'site:linkedin.com "{username}"',
    'site:about.me "{username}"',
    'site:angel.co "{username}"',
    'site:crunchbase.com "{username}"',
    'site:glassdoor.com "{username}"',
    'site:indeed.com "{username}"',
    'site:behance.net "{username}"',
    'site:dribbble.com "{username}"',
    'site:carbonmade.com "{username}"',
    'site:portfoliobox.net "{username}"',
    'site:hired.com "{username}"',
    'site:wellfound.com "{username}"',
    'site:xing.com "{username}"',
    'site:upwork.com "{username}"',
    'site:fiverr.com "{username}"',
    'site:freelancer.com "{username}"',
    'site:toptal.com "{username}"',

    # ── Developer / Code ──────────────────────────────────────
    'site:github.com "{username}"',
    'site:gitlab.com "{username}"',
    'site:bitbucket.org "{username}"',
    'site:codepen.io "{username}"',
    'site:replit.com "{username}"',
    'site:stackoverflow.com "{username}"',
    'site:stackexchange.com "{username}"',
    'site:dev.to "{username}"',
    'site:medium.com "@{username}"',
    'site:hashnode.com "{username}"',
    'site:hackerrank.com "{username}"',
    'site:leetcode.com "{username}"',
    'site:codeforces.com "{username}"',
    'site:kaggle.com "{username}"',
    'site:npmjs.com "{username}"',
    'site:pypi.org "{username}"',
    'site:rubygems.org "{username}"',
    'site:hub.docker.com "{username}"',
    'site:codewars.com "{username}"',
    'site:exercism.org "{username}"',
    'site:topcoder.com "{username}"',
    'site:codesandbox.io "{username}"',
    'site:jsfiddle.net "{username}"',
    'site:glitch.com "{username}"',
    'site:sourceforge.net "{username}"',
    'site:launchpad.net "{username}"',
    'site:coderwall.com "{username}"',
    'site:codeberg.org "{username}"',
    'site:gitea.com "{username}"',
    'site:huggingface.co "{username}"',
    'site:wandb.ai "{username}"',

    # ── Forums / Communities ──────────────────────────────────
    'site:reddit.com/user "{username}"',
    'site:reddit.com "{username}"',
    'site:quora.com "{username}"',
    'site:news.ycombinator.com "{username}"',
    'site:disqus.com "{username}"',
    'site:discourse.org "{username}"',
    'site:hackforums.net "{username}"',
    'site:4chan.org "{username}"',
    'site:kiwifarms.net "{username}"',
    'site:resetera.com "{username}"',
    'site:neogaf.com "{username}"',
    'site:producthunt.com "{username}"',
    'site:lobste.rs "{username}"',
    'site:slashdot.org "{username}"',
    'site:arstechnica.com "{username}"',
    'site:xda-developers.com "{username}"',
    'site:spiceworks.com "{username}"',
    'site:f-droid.org "{username}"',

    # ── Media / Content ───────────────────────────────────────
    'site:youtube.com "{username}"',
    'site:twitch.tv "{username}"',
    'site:vimeo.com "{username}"',
    'site:soundcloud.com "{username}"',
    'site:spotify.com "{username}"',
    'site:bandcamp.com "{username}"',
    'site:mixcloud.com "{username}"',
    'site:dailymotion.com "{username}"',
    'site:rumble.com "{username}"',
    'site:odysee.com "{username}"',
    'site:kick.com "{username}"',
    'site:bitchute.com "{username}"',
    'site:anchor.fm "{username}"',
    'site:podcasts.apple.com "{username}"',
    'site:last.fm "{username}"',
    'site:genius.com "{username}"',

    # ── Gaming ────────────────────────────────────────────────
    'site:steamcommunity.com "{username}"',
    'site:xbox.com "{username}"',
    'site:playstation.com "{username}"',
    'site:epicgames.com "{username}"',
    'site:chess.com "{username}"',
    'site:lichess.org "{username}"',
    'site:roblox.com "{username}"',
    'site:minecraft.net "{username}"',
    'site:osu.ppy.sh "{username}"',
    'site:tracker.gg "{username}"',
    'site:namemc.com "{username}"',
    'site:valorant.gg "{username}"',
    'site:op.gg "{username}"',
    'site:dotabuff.com "{username}"',
    'site:faceit.com "{username}"',
    'site:esea.net "{username}"',
    'site:mobalytics.gg "{username}"',
    'site:itch.io "{username}"',

    # ── Messaging / Chat ──────────────────────────────────────
    'site:t.me "{username}"',
    'site:telegram.me "{username}"',
    'site:discord.com "{username}"',
    'site:keybase.io "{username}"',
    'site:signal.org "{username}"',
    'site:slack.com "{username}"',
    'site:matrix.to "{username}"',
    'site:element.io "{username}"',

    # ── Dating ────────────────────────────────────────────────
    'site:tinder.com "{username}"',
    'site:okcupid.com "{username}"',
    'site:pof.com "{username}"',
    'site:match.com "{username}"',
    'site:bumble.com "{username}"',
    'site:hinge.co "{username}"',

    # ── Shopping / Commerce ───────────────────────────────────
    'site:ebay.com "{username}"',
    'site:etsy.com "{username}"',
    'site:amazon.com "{username}"',
    'site:poshmark.com "{username}"',
    'site:depop.com "{username}"',
    'site:mercari.com "{username}"',
    'site:grailed.com "{username}"',
    'site:vinted.com "{username}"',
    'site:redbubble.com "{username}"',
    'site:society6.com "{username}"',
    'site:teepublic.com "{username}"',

    # ── Blogging / Publishing ─────────────────────────────────
    'site:wordpress.com "{username}"',
    'site:blogger.com "{username}"',
    'site:substack.com "{username}"',
    'site:wattpad.com "{username}"',
    'site:livejournal.com "{username}"',
    'site:medium.com "{username}"',
    'site:ghost.io "{username}"',
    'site:notion.so "{username}"',
    'site:bearblog.dev "{username}"',
    'site:mirror.xyz "{username}"',

    # ── Photo / Image / Art ───────────────────────────────────
    'site:500px.com "{username}"',
    'site:unsplash.com "{username}"',
    'site:deviantart.com "{username}"',
    'site:artstation.com "{username}"',
    'site:pixiv.net "{username}"',
    'site:imgur.com "{username}"',
    'site:vsco.co "{username}"',
    'site:giphy.com "{username}"',
    'site:pexels.com "{username}"',
    'site:newgrounds.com "{username}"',
    'site:furaffinity.net "{username}"',

    # ── Academic / Research ───────────────────────────────────
    'site:scholar.google.com "{username}"',
    'site:researchgate.net "{username}"',
    'site:academia.edu "{username}"',
    'site:orcid.org "{username}"',
    'site:arxiv.org "{username}"',
    'site:ieee.org "{username}"',
    'site:semantic-scholar.org "{username}"',
    'site:pubmed.ncbi.nlm.nih.gov "{username}"',

    # ── Finance / Crypto ──────────────────────────────────────
    'site:tradingview.com "{username}"',
    'site:coinmarketcap.com "{username}"',
    'site:opensea.io "{username}"',
    'site:etherscan.io "{username}"',
    'site:debank.com "{username}"',

    # ── Funding / Support ─────────────────────────────────────
    'site:buymeacoffee.com "{username}"',
    'site:ko-fi.com "{username}"',
    'site:patreon.com "{username}"',
    'site:gumroad.com "{username}"',
    'site:gofundme.com "{username}"',
    'site:kickstarter.com "{username}"',
    'site:indiegogo.com "{username}"',

    # ── Link-in-bio / Portfolio ───────────────────────────────
    'site:linktr.ee "{username}"',
    'site:carrd.co "{username}"',
    'site:bio.link "{username}"',
    'site:beacons.ai "{username}"',
    'site:about.me "{username}"',
    'site:calendly.com "{username}"',

    # ── Misc Platforms ────────────────────────────────────────
    'site:gravatar.com "{username}"',
    'site:trello.com "{username}"',
    'site:slideshare.net "{username}"',
    'site:scribd.com "{username}"',
    'site:issuu.com "{username}"',
    'site:instructables.com "{username}"',
    'site:hackaday.io "{username}"',
    'site:goodreads.com "{username}"',
    'site:myanimelist.net "{username}"',
    'site:letterboxd.com "{username}"',
    'site:trakt.tv "{username}"',
    'site:duolingo.com "{username}"',
    'site:codecademy.com "{username}"',
    'site:freecodecamp.org "{username}"',
    'site:hackerone.com "{username}"',
    'site:bugcrowd.com "{username}"',
    'site:wikipedia.org "{username}"',
    'site:fandom.com "{username}"',
    'site:ravelry.com "{username}"',
    'site:thingiverse.com "{username}"',
    'site:printables.com "{username}"',
    'site:grabcad.com "{username}"',

    # ── Security / Hacking ────────────────────────────────────
    'site:exploit-db.com "{username}"',
    'site:vulnhub.com "{username}"',
    'site:tryhackme.com "{username}"',
    'site:hackthebox.com "{username}"',
    'site:ctftime.org "{username}"',

    # ── Generic Profile Discovery ─────────────────────────────
    '"{username}" "profile"',
    '"{username}" "contact"',
    '"{username}" "bio"',
    '"{username}" "about me"',
    '"{username}" "portfolio"',
    '"{username}" "resume" OR "cv"',
    '"{username}" "my account"',
    '"{username}" inurl:profile',
    '"{username}" inurl:user',
    '"{username}" inurl:member',
    '"{username}" inurl:author',
    '"{username}" intitle:profile',
    '"{username}" "social media"',
    '"{username}" "find me on"',
    '"{username}" "follow me"',
    '"{username}" "connect with"',

    # ── Paste / Leak Discovery ────────────────────────────────
    'site:pastebin.com "{username}"',
    'site:ghostbin.com "{username}"',
    'site:justpaste.it "{username}"',
    'site:hastebin.com "{username}"',
    'site:paste.ee "{username}"',
    'site:controlc.com "{username}"',
    'site:dpaste.org "{username}"',
    'site:rentry.co "{username}"',
    'site:privatebin.net "{username}"',
    'site:paste.mozilla.org "{username}"',
]


# ──────────────────────────────────────────────────────────────
#  EMAIL-BASED DORKS
# ──────────────────────────────────────────────────────────────

EMAIL_DORKS: list[str] = [
    # ── Direct email search ───────────────────────────────────
    '"{email}"',
    '"{email}" "profile"',
    '"{email}" "contact"',
    '"{email}" "resume"',
    '"{email}" "cv"',
    '"{email}" "about"',
    '"{email}" "portfolio"',
    '"{email}" "bio"',
    '"{email}" "registered"',
    '"{email}" "sign up"',
    '"{email}" "account"',
    '"{email}" "member"',
    '"{email}" "author"',
    '"{email}" "posted by"',
    '"{email}" "submitted by"',
    '"{email}" "contributed by"',
    '"{email}" "linked"',
    '"{email}" "verified"',
    '"{email}" "subscribed"',
    '"{email}" "unsubscribe"',
    '"{email}" "notification"',
    '"{email}" "welcome"',
    '"{email}" "confirmation"',
    '"{email}" "receipt"',

    # ── Document discovery (email) ────────────────────────────
    '"{email}" filetype:pdf',
    '"{email}" filetype:doc',
    '"{email}" filetype:docx',
    '"{email}" filetype:xls',
    '"{email}" filetype:xlsx',
    '"{email}" filetype:ppt',
    '"{email}" filetype:pptx',
    '"{email}" filetype:csv',
    '"{email}" filetype:txt',
    '"{email}" filetype:rtf',
    '"{email}" filetype:odt',
    '"{email}" filetype:xml',
    '"{email}" filetype:json',
    '"{email}" filetype:log',
    '"{email}" filetype:sql',
    '"{email}" filetype:env',
    '"{email}" filetype:conf',
    '"{email}" filetype:cfg',
    '"{email}" filetype:ini',
    '"{email}" filetype:yaml',
    '"{email}" filetype:yml',
    '"{email}" filetype:bak',

    # ── Site-specific email search ────────────────────────────
    'site:linkedin.com "{email}"',
    'site:facebook.com "{email}"',
    'site:twitter.com "{email}"',
    'site:github.com "{email}"',
    'site:gitlab.com "{email}"',
    'site:stackoverflow.com "{email}"',
    'site:reddit.com "{email}"',
    'site:quora.com "{email}"',
    'site:medium.com "{email}"',
    'site:pastebin.com "{email}"',
    'site:scribd.com "{email}"',
    'site:slideshare.net "{email}"',
    'site:issuu.com "{email}"',
    'site:academia.edu "{email}"',
    'site:researchgate.net "{email}"',
    'site:gravatar.com "{email}"',
    'site:keybase.io "{email}"',
    'site:about.me "{email}"',
    'site:crunchbase.com "{email}"',
    'site:angel.co "{email}"',
    'site:xing.com "{email}"',
    'site:zoom.us "{email}"',
    'site:kaggle.com "{email}"',
    'site:instructables.com "{email}"',
    'site:hackaday.io "{email}"',
    'site:buymeacoffee.com "{email}"',
    'site:ko-fi.com "{email}"',
    'site:pinterest.com "{email}"',
    'site:flickr.com "{email}"',
    'site:npmjs.com "{email}"',
    'site:pypi.org "{email}"',
    'site:wordpress.org "{email}"',
    'site:drupal.org "{email}"',
    'site:opensea.io "{email}"',

    # ── Leak / Exposure ───────────────────────────────────────
    '"{email}" "password"',
    '"{email}" "leak"',
    '"{email}" "breach"',
    '"{email}" "dump"',
    '"{email}" "database"',
    '"{email}" "exposed"',
    '"{email}" "compromised"',
    '"{email}" "hacked"',
    '"{email}" "credential"',
    'site:pastebin.com "{email}"',
    'site:justpaste.it "{email}"',
    'site:ghostbin.com "{email}"',
    'site:rentry.co "{email}"',
    'site:paste.ee "{email}"',
]


# ──────────────────────────────────────────────────────────────
#  DOCUMENT DISCOVERY DORKS (username-based)
# ──────────────────────────────────────────────────────────────

DOCUMENT_DORKS: list[str] = [
    '"{username}" filetype:pdf',
    '"{username}" filetype:doc',
    '"{username}" filetype:docx',
    '"{username}" filetype:xls',
    '"{username}" filetype:xlsx',
    '"{username}" filetype:ppt',
    '"{username}" filetype:pptx',
    '"{username}" filetype:csv',
    '"{username}" filetype:txt',
    '"{username}" filetype:rtf',
    '"{username}" filetype:odt',
    '"{username}" filetype:key',
    '"{username}" filetype:sql',
    '"{username}" filetype:log',
    '"{username}" filetype:bak',
    '"{username}" filetype:xml',
    '"{username}" filetype:json',
    '"{username}" filetype:yml',
    '"{username}" filetype:yaml',
    '"{username}" filetype:env',
    '"{username}" filetype:conf',
    '"{username}" filetype:cfg',
    '"{username}" filetype:ini',
]


def get_username_dorks(username: str) -> list[str]:
    """Generate all username-based dork queries with deduplication."""
    all_dorks = USERNAME_DORKS + DOCUMENT_DORKS
    populated = []
    seen = set()
    for dork in all_dorks:
        query = dork.replace("{username}", username)
        if query not in seen:
            seen.add(query)
            populated.append(query)
    return populated


def get_email_dorks(email: str) -> list[str]:
    """Generate all email-based dork queries with deduplication."""
    populated = []
    seen = set()
    for dork in EMAIL_DORKS:
        query = dork.replace("{email}", email)
        if query not in seen:
            seen.add(query)
            populated.append(query)
    return populated


def get_all_dorks(username: str = "", email: str = "") -> list[str]:
    """Get all applicable dork queries based on provided inputs."""
    dorks = []
    if username:
        dorks.extend(get_username_dorks(username))
    if email:
        dorks.extend(get_email_dorks(email))
    seen = set()
    unique = []
    for d in dorks:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return unique


# ── Metadata ──────────────────────────────────────────────────
TOTAL_USERNAME_DORKS = len(USERNAME_DORKS) + len(DOCUMENT_DORKS)
TOTAL_EMAIL_DORKS = len(EMAIL_DORKS)
TOTAL_DORKS = TOTAL_USERNAME_DORKS + TOTAL_EMAIL_DORKS
