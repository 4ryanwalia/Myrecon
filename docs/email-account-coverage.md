# Email account evidence

Web and Android show named historical breach associations even with live linked-account checks disabled. Canva, Adobe, Dropbox and other named service records appear as historical evidence. Combined breach collections and stealer lists are not treated as service accounts. Historical evidence does not establish a current account or ownership.

The opt-in toggle sends the address to MyRecon and responding services. Public GitHub evidence remains separate from registration signals. Android requests registration coverage through `POST /api/email/accounts`; the web email endpoint includes the same `registration_checks` object. Results, including per-service gaps, survive saved-report serialization and text export.

## Holehe runtime

The catalogue contains 123 modules from [Holehe](https://github.com/megadose/holehe) revision `14da70f588538936b20d238783c5e28a0772a2b3`. There are 111 initially eligible modules, including Spotify. Twelve modules are excluded because their implementations use password recovery, credential submission or account creation. Runtime guards may exclude additional requests. Catalogue size is not completed coverage.

The external runtime is installed from the pinned Git dependency in `backend/requirements.txt`, requires Git during installation, and executes in a separate subprocess. Holehe is GPL-3.0 licensed: its unchanged source and license are available at the linked upstream revision. Its implementation is not vendored into MyRecon. Module hashes must match the reviewed catalogue. If the dependency is unavailable or changes, checks return unavailable rather than a negative answer.

Each service returns `found`, `no_signal`, `rate_limited`, `timeout`, `skipped` or `unavailable`. Found means the service returned a registration signal, not a verified profile. No signal does not prove absence. `checked` counts only found and no-signal responses. `attempted` excludes skipped requests. Both counts and all service outcomes are visible.

There are at most 12 concurrent service checks per subprocess, five HTTP requests per module, seven seconds per service and 35 seconds overall. The backend permits at most two simultaneous registration workers per process. Recovery endpoints, nonempty credentials, message-trigger fields and non-HTTPS requests are blocked. Redirects are not followed and TLS verification stays enabled. Provider throttling is not retried or bypassed. Recovery hints and raw provider payloads are discarded. Email is passed on stdin rather than command arguments and is not cached by the adapter.

Actual coverage depends on providers and network conditions. A user-owned email and an installed Android device are required to verify specific personal account matches and the physical-device journey. Local browser fixtures exercise historical evidence, optional scanning, service outcomes and provider outages without asserting real matches.
