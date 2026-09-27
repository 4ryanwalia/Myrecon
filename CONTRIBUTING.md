# Contributing to MyRecon

Help make public-source research easier to reproduce and less likely to mislead. Documentation, provider fixtures, accessibility fixes, and focused regression tests are welcome.

## Agree on scope

For substantial or behavior-changing work, open an issue with the problem, proposed approach, and verification plan. Wait for **@4ryanwalia to approve the scope** before starting that work. For a small documentation correction, a focused pull request is welcome directly.

Every pull request needs explicit approval from **@4ryanwalia before merge**. Opening an issue, assignment, a passing check, or another review does not replace that approval. Contributions are not guaranteed acceptance.

## Start locally

```bash
git clone https://github.com/4ryanwalia/Myrecon.git
cd Myrecon
python -m venv .venv
```

Activate the environment with `.venv\Scripts\Activate.ps1` on PowerShell or `source .venv/bin/activate` on macOS/Linux. Then:

```bash
python -m pip install -r backend/requirements.txt
python -m pip install pytest
python examples/offline_demo.py
python -m pytest backend/tests -q
```

The demo uses synthetic data and needs no dependencies. See the [README](README.md#run-the-website-locally) for local API and frontend setup. Never use production credentials for a contribution.

## Keep evidence honest

- Preserve `found`, `not_found`, and `unknown`. A timeout, block, challenge, or login wall is unresolved, not a missing account. HTTP 200 alone is insufficient positive evidence.
- For a provider change, describe the evidence rule and include sanitized or synthetic fixtures for relevant success, missing, and uncertain cases. Test parsing without contacting real accounts in CI.
- Shared handles are leads, not proof that accounts belong to one person. Use handles you own or are authorized to research for any necessary manual checks.
- Keep keys, cookies, private data, and identifiable lookup results out of issues, screenshots, fixtures, and commits. Report suspected vulnerabilities through [GitHub's private reporting option](https://github.com/4ryanwalia/Myrecon/security/advisories/new) if available; otherwise contact the maintainer through the [contact page](https://myrecon.xyz/contact.html) to arrange private disclosure before sharing details.

## Submit a reviewable change

1. Fork the repository and create a branch for one change.
2. Explain the user-visible problem and link the approved issue where applicable.
3. Run checks that exercise the behavior changed. For backend changes, run the backend suite above; for UI changes, include desktop/mobile verification and screenshots with sample data.
4. State the exact commands and outcomes in the pull request, including anything you could not verify.
5. Wait for maintainer review and address feedback. Keep unrelated cleanup in a separate change.

By contributing code, you agree that your contribution is licensed under the repository's [MIT License](LICENSE).
