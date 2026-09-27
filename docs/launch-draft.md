# MyRecon launch drafts

These are public drafts for the owner to review before posting. Verify each community's current rules and the active account first. Do not cross-post rapidly or describe the synthetic demo as a live accuracy test.

## Technical launch story

**Title:** MyRecon: an open-source OSINT toolkit that reports uncertainty

I built MyRecon for people auditing their own public digital footprint. A username checker can give a false sense of certainty when a site returns a sign-in wall, rate limit, or generic HTTP 200 page. MyRecon keeps those results `unknown` and reserves `found` and `not_found` for evidence it can explain.

The repository includes a web app, Python CLI, and Flask API. The standard web catalogue currently has 561 entries; the CLI checks 50 by default or 100 with `--deep`. The offline demo uses four clearly fictional cases to show the verdict rules without contacting any platform: `python examples/offline_demo.py`.

I would value feedback on false positives, unclear verdicts, first-run friction, and safe fixture tests. Please use handles you own or have permission to investigate, and do not post personal scan results.

Repository: https://github.com/4ryanwalia/Myrecon

## Short post

I released MyRecon v0.1.0, an open-source OSINT toolkit for authorized digital-footprint audits. Its username checks keep blocks, login walls, and timeouts as `unknown` instead of pretending they prove an account is absent. Web app, Python CLI, Flask API, and a synthetic offline demo. Feedback on false positives and contributor setup is welcome: https://github.com/4ryanwalia/Myrecon

## Candidate beginner issues

1. **Add offline validation for platform catalogue entries.** Write tests for required fields, unique names across standard and extra catalogues, HTTPS profile URL templates containing `{username}`, and malformed miniature fixtures. Start at `backend/tests/test_platform_catalogue_file.py` and `backend/data/platforms_full.json`. Keep live network checks out of scope. Ask the maintainer to approve the precise validation rules before coding.
2. **Add sanitized username evidence regression fixtures.** Test the `backend/modules/username_checker.py` evidence boundary with local positive-profile, explicit missing-user, generic/login-wall, and timeout examples. Assert that ambiguous and blocked responses remain `unknown`, with no real accounts or HTTP requests. Agree on the exact function and expected output with the maintainer before coding.

## Baseline and measurement

At the September 27, 2026 live check: 2 stars, 0 forks, 0 open issues, 0 releases before v0.1.0. GitHub's community profile was 42% before the contributor files and 71% after. That percentage is checklist coverage, not a Trending score. GitHub Traffic reported 84 views from 27 unique visitors and 812 clones from 295 unique cloners over its available window; clone counts can include automation, so do not treat them as human adoption. Recheck traffic, stars, and useful contributor activity after promotion.
