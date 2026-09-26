"""Create the 206-route inventory used by the MyRecon SEO kit."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
core = [
    ("/", "OSINT social media lookup"),
    ("/features", "digital footprint discovery features"),
    ("/pricing", "OSINT lookup pricing"),
    ("/enterprise-osint-api", "legal OSINT API for teams"),
    ("/privacy-audit", "digital footprint privacy audit"),
]

comparisons = """sherlock social-searcher namechk maigret usersearch whatsmyname knowem spiderfoot osint-industries social-catfish spokeo pipl epieos osint-combine seon blackbird userrecon osint-framework recon-ng phoneinfoga namecheckup maltego lampyre usernamecheck ghunt""".split()
targets = """instagram-account tiktok-profile x-twitter-account reddit-activity telegram-username youtube-channel facebook-profile linkedin-profile snapchat-username pinterest-profile discord-username twitch-channel github-profile spotify-profile steam-profile threads-account bluesky-profile mastodon-account tumblr-blog medium-author quora-profile vimeo-profile dailymotion-channel behance-portfolio dribbble-profile deviantart-profile figma-profile soundcloud-profile substack-publication patreon-profile fiverr-profile upwork-profile goodreads-profile letterboxd-profile lastfm-profile roblox-profile epic-games-profile xbox-gamertag playstation-network-profile hacker-news-profile stack-overflow-profile keybase-profile kaggle-profile gravatar-profile venmo-profile cash-app-profile etsy-shop ebay-seller amazon-author-profile flickr-profile 500px-profile strava-profile duolingo-profile wattpad-profile airbnb-profile roblox-user pinterest-board vimeo-user discord-user kick-streamer duo-profile patreon-creator telegram-channel minecraft-player itchio-developer bandcamp-artist deezer-artist researchgate-author orcid-researcher gumroad-creator ko-fi-creator unsplash-photographer producthunt-maker opensea-creator peerlist-profile lemmy-user artstation-portfolio devto-author thingiverse-maker medium-publication""".split()
guides = """how-to-find-hidden-social-media-accounts reverse-email-lookup-techniques reverse-username-search-workflow digital-footprint-audit-checklist cross-platform-entity-resolution verify-osint-account-matches username-reuse-privacy-risks find-old-online-accounts identify-impersonation-accounts public-profile-evidence-logging search-operators-for-social-profiles account-enumeration-false-positives handle-variations-and-aliases investigate-public-github-exposure discover-public-forum-activity link-social-profiles-without-overclaiming osint-investigation-workflow privacy-audit-for-families brand-impersonation-monitoring breach-exposure-vs-public-profiles protect-researcher-notes responsible-public-data-collection account-discovery-without-scraping triage-uncertain-identity-matches build-a-repeatable-footprint-audit how-to-find-someone-on-all-social-media find-hidden-dating-profiles-by-email reverse-lookup-phone-number-free-osint how-to-find-an-exs-secret-account trace-anonymous-telegram-username find-linked-email-addresses-from-username find-social-profiles-by-full-name find-public-profiles-by-phone-number find-business-social-media-profiles find-creator-profiles-by-username search-usernames-across-social-platforms use-reverse-image-search-for-profiles verify-social-media-profile-ownership distinguish-same-name-social-accounts document-public-web-findings track-public-username-changes username-search-vs-email-search reduce-public-social-media-footprint audit-social-media-before-job-search protect-family-public-profile-exposure preserve-osint-evidence-chain passive-osint-vs-active-collection validate-a-user-search-result how-to-audit-username-reuse""".split()
privacy = """how-to-delete-instagram-account how-to-delete-tiktok-account how-to-delete-facebook-account how-to-delete-reddit-account how-to-delete-x-account how-to-delete-snapchat-account how-to-delete-linkedin-account how-to-delete-discord-account how-to-delete-telegram-account how-to-delete-pinterest-account how-to-delete-twitch-account how-to-delete-steam-account how-to-delete-roblox-account how-to-delete-spotify-account how-to-delete-github-account how-to-delete-quora-account how-to-delete-tumblr-account how-to-delete-medium-account how-to-delete-whatsapp-account remove-data-from-people-search-sites opt-out-of-spokeo opt-out-of-whitepages opt-out-of-beenverified remove-personal-info-from-google-audit what-remains-after-account-deletion delete-whitepages-info opt-out-spokeo remove-beenverified-record delete-fastpeoplesearch remove-intelius-profile opt-out-radaris delete-nuwber-record remove-from-truepeoplesearch opt-out-familytreenow opt-out-truthfinder opt-out-instant-checkmate remove-from-peoplefinders remove-from-peekyou opt-out-peoplewhiz opt-out-socialcatfish request-google-search-removal remove-phone-number-from-search remove-home-address-from-data-brokers data-broker-opt-out-checklist delete-substack-account delete-bluesky-account delete-mastodon-account""".split()

focus_overrides = {
    "roblox-user": "find a Roblox user by username",
    "pinterest-board": "find a Pinterest board by username",
    "vimeo-user": "find a Vimeo user by username",
    "discord-user": "find a public Discord username profile",
    "kick-streamer": "find a Kick streamer by username",
    "duo-profile": "Duo profile username lookup limits",
    "patreon-creator": "find a Patreon creator by username",
    "medium-publication": "find a Medium publication by username",
    "ghunt": "GHunt alternative for authorized OSINT research",
    "delete-whitepages-info": "delete personal information from Whitepages",
    "opt-out-spokeo": "Spokeo opt-out and record removal",
    "remove-beenverified-record": "remove a BeenVerified record",
    "delete-fastpeoplesearch": "delete a FastPeopleSearch listing",
    "remove-intelius-profile": "remove an Intelius profile",
    "opt-out-radaris": "Radaris opt-out and profile removal",
    "delete-nuwber-record": "delete a Nuwber record",
    "how-to-find-someone-on-all-social-media": "how to find someone across public social media",
    "find-hidden-dating-profiles-by-email": "privacy-safe dating profile search by email",
    "reverse-lookup-phone-number-free-osint": "free reverse phone lookup OSINT methods",
    "how-to-find-an-exs-secret-account": "ethical public account search after a breakup",
    "trace-anonymous-telegram-username": "trace public clues from a Telegram username",
    "find-linked-email-addresses-from-username": "find publicly linked email addresses from a username",
    "opt-out-of-spokeo": "opt out of Spokeo people search",
}

rows = []
for url, keyword in core:
    rows.append({"cluster": "core", "url": url, "focus_keyword": keyword, "intent": "product", "status": "published"})
for slug in comparisons:
    rows.append({"cluster": "comparison", "url": f"/vs/{slug}", "focus_keyword": focus_overrides.get(slug, f"{slug.replace('-', ' ')} alternative"), "intent": "commercial", "status": "published"})
for slug in targets:
    default_keyword = f"{slug.replace('-', ' ')} username lookup"
    rows.append({"cluster": "target", "url": f"/find/{slug}", "focus_keyword": focus_overrides.get(slug, default_keyword), "intent": "tool", "status": "published"})
for slug in guides:
    rows.append({"cluster": "guide", "url": f"/guides/{slug}", "focus_keyword": focus_overrides.get(slug, slug.replace('-', ' ')), "intent": "informational", "status": "published"})
for slug in privacy:
    rows.append({"cluster": "privacy", "url": f"/privacy/{slug}", "focus_keyword": focus_overrides.get(slug, slug.replace('-', ' ')), "intent": "removal", "status": "published"})

assert len(rows) == 206, f"Expected 206 routes, got {len(rows)}"
assert len({row["url"] for row in rows}) == len(rows), "Duplicate route"
(root / "data" / "inventory.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {len(rows)} published routes")
