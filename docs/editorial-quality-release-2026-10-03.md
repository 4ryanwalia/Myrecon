# Editorial quality release, October 3, 2026

The release replaces generated topic substitutions with focused workflows and
removes 201 overlapping or unsupported landing routes. Permanent redirects retain
old entry links; retired article files and sitemap entries are removed. The
redirect inventory is `frontend/content/editorial-redirects.json`.

Seven public-source guides, three platform guides and the Sherlock comparison
were rewritten. The four topic hubs now help readers select a workflow, including
account deletion, broker suppression and search-result removal. Existing original
explainers, blog articles and breach case files remain accessible. The two breach
entries missing editorial interpretation now distinguish reported fields,
plausible risks and unknown intrusion mechanisms.

The GitHub article includes a real signed-out capture of the public Octocat page
observed for this release. Worked examples elsewhere are explicitly illustrative.
The articles distinguish a documented procedure from an account flow that was
actually tested; private-account settings and deletion flows were not exercised.

Coverage and plan wording follows the standard catalogue and `backend/core/plans.py`:
500+ standard platforms, limited guest previews, five complete standard scans per
UTC day for signed-in free accounts, and a separate optional paid Extended scope.
The Android listing is described as closed testing. Repeated article invitations
are below useful content and the floating invitation is removed.

Build safeguards require reviewed, topic-specific workflows for newly published
editorial records. They do not require a minimum page count. The finalizer resolves
retired internal links after all article generators. Visible generated FAQs are
refreshed along with their structured data.

Validation: full static build; 42 Node tests including all retired route,
sitemap and internal page-link checks; ten representative editorial routes at
390px and 1280px browser widths, with actual image loading and layout checks.

AdSense approval is determined by Google. This release does not certify approval,
traffic authenticity, completed indexing, or the exact cause of an earlier review.
Policy reference: https://support.google.com/adsense/answer/10015918?hl=en

## Follow-up: discovery and reproducible evidence

The exact production sitemap passed Google's Search Console live inspection on
October 3: crawl allowed Yes, page fetch Successful. The separate Sitemaps report
still showed Couldn't fetch and zero discovered pages. No manual actions were
reported. A successful live inspection does not establish sitemap processing or
indexing; no server-side block was found that would justify changing the sitemap
address merely to reset the report.

Navigation auditing found two sitemap pages with no reachable incoming links:
the Standard/Extended explainer and the original Have I Been Pwned comparison.
The comparison hub now links both. All 179 sitemap pages can be reached by
following links from the homepage.

Four guides now include review tables, three include downloadable local CSV
worksheets, and the false-positive guide explains an observed GitLab HTTP-200
false positive from the October 2 regression run. A frozen JSON snapshot retains
the method, source URLs, dates and version evidence. It is a historical example,
not an independent accuracy audit or a current account-status claim.

Further builds exposed a notice duplication bug: the article enhancer removed
old section notices but did not remove paragraph notices. It now removes either
form before appending one end-of-content notice. Existing duplicated paragraphs
are cleaned from original articles. Checks prevent a recurrence.

Validation: 46 Node tests and 14 editorial routes at 390px and 1280px. This is
evidence of implemented quality and discovery improvements, not an approval score.
