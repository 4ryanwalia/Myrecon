# Email account evidence

Web and Android show named historical breach associations even with live linked-account checks disabled. Canva, Adobe, Dropbox and other named service records appear as historical evidence. Combined breach collections and stealer lists are not treated as service accounts. Historical evidence does not establish a current account or ownership.

The opt-in toggle sends the address to MyRecon and responding services. Public GitHub evidence remains separate from registration signals. Android requests registration coverage through `POST /api/email/accounts`; the web email endpoint includes the same `registration_checks` object. Results, including per-service gaps, survive saved-report serialization and text export.

## Holehe runtime

### Selected User Scanner review (2026-10-05)

The existing guarded worker also runs two native MyRecon adapters inspired by
[User Scanner](https://github.com/kaifcodec/user-scanner), reviewed from the
supplied local snapshot. The external tool, CLI, updater and transports are
not executed or installed. Its documentation is reference material, not
authorization to submit credentials or bypass provider restrictions.

| Service | Decision | Signal or reason |
| --- | --- | --- |
| Hugging Face | Added | Email-only POST `/api/check-user-email`; explicit JSON availability message or already-exists message |
| HackerRank | Added | Email-only POST `/auth/valid_email`; explicit already-registered code/message, or uncontradicted boolean success |
| Codewars | Excluded | Submits `/join` account-creation form, follows redirects and infers availability from unrelated validation errors |
| RubyGems | Excluded | Submits `/users` account-creation form |
| LuaRocks | Excluded | Sends password recovery |
| HackerOne | Excluded | Submits account-creation form with credentials |
| HackerEarth | Excluded | Submits account-creation form, even though its password is blank |
| Qiita | Excluded | Submits registration with credentials and assumes availability from ambiguous responses |
| Envato | No addition | Already in the pinned Holehe catalogue |
| Codecademy | No addition | Already in the pinned Holehe catalogue |

The total catalogue is now 125 checks: the original 123 Holehe entries plus
these two distinct services. There are 113 initially eligible checks. The new
checks use the existing seven-second service, 35-second overall, five-request
and 12-concurrent-check budgets, HTTPS verification, no redirects, no retries,
stdin-only email transport and unchanged request guard. They additionally
allow only their exact endpoint and a JSON object containing only `email`.
Each row identifies its engine in coverage and text exports. Unknown schemas,
bare HTTP success, invalid-email errors and generic `status: false` remain
unavailable. No public profile is synthesized from these registration checks.
They run only through the existing opt-in flow and feed its registration
summary and saved JSON/text exports. No email cache or logging is added.

Acceptance is based on source inspection and mocked request/response tests.
Public page inspection does not verify live email matches; provider schema,
non-notification and availability have not been verified with a user-owned
address. A provider block stays visible and is never bypassed.

### Preserved Holehe integration

The catalogue contains 123 modules from [Holehe](https://github.com/megadose/holehe) revision `14da70f588538936b20d238783c5e28a0772a2b3`. There are 111 initially eligible modules, including Spotify. Twelve modules are excluded because their implementations use password recovery, credential submission or account creation. Runtime guards may exclude additional requests. Catalogue size is not completed coverage.

The external runtime is installed from the pinned Git dependency in `backend/requirements.txt`, requires Git during installation, and executes in a separate subprocess. Holehe is GPL-3.0 licensed: its unchanged source and license are available at the linked upstream revision. Its implementation is not vendored into MyRecon. Module hashes must match the reviewed catalogue. If the dependency is unavailable or changes, checks return unavailable rather than a negative answer.

Each service returns `found`, `no_signal`, `rate_limited`, `timeout`, `skipped` or `unavailable`. Found means the service returned a registration signal, not a verified profile. No signal does not prove absence. `checked` counts only found and no-signal responses. `attempted` excludes skipped requests. Both counts and all service outcomes are visible.

There are at most 12 concurrent service checks per subprocess, five HTTP requests per module, seven seconds per service and 35 seconds overall. The backend permits at most two simultaneous registration workers per process. Recovery endpoints, nonempty credentials, message-trigger fields and non-HTTPS requests are blocked. Redirects are not followed and TLS verification stays enabled. Provider throttling is not retried or bypassed. Recovery hints and raw provider payloads are discarded. Email is passed on stdin rather than command arguments and is not cached by the adapter.

Actual coverage depends on providers and network conditions. A user-owned email and an installed Android device are required to verify specific personal account matches and the physical-device journey. Local browser fixtures exercise historical evidence, optional scanning, service outcomes and provider outages without asserting real matches.
