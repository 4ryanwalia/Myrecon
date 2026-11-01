# Independent coverage outreach

Checked 1 November 2026. Goal: invite honest external testing and editorial
evaluation of MyRecon. Documentation and drafts were prepared with AI assistance.
The developer's affiliation must remain visible in every submission.

## Verified routes and status

| Recipient | Fit and public route | Status / constraint |
| --- | --- | --- |
| OSINT Newsletter / OSINT Tools Library | Reviewed directory and tool coverage. [Submission guide](https://tools.osintnewsletter.com/submission-guide) links its [tool form](https://forms.gle/kFE3Ddj4rbzsnxyUA). | Submitted 1 Nov 2026; form confirmed "Your response has been recorded." [Exact submission](osint-newsletter-submission-2026-11-01.json), [receipt](osint-newsletter-receipt-2026-11-01.jpg). Editorial decision pending. |
| OSINT Framework | Public/free OSINT discovery. [Repository guidelines](https://github.com/lockfale/OSINT-Framework#contribute-with-a-github-pull-request) welcome a PR or issue. | Submitted 1 Nov 2026: [issue #880](https://github.com/lockfale/OSINT-Framework/issues/880), open and awaiting evaluation. Hosted freemium limits and affiliation disclosed. |
| Sector035 | Researcher and Week in OSINT publisher. [Homepage](https://sector035.nl/) invites useful tips at sector035@pm.me. | Invitation sent 1 Nov 2026 at 22:20 IST; Gmail displayed "Message sent" and the sent conversation was verified. No reply/publication yet. Current publishing cadence is unconfirmed (visible archive includes 2024). |
| My OSINT Training / instructor team | Security educators, including WhatsMyName creator Micah Hoffman. [Company contact](https://sg.linkedin.com/company/my-osint-training) lists support@myosint.training; [instructor page](https://www.myosint.training/pages/instructors) establishes fit. | Invitation sent 1 Nov 2026; Gmail confirmed "Message sent." [Exact invitation](my-osint-training-invitation-2026-11-01.md). Response/publication pending. |
| Sofia Santos / Gralhix | Educator and researcher; [about page](https://gralhix.com/aboutme/) links LinkedIn, Mastodon and Bluesky private messages. | Draft ready. LinkedIn message and connection routes displayed a Premium reactivation upsell. No message or invitation sent and no purchase made. No guessed email used. |
| Steven Harris / Nixintel | Published practical OSINT tool tests and account-verification guidance. His [contact page](https://nixintel.info/contact/) provides a form or LinkedIn. | Suitable reviewer identified; no invitation sent. Browser use is disabled in current settings, so the form could not be submitted. No guessed email or alternate-channel follow-up. |
| Awesome OSINT | [Contribution rules](https://github.com/jivoi/awesome-osint/blob/master/CONTRIBUTING.md) require affiliation disclosure and explicitly prohibit LLM/agent-submitted PRs. | Excluded from agent submission. A human may independently evaluate whether to submit. |
| Bellingcat toolkit | [Official introduction](https://www.bellingcat.com/resources/2024/09/24/bellingcat-online-investigations-toolkit/) links its [contribution form](https://forms.gle/dZvsJzuEjTNjJ9HWA). | Excluded: the live form says not to suggest your own tools. Toolkit email also excludes tool suggestions. |

Prior GitHub issues/PRs in OSINT Framework and OSINT Tools Library were searched
for MyRecon on this date; no matches were returned. Recheck before sending a
later suggestion. Do not submit both a form and PR for the same recipient.

## Shared evidence

- [Review kit](../review-kit/README.md): source-pinned reproduction, limitations,
  privacy/access distinctions and the independent-review request.
- [Raw run and notes](../review-kit/evidence/README.md): first-party measurements,
  timestamps and integrity hashes.
- [Blank review worksheet](../review-kit/review-worksheet.md): independent expected
  labels, tool verdicts, mismatches, unknowns and denominators.
- [Separate expanded study](https://github.com/4ryanwalia/Myrecon/tree/1da82d7b8541cff254a44d7b63bae4fb6ca5b1d0/frontend/assets/downloads/username-controls-2026-11-01):
  35 platform-specific controls across eight platforms with actual pinned
  comparator runs, 105 CSV rows, raw JSON, reproduction harness and checksums.
  Eleven references remained unresolved; this is still first-party evidence.

The kit is first-party. Publication by the developer on GitHub is not independent
coverage. No independent review or endorsement is claimed by this tracker.

## Submitted OSINT Framework suggestion text

Title: Consider MyRecon for public username research

Disclosure: I am Aryan Walia, the developer of MyRecon at BugSnaps. This suggestion
was prepared with AI assistance and is submitted on behalf of the project.

Would you evaluate MyRecon for the username research category? It has an
MIT-licensed CLI and web frontend, plus a hosted interface with free guest and
paid limits. Public username verdicts distinguish found, not_found and unknown;
matching handles are leads, not identity proof or registration availability.

Source: https://github.com/4ryanwalia/Myrecon

Review kit: https://github.com/4ryanwalia/Myrecon/blob/97f976bd120488c7ddd26ce444b88f7931a31ed1/docs/review-kit/README.md

The kit includes source-pinned commands, raw first-party results for ten fixed
usernames on three platforms, synthetic offline examples, and a worksheet for
your own cases. The reference shares some API evidence with the engine, so it
is a regression sample, not an independent accuracy audit. Please include any
limitations you find. No endorsement, ranking or positive coverage is requested.

Suggested concise entry: MyRecon - Public username leads and domain/DNS/IP
lookups through an MIT-licensed CLI and hosted web interface; hosted access has
free and paid limits. Verify account matches at the original source.

## Sector035 invitation sent

The [exact invitation](sector035-invitation-2026-11-01.md) was sent on 1 November
2026 at 22:20 IST. The sent Gmail conversation was verified. Receipt stays local.

## My OSINT Training invitation sent

The [exact invitation](my-osint-training-invitation-2026-11-01.md) asks the
instructor team to evaluate the exercise's teaching value and limitations. The
public contact address was verified on the company's own LinkedIn profile.
Gmail confirmed sending. No response or publication has been confirmed.

## Sofia Santos professional-message draft

Hi Sofia, I am Aryan Walia, the developer of MyRecon at BugSnaps. Your public
OSINT exercises suggested a useful teaching question: when should a username
lookup remain inconclusive?

Would you be interested in testing a short exercise using MyRecon's synthetic
offline verdict examples, then accounts you control? The code is MIT-licensed;
the hosted site has separate free and paid limits. The review kit has
source-pinned commands, raw first-party data, a blank worksheet and limitations:
https://github.com/4ryanwalia/Myrecon/blob/97f976bd120488c7ddd26ce444b88f7931a31ed1/docs/review-kit/README.md

The supplied three-platform sample is not an independent accuracy audit. I
would value any failures and teaching limitations you find. You choose your
cases, conclusions and whether to publish. No payment or positive coverage is
offered or requested. This invitation was prepared with AI assistance. If it
is outside your interests, no reply is needed.

## Current outcome

Four invitations/suggestions were sent: the OSINT Tools Library form, OSINT
Framework issue, Sector035 email, and My OSINT Training email. No independent review, accepted listing,
endorsement or publication has been confirmed. Sofia Santos's optional invitation remains unsent; My OSINT Training received the educator request. Gmail browser access was used for the email; no new email connection was
required. Its receipt stays local so unrelated account details are not published.

The kit and evidence were published on `main` in commit
`97f976bd120488c7ddd26ce444b88f7931a31ed1`. GitHub backend/security checks and the
Vercel deployment passed for that commit. Local validation covered 21 benchmark
tests, the synthetic demo, live raw JSON, evidence hashes and local document links.

Rechecked on 1 November 2026 after the initial invitations: Gmail's authoritative
conversation API returned only the sent invitation in each of the Sector035 and
My OSINT Training threads. A focused delivery-failure search returned no matches;
this does not prove recipient delivery or reading. OSINT Framework issue #880
remained open with no comments. No published independent coverage was verified.
The existing requests are awaiting external evaluation; no repeat email was sent.

The newer study's loose-file and archive checksums, 35-case manifest, eight-platform
scope, 105 CSV rows and outcome summaries were checked before linking it here.
It supplements the original 30-pair evidence; the original records are unchanged.

## Follow-up and outcome recording

Use at most one individual follow-up after 10-14 days if the recipient permits
it; stop on a decline. Do not follow up through unrelated channels. A follow-up
date here is guidance, not an automatically scheduled message.

The initial requests were sent on 1 November 2026. The first follow-up window is
11-15 November 2026, subject to the recipient's rules and any response. Response
checks before then should not trigger additional messages merely because no
reply has arrived. No monitor or scheduled email has been created.

Record submitted date, exact recipient, evidence permalink, receipt/PR URL,
response, and any requested correction. Keep private correspondence out of the
public repository. Record external outcomes as: submitted, acknowledged,
testing, published listing, published review, declined, or no response. Only a
published third-party URL establishes coverage; do not infer testing from
acceptance or infer endorsement from directory inclusion.
