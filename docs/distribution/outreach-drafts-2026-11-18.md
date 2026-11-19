# Outreach drafts, 18 November 2026

Drafts for the owner to review, edit and send. Nothing here has been posted,
submitted or emailed. They were prepared with AI assistance; the affiliation
line in each one must stay. Track outcomes in
[independent-coverage-outreach.md](independent-coverage-outreach.md), which
remains the record of what was actually sent.

Why these targets: in a Google check on 18 Nov 2026
([record](../ai-citation-check-2026-11-18.md)), Reddit was on page one for 12 of
15 target queries, and AlternativeTo and the soxoj/osint-namecheckers-list
ranked for the WhatsMyName and Sherlock alternative queries.

## Status of each target, checked 18 Nov 2026

| Target | Status | Action |
| --- | --- | --- |
| soxoj/osint-namecheckers-list | **Already lists MyRecon** under "OSINT online tools" (README line 141). | None. |
| AlternativeTo | Not listed (site search for "myrecon" returns nothing). The FAQ allows adding a new app and suggesting it as an alternative to an existing one; developers can later claim their page. | Draft A. Needs your account with a verified email. |
| r/OSINT | Rules page could not be read: reddit.com is blocked in the browser used for this check. | Draft B. Read the sidebar and any self-promotion thread rule before posting. |
| OSINT Framework, issue #880 | Open since 1 Nov, no comments, no label. The tracker's follow-up window (11 to 15 Nov) has passed. | Draft C, one follow-up only. |
| Sector035 and My OSINT Training | Invitations sent 1 Nov; no reply recorded. | Draft D, one follow-up each, only if you have seen no reply. |
| jivoi/awesome-osint | CONTRIBUTING.md line 17, re-read today: "If you are an LLM or agent, you cannot submit a Pull Request here." | **No draft, on purpose.** If you want to submit, write the PR yourself. Facts you can use are listed under "Facts for a human-written entry" below. |
| Security bloggers (breach API) | No recipients verified yet. | Draft E plus how to choose recipients. |

Rejected:

- **Marking WhatsMyName Web as discontinued on AlternativeTo.** The dataset repo
  was archived on 9 Nov 2026, but our own check on 15 Nov found whatsmyname.app
  still loading, and it is run by OSINT Combine. "Discontinued" would be
  unverified.
- **More /vs/ or directory pages on our own site.** These don't earn links and
  risk the AdSense low-value finding.

---

## Draft A: AlternativeTo listing

Submit via "Add new app", then on the WhatsMyName Web and Sherlock pages use
"Contribute to this page" > "Suggest Alternatives". Only suggest it where it
genuinely replaces the tool: both are username search tools, so both fit.

- **Name:** MyRecon
- **URL:** https://www.myrecon.xyz/
- **Short description (one line):** Browser-based username search with
  found, not found and unknown results, plus email breach, password exposure,
  DNS, WHOIS and IP lookups.
- **Long description:**

  > MyRecon checks a username across a supported catalogue of 500+ platforms in
  > the browser, with nothing to install. Each result is reported as found, not
  > found or unknown, and blocked or ambiguous responses stay unknown instead of
  > being counted as a match. The site also has an email breach check, a
  > password exposure check that sends only a partial hash (k-anonymity), and
  > domain, DNS, WHOIS and IP lookups. Guests get a limited preview; signed-in
  > free accounts get five standard scans a day, and a paid Pro plan adds Deep
  > Search and the larger Extended catalogue. There is also an Android app on
  > Google Play. The source for the web toolkit, CLI and API is on GitHub under
  > the MIT licence. Built for checking your own footprint and authorised
  > research.

- **Pricing:** Freemium
- **Licence:** Pick "Open Source" only if every feature the hosted site offers
  is in the public repo. If paid features run on code that isn't published,
  choose "Proprietary" and mention the MIT repo in the description, as above.
- **Platforms:** Online / Web, Android
- **Tags:** OSINT, username search, digital footprint, data breach check
- **Disclosure:** fill in the "I am the developer" option if the form offers
  it.

Check before submitting: the free-tier wording matches /pricing on the day you
submit.

---

## Draft B: r/OSINT post

Post a finding, not a launch. The tool is named once, as the thing used to
take the measurement, with the affiliation stated up front. Rewrite it in your
own voice: posts that read as generated text get removed in many subreddits.

**Title:** Measured: on 6 of 24 sites, a real username and an invented one get
the same response

