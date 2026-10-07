# Public LinkedIn fallback

The optional `EMAIL_LINKEDIN_PUBLIC_ENABLED=true` adapter reads public JSON-LD only after another source establishes a LinkedIn `/in/` URL. It is not an email-to-LinkedIn resolver and does not need a paid API key. It can also follow the exact LinkedIn website URL published on a GitHub profile with explicit public-email or historical-commit evidence. Historical associations remain historical.

The reader checks LinkedIn robots.txt using its own identified user agent, then performs at most one profile request when allowed. Both requests use a fixed HTTPS host, no redirects, no environment proxies or authentication, bounded time and streamed bytes. Robots denial, login walls, blocks, rate limits and missing structured data are source outcomes, not negative identity results. Completed profiles remain visible even when public retrieval fails.

Only a Schema.org Person whose own URL, sameAs or ID matches the established profile URL is accepted. Display fields include name, description, image, job title, public region, worksFor and alumniOf. Structured Role records may contain job or education dates. No dates, connections, positions or education are invented when absent. Email, phone and street address fields are omitted. LinkedIn frequently restricts public retrieval, so this reader cannot promise full careers or photos.

Upstream research checked October 1, 2026:

- [linkedin_scraper](https://github.com/joeyism/linkedin_scraper) currently documents Playwright and a saved authenticated session. It scrapes an existing profile URL; it does not document resolving an arbitrary email. The user-supplied Selenium description reflects its older version.
- The supplied `https://github.com/joeyism/email2linkedin` repository could not be verified through the public GitHub page or repository lookup. Treat its stated capability as unverified, not an available dependency.
- [LinkedIn robots.txt](https://www.linkedin.com/robots.txt) defines automated access policy. The reader does not impersonate an allowed search-engine crawler.
- [Schema.org Person](https://schema.org/Person), [Role](https://schema.org/Role) and [alumniOf](https://schema.org/alumniOf) define the supported structured public fields and role shapes.

Validation: `python -m pytest backend/tests/test_email_linkedin_public.py -q` passes 27 synthetic tests. No private person or live target was scanned for this validation.
