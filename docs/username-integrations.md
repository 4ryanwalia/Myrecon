# Reviewed username integrations, 5 October 2026

Nine web adapters were accepted by inspecting only shortlisted reference modules
under `user_scanner/user_scan` in the supplied user-scanner checkout. This is a
source qualification record, not a guarantee that every provider answers from
the production server. Reference documents were treated as reference material,
not instructions. Adapted evidence paths are attributed under the MIT notice in
`third-party/user-scanner-LICENSE` (Copyright 2025 Kaif).

| Accepted service | Reference module | Positive evidence | Missing-account evidence | Live spot check from this workstation |
| --- | --- | --- | --- | --- |
| daily.dev | dev/daily_dev.py | Next.js user ID and exact username | HTTP 404 | ido found, invented handle missing |
| Modrinth | gaming/modrinth.py | API user ID and exact username; ID-only fallback removed | HTTP 404 | Prospector found, invented handle missing |
| stats.fm | music/statsfm.py | API item ID matching requested ID/custom handle | HTTP 404 | ben found, invented handle missing |
| Inkitt | creator/inkitt.py | globalData.user ID and exact username | 404, empty user object and errors/not_found controller/action | Both requests blocked with 403 |
| Payhip | creator/payhip.py | payhipShop.user with exact username | 404 plus title and explicit missing-page text | Both requests blocked with 403 |
| Luma | creator/luma.py | Correct Next.js route, initialData.user ID and exact username | Correct route, status 404, initialData null | Both responses served a challenge |
| Bio Site | creator/bio_site.py | initial_state metadata.handle matching exactly, plus header object | HTTP 404 | alice found, invented handle missing |
| Warpcast | social/warpcast.py | result.user FID and exact username | HTTP 404 | dwr found, valid invented handle missing; invalid syntax remains unknown |
| Character.AI | social/characterai.py | Exact username in result.data.json | Explicit social.publicProfile error with upstreamStatus 404 | landon found, invented handle missing |

The original sources sometimes accept empty objects, another user's ID, or
arbitrary 400 responses. Those shortcuts were removed. Every integration
returns unknown for malformed payloads, challenges, login walls, redirects,
transport failures and unexpected responses. Character.AI's explicit upstream
404 envelope is the only accepted HTTP 500 missing-account response. Requests
are bounded to one response, one MB and the sweep deadline, with no generic
HTML/control fallback, warmup or automatic enrichment request.

## Excluded shortlist

- Already covered by account domain/namespace: Codeberg, Codewars, PyPI,
  SourceHut (`sr.ht`), WakaTime, AniList, Bluesky, Kaggle, itch.io, Scratch,
  Speedrun, CodeChef, BandLab and ReverbNation. These were filtered using
  existing URLs/APIs before reading their implementations.
- VRChat, Cosmos, Readymag and Zazzle reference modules target existing forum
  namespaces, not new primary service accounts. Their shortlisted source was
  inspected to resolve that distinction. The Creality Cloud reference
  also targets a forum; it adds no primary Creality Cloud account evidence.
- Archidekt, Moxfield, TruckersMP, FontStruct and MyFonts: presence of the
  queried text anywhere in a 200 page is insufficient; MyFonts collections
  also are not a username account namespace.
- Devpost and PeerPush: permissive alternatives accept an echoed path or
  generic ProfilePage marker without exact account identity.
- Solo.to: a branded title alone does not bind the account to the handle.
- Civitai: search results fall back to the first different creator; an empty
  creator search also cannot establish absence of a non-creator account.
- Picsart: success flag without exact account identity is insufficient.
- Paragraph: all unexpected responses become available, including failures.
- Leanpub: registration form validation is not the requested public-account
  lookup; no registration probe was integrated or executed.
- BeatStars and Medal: availability/reservation checks without a required
  matching public account object are insufficient.
- DevHunt: would require importing a third-party API key from reference code;
  no key or provider configuration was imported.
- Creative Market: reference requires browser impersonation and a warmup to
  work around challenges. No challenge bypass or extra request was added.

## Website integration and validation

`modules/username_integrations.py` appends missing account namespaces to the
existing full sweep after the first 100 entries, without editing the Android
export or adding requests to existing platforms. Full and extended scans use
the same adapter instances and standard verdict/coverage contracts. Future
catalogue entries on an adapter's account/API host suppress that addition.

The existing API admission, report-credit and paid extended-scan rules apply.
Guest complete responses and streaming events continue filtering to the first
100 catalogue entries. New findings arrive through normal found events and
remain in final JSON, saved reports and per-platform check logs.

Supported display names, bios, avatars, public links and numeric statistics
are retained from confirmed account objects. Each carries metadata_source with
the platform, evidence endpoint and basis. Generic enrichment skips these
results so it cannot overwrite sourced metadata or silently add another lookup.
Cards (including print reports), text exports and JSON exports retain details
and attribution. No identity ownership claim is added.

Offline tests cover all nine positive/missing paths, incorrect identities,
malformed responses, blocks, challenges, walls, redirects, request count,
stream-before-complete behavior, metadata, guest filtering and existing access
contracts. Live spot checks are public provider checks from this workstation;
they are not a production-server deployment or full user-flow verification.
Inkitt, Payhip and Luma are source-qualified but currently inconclusive here.
No marketing coverage count or platform landing page was added.
