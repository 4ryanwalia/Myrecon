# AI answer citation check, 18 November 2026

Queries were chosen by Claude from the site's target topics, not taken from
Search Console. Replace or extend them once the Search Console export is in.

Method: Google search in the Claude desktop browser pane, `hl=en&gl=us`, logged
out, one location. Each page was read 8 seconds after load, once the AI Overview
had finished. "MyRecon linked" means a script found an `<a>` pointing at
myrecon.xyz anywhere on page one (AI Overview citations included). "Organic"
lists the hostnames of the page-one result titles in order. One observation, not
a rank tracker. Repeat monthly with the same queries and method.

Not checked: ChatGPT (needs sign-in) and Perplexity (a logged-out query returned
"Sign up and repeat your request"). Both need a signed-in check by the owner.

| # | Query | AI Overview | MyRecon linked | Organic page one (in order) | Notes |
|---|---|---|---|---|---|
| 1 | whatsmyname alternative | Yes | No | reddit, alternativeto, similarweb, osintcombine, whatsmynameapp.us, aiagentsdirectory, x.com, alternativeto, raebaker | Overview (read earlier) does not mention the 9 Nov archive |
| 2 | is whatsmyname still maintained | Yes | Yes, organic #4 (/whatsmyname-alternatives.html); overview citation not determined | linkedin, intelmind, kitploit, **myrecon**, x.com, osintnewsletter, github, whatsmyname.io, reddit | Our dated fact ranks |
| 3 | sherlock username search alternative without python | Yes | No | osint-ui, whatsmynameapp.us, reddit, github (soxoj/osint-namecheckers-list), medium, osint-ui, whatsmynameapp.us, apify, alternativeto | A GitHub list and a Medium comparison rank |
| 4 | why do username checkers show false positives | Yes | **Yes, cited in the AI Overview** (/guides/account-enumeration-false-positives), not in organic | reddit, spiderfoot.tools, malwarebytes, thehypemagazine, mit.edu, sandiego.edu, turnitin, youtube, identogo | Only AI Overview citation found |
| 5 | what does it mean if my email is not found in a data breach check | Yes | No | secria, reddit, haveibeenpwned, aura, google support, facebook, malware.news, quora, forbes | /blog/breach-check-no-results-meaning.html matches the intent but is absent |
| 6 | how much do osint tools cost | Yes | No | osint.industries, shadowdragon, reddit, intelmind, forensicosint, espectrosint, maltego, comparitech, app.osint.industries | Our 15 Nov price guide is 3 days old |
| 7 | sherlock vs maigret | Yes | No | footprintiq, osintverse, reddit, facebook, linkedin, police1, maxintel, timsullivan | We have /blog/sherlock-vs-maigret-vs-myrecon.html |
| 8 | free data breach api | Yes | No | xposedornot, github, haveibeenpwned, leakcheck, hudsonrock, enzoic, dehashed, freepublicapis | Intent is email lookup; our API is metadata only, so not our query |
| 9 | best free username search tool | Yes | No | whatsmynameapp.us, whatsmyname.io, reddit, recosint, shadowdragon, revealer, instantusername, socialcatfish, osintnewsletter | Overview leads with whatsmynameapp.us. whatsmyname.io says it is independent of the project; whatsmynameapp.us affiliation not verified |
| 10 | how to find my old social media accounts | Yes | No | reddit, social-searcher, pnewton84.github.io, smartsocial, consumerreports, meta | |
| 11 | have i been pwned breach date vs added date | Yes | No | haveibeenpwned (x4), uservoice, wikipedia, reddit, consumerreports, dnsstuff | /blog/breach-date-vs-disclosure-date.html covers this; HIBP owns the query |
| 12 | free digital footprint checker | Yes | No | digitalfootprintcheck, malwarebytes, incogni, whatsmynameapp.us, reddit, aura, footprintiq, bitdefender, whatsmyname.io | |
| 13 | is myrecon legit | Yes | **Yes, overview cites /about.html**; organic #6 is myrecon.xyz | scamadviser (unrelated myrecon.shop), play.google, trustpilot, reddit, github, **myrecon**, youtube, medium, trustpilot | Overview splits the answer with an unrelated store; /is-myrecon-legit.html opening fixed in this session |
| 14 | castlerat data breach | Yes | No | europol, shadowserver, haveibeenpwned, securityweek, thehackernews, aviatrix, helpnetsecurity, mozilla monitor, optmsg | Primary sources and news own the spike |
| 15 | how to check if my email was in a data breach | Yes | No | haveibeenpwned, norton, databreach.com, reddit, ca.gov, mozilla monitor, whatismyipaddress, avast, secria | |

## What this says

- Two of 15 link to MyRecon: a dated fact (query 2) and a guide with measured data cited by the AI Overview (query 4). Both are original information others lack, which is the pattern to repeat.
- Lists and threads rank (reddit on 12 of 15, AlternativeTo, the soxoj GitHub list). Getting listed there is off-site work for the owner.
- Sites using the WhatsMyName name lead the generic username queries (1, 3, 9, 12).
- Queries 5, 7 and 11 have a matching MyRecon page that does not appear. Search Console data is needed to see whether those pages get impressions before rewriting them.