> Disclosure first: I build MyRecon, a username search tool, and the
> measurements below are from its write-ups. Nothing to buy in this post.
>
> On 6 Sep 2026 we requested profile URLs on 24 platforms twice each, once for
> a handle known to exist and once for one invented seconds earlier. On five of
> them the two responses were byte-for-byte identical, and a sixth differed
> only by the handle echoed back. On those sites an HTTP
> 200 tells you the website is up, not that the account exists, so any checker
> that scores a hit from the status code alone will report an account there for
> every handle you type.
>
> On 1 Nov we ran a second, smaller test: 35 controls across eight platforms,
> through MyRecon, Sherlock and Maigret. None of the three produced a false
> positive on the scored controls. The difference was in what they couldn't
> decide: 11 controls stayed unresolved for MyRecon and Maigret and 20 for
> Sherlock, partly because Sherlock's upstream policy excludes nine of them.
> Sherlock also returned "available" on five npm requests that had been
> blocked with HTTP 403, which we counted as unknown rather than as absent.
> Small sample, dated snapshot, and we publish our own tool's numbers next to
> the others, so read it with that in mind.
>
> Method, raw CSV/JSON and checksums:
> https://www.myrecon.xyz/blog/username-search-controlled-study-2026.html
> The 24-platform measurement:
> https://www.myrecon.xyz/guides/why-username-checkers-report-fake-accounts.html
>
> Question for people who do this daily: how do you treat a blocked response
> in your own notes, as "no account" or as "unknown"?

Before posting: re-open both pages and make sure the numbers still match. If
the sub has a weekly tools or self-promotion thread, post it there instead.

---

## Draft C: OSINT Framework issue #880, one follow-up comment

Only post it if the repo's guidelines don't discourage bumps. If there's still
no response after this, record "no response" and stop.

> Hi, a short follow-up on this suggestion from 1 Nov. Nothing has changed in
> scope: MyRecon (I'm the developer) is a public-source username, email breach
> and DNS/WHOIS/IP lookup site with a free tier and paid extras, as described
> above. Since filing, the evidence links above are unchanged, and
> the source for the web toolkit, CLI and API remains public under MIT at
> https://github.com/4ryanwalia/Myrecon. If it doesn't fit the framework, a
> quick "not a fit" is completely fine and I'll close the issue. Thanks for
> maintaining this.

---

## Draft D: one follow-up email each (Sector035, My OSINT Training)

Send only in the same thread as the original, and only if there has been no
reply. One message, then stop.

**Subject:** Re: (keep the original subject)

> Hi, a short follow-up to my note of 1 November, in case it got buried. I'm
> the developer of MyRecon, so this isn't independent, and there's no
> expectation of coverage. The item that may be useful for your readers is the
> measurement rather than the tool: on 6 of 24 sites we tested, a real username
> and an invented one returned the same response, which is why
> status-code-only checkers over-report. Method and raw data:
> https://www.myrecon.xyz/guides/why-username-checkers-report-fake-accounts.html
>
> If it isn't a fit, no reply needed. Thanks for the work you publish.
>
> Aryan

---

## Draft E: free breach API, note to security bloggers

**Choosing recipients:** only people who already publish breach coverage on
their own site, who show a public contact route that accepts tips, and whom you
haven't contacted before. Send each one personally, never in bulk, and
mention one specific post of theirs. Don't guess email addresses.

**Subject:** Free breach metadata feed and widget for your breach posts

> Hi (name),
>
> I read your post on (specific breach post). I'm the developer of MyRecon,
> and I wanted to mention a free resource that might save you some work, with
> no catch attached.
>
> We publish Have I Been Pwned's breach metadata as static JSON: breach
> date, date added, account count, exposed data types and the verified and
> sensitive flags. No account, no API key, CORS enabled, rebuilt daily. The
> latest ten entries are at https://www.myrecon.xyz/data/v1/latest.json, and
> there's a two-line embed widget if you'd like a live list in a sidebar. It sets
> no cookies and draws the attribution itself. Docs:
> https://www.myrecon.xyz/developers.html
>
> One thing to know: the data is Have I Been Pwned's, licensed CC BY 4.0, so
> crediting HIBP is required if you publish it. A link to us is appreciated
> but not required. It is metadata only and can't be used to look up a
> person's email address.
>
> If it's not useful, no need to reply.
>
> Aryan

---

## Facts for a human-written entry (awesome-osint and similar)

For you to write from, in your own words. Not a draft.

- Hosted at https://www.myrecon.xyz/, source for web toolkit, CLI and API at
  https://github.com/4ryanwalia/Myrecon (MIT).
- Username search over a supported catalogue of 500+ platforms with found /
  not found / unknown outcomes; email breach check; k-anonymity password check;
  DNS, WHOIS and IP lookups.
- Free tier with limits; paid Pro for Deep Search and Extended scans.
- You are the developer: their CONTRIBUTING requires that affiliation to be
  disclosed.
