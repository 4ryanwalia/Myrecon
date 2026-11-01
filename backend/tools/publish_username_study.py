"""Package a completed study and render the indexable article without network IO."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
from pathlib import Path
import zipfile

from expanded_username_study import ROOT, TOOLS, outcome, tool_summary, write

SLUG = "username-search-controlled-study-2026"
EVIDENCE = "username-controls-2026-11-01"
LABELS = {"supported_match": "Supported match", "supported_absence": "Supported absence",
    "false_positive": "False positive", "false_negative": "False negative",
    "unscored_reference": "Unscored reference", "unresolved_prediction": "Unresolved prediction"}
COHORTS = {"upstream_claimed_fixture": "Claimed fixture", "upstream_unclaimed_fixture": "Unclaimed fixture",
    "synthetic_negative_candidate": "Generated candidate"}
esc = lambda x: html.escape(str(x), quote=True)


def table(caption, headers, rows, identity=""):
    return f'<table{f" id={chr(34)}{identity}{chr(34)}" if identity else ""}><caption>{caption}</caption><thead><tr>' + ''.join(
        f'<th scope="col">{esc(h)}</th>' for h in headers) + '</tr></thead><tbody>' + ''.join(
        '<tr>' + ''.join(f'<{"th scope=\"row\"" if i == 0 else "td"}>{cell}</{"th" if i == 0 else "td"}>'
            for i, cell in enumerate(row)) + '</tr>' for row in rows) + '</tbody></table>'


def validate(data):
    if data.get("status") != "measured":
        raise ValueError("Cannot publish an incomplete study")
    if data["checks"] == [] or len(data["checks"]) != len(data["manifest"]["cases"]):
        raise ValueError("Missing cases")
    for row, case in zip(data["checks"], data["manifest"]["cases"]):
        if any(row[k] != case[k] for k in case):
            raise ValueError("Case selection changed after measurement")
        for tool in TOOLS:
            if outcome(row["reference"], row[tool]) != row[tool]["outcome"]:
                raise ValueError("Outcome drift")
    for tool in TOOLS:
        if tool_summary(data["checks"], tool) != data["summaries"][tool]:
            raise ValueError("Summary does not reconcile")


def render(data):
    n = len(data["checks"])
    platforms = ', '.join(data["manifest"]["platforms"])
    base = f"/assets/downloads/{EVIDENCE}"
    metadata = {"title": "Username Search Study: 35 Controls, 8 Platforms | MyRecon",
        "headline": "Expanded username testing: 35 controls across eight platforms",
        "description": "Original MyRecon, Sherlock and Maigret control study: supported matches, false positives, unresolved checks, pinned versions and downloadable CSV/JSON evidence.",
        "category": "Research", "datePublished": "2026-11-01", "dateModified": "2026-11-01",
        "editorial_review": "2026-11-01"}
    parts = ['<!--\n' + json.dumps(metadata, indent=2) + '\n-->']
    def add(value):
        parts.append(value)
    add(f'<p class="lead">We tested <strong>{n} platform-specific controls across eight platforms</strong> with the MyRecon web engine, Sherlock and Maigret on 1 November 2026. Each tool has {n} recorded outcomes, including exclusions and unresolved checks. MyRecon and Maigret each returned six source-supported matches; Sherlock returned four. No definitive false positives were observed on the scored controls. Eleven reference checks remained unresolved, and Sherlock also excluded nine controls under its current upstream policy. These limits matter when reading the results.</p>')
    add('<p><strong>Publisher disclosure:</strong> MyRecon ran and publishes this study of its own engine and competing tools. The sample uses published upstream testing fixtures and generated candidates. We do not claim to own those fixture accounts. Personal social-media handles and customer search history are excluded. A fixture handle used on several platforms does not imply the accounts share an owner.</p>')
    add(f'<p><strong>Observation window:</strong> <time datetime="{esc(data["started_at_utc"])}">{esc(data["started_at_utc"])}</time> to <time datetime="{esc(data["finished_at_utc"])}">{esc(data["finished_at_utc"])}</time> (UTC). This is a dated snapshot. <a href="{base}/evidence.zip" download>Download the complete evidence ZIP</a>, <a href="{base}/checks.csv" download>105-row CSV</a>, <a href="{base}/study.json" download>JSON observations</a> and <a href="{base}/SHA256SUMS.txt" download>SHA-256 checksums</a>.</p>')
    add('<h2 id="results">Supported matches, false positives and unresolved checks</h2>')
    add(table('All 35 controls per tool; excluded, failed and unknown cases remain in the denominator.',
        ['Tool', 'Supported matches (TP)', 'False positives (FP)', 'False negatives (FN)', 'Supported absences (TN)', 'Unresolved / unscored', 'Scored / total', 'Coverage', 'FP / scored negatives'],
        [[esc(data['tool_metadata'][t]['label']), *[str(data['summaries'][t][k]) for k in ('TP','FP','FN','TN','unresolved_checks')],
          f"{data['summaries'][t]['scored']} / {n}", f"{data['summaries'][t]['coverage_percent']}%",
          f"{data['summaries'][t]['FP']} / {data['summaries'][t]['negative_denominator']}"] for t in TOOLS], 'study-results'))
    add('<p><strong>Supported match:</strong> a normalized positive agrees with current, account-specific reference evidence. <strong>False positive:</strong> a normalized positive contradicts explicit reference absence. <strong>False negative:</strong> a normalized negative contradicts a verified existing account. <strong>Unresolved / unscored:</strong> the reference or prediction is unknown, counted once per control. This includes upstream exclusions. Excluded entries were recorded without making a tool request. Zero observed false positives here is not a guarantee of zero errors elsewhere.</p>')
    add('<p>Coverage is (TP + TN + FP + FN) / all 35 controls. The false-positive denominator is FP + TN; unknown predictions on reference negatives are excluded from that denominator and retained in the evidence. No whole-catalogue accuracy or speed ranking follows from this developer/community sample.</p>')
    add('<h2 id="native-claims">Native claims and quarantined outcomes</h2>')
    add(table('Native CLAIMED outcomes are retained even when normalization changes a verdict to unknown.',
        ['Tool', 'Reported claims', 'Source supported', 'Source contradicted', 'Reference unresolved', 'Unknown predictions'],
        [[esc(data['tool_metadata'][t]['label']), *[str(data['summaries'][t][k]) for k in ('reported_claims','source_supported_claims','source_contradicted_claims','unresolved_claims','unknown_predictions')]] for t in TOOLS], 'native-claims-results'))
    add('<p>Maigret reported two additional npm claims whose references returned HTTP 401. Both remain unverified. Sherlock returned native AVAILABLE on five denied npm requests; their HTTP 403 responses are normalized to unknown, preserving the native statuses. Blocks and unavailable sources are not evidence of account absence. All tool-specific outcomes appear below and in the CSV.</p>')
    add('<h2 id="controls">How the controls were selected and verified</h2>')
    add(f'<p>The predeclared manifest contains 11 upstream claimed fixtures, eight upstream unclaimed fixtures and 16 generated negative candidates. They span {esc(platforms)}. Each fixture is tested only on the platform that published it as a control; this is not a cross-platform identity search. Case variants in case-insensitive namespaces are deduplicated. The 35 pairs contain 23 literal handle spellings (22 case-folded strings); repeated handles do not represent independent people.</p>')
    add(f'<p>The <a href="{base}/controls.json" download>selection manifest</a> records the upstream repository revision, source field, selected detection rule and rule hash for each fixture. Two deterministic 14-character alphanumeric candidates per platform are generated from the study ID, platform and index. Random-looking names are not assumed absent. Current source evidence determines their reference labels.</p>')
    add('<p>All reference observations were collected before tool predictions. Exact typed official API objects, explicit API absence, or a PyPI profile title naming the exact handle can establish a reference. HTML 200 alone, tool agreement, a login wall and a challenge cannot. We retain only account identifiers needed to verify the reference, response status, timestamps, response length and SHA-256, with profile contents omitted.</p>')
    add('<h2 id="disagreements">Stale fixtures and unresolved observations</h2>')
    add('<ul><li><strong>Stale claimed fixture:</strong> Sherlock’s Hacker News fixture <code>blue</code> returned JSON <code>null</code> from the official API. It is a verified absence in this snapshot, despite its historical claimed label. The <code>pg</code> fixture was confirmed separately.</li><li><strong>GitHub namespace:</strong> the official API identifies <code>blue</code> as an organization. This supports the tested public account namespace; it does not verify an individual person.</li><li><strong>npm:</strong> all five independent reference requests returned HTTP 401. Their account truth remains unknown, including the three negative candidates.</li><li><strong>PyPI:</strong> all five reference pages showed a Client Challenge. Sherlock’s negative outputs cannot be scored against those challenges. Maigret’s PyPI rule is disabled/protected and stayed unknown.</li><li><strong>Keybase:</strong> the published long unclaimed fixture did not satisfy the reference’s typed absence rule. Its negative predictions are unscored; the two shorter generated candidates were verified absent.</li><li><strong>Sherlock exclusions:</strong> the captured upstream exclusion list contains HackerNews and DEV Community. Their nine controls stay unknown. The study honors those exclusions even though the engine and bundled rules are pinned.</li></ul>')
    add('<h2 id="matrix">Every control and tool outcome</h2>')
    matrix = []
    for row in data['checks']:
        reference = row['reference']
        reftext = {'found':'Verified account','not_found':'Verified absence','unknown':'Unresolved'}[reference['verdict']]
        cell = f'<a href="{esc(reference["url"])}" rel="noreferrer">{reftext}</a><br><small>{esc(reference["evidence"])}; HTTP {esc(reference["status_code"] or "unavailable")}</small>'
        toolcells = []
        for tool in TOOLS:
            p = row[tool]
            reason = p.get('reason_code') or p.get('native_status') or p['verdict']
            toolcells.append(f'<strong>{LABELS[p["outcome"]]}</strong><br><small>{esc(reason)}; HTTP {esc(p.get("status_code") or "—")}</small>')
        matrix.append([f'{esc(row["id"])} · {esc(row["platform"])}<br><code>{esc(row["handle"])}</code><br><small>{COHORTS[row["cohort"]]}</small>', cell, *toolcells])
    add(table('Thirty-five platform-specific controls. Source links identify what was checked; dated retained observations are in the downloads.', ['Control / provenance', 'Independent reference', 'MyRecon', 'Sherlock', 'Maigret'], matrix, 'control-matrix'))
    add('<h2 id="versions">Tool versions, rules and execution settings</h2>')
    add(table('Pinned source revisions, selected rule fingerprints and UTC execution windows.', ['Tool / version', 'Source revision', 'Configuration / rule hash', 'Started / finished (UTC)'], [
        [f'{esc(data["tool_metadata"][t]["label"])} {esc(data["tool_metadata"][t]["version"])}',
         f'<code>{esc(data["tool_metadata"][t]["commit"])}</code>',
         ('One connection; 45-second deadline; 6-second connect / 8-second read timeout.' if t == 'myrecon' else 'One connection; 8-second timeout; no enrichment, parsing, recursion or retries.') + '<br><code>' + esc(data['tool_metadata'][t].get('selected_rules_sha256') or data['tool_metadata'][t]['selected_catalogue_sha256']) + '</code>',
         esc(data['tool_metadata'][t]['started_at_utc']) + '<br>' + esc(data['tool_metadata'][t]['finished_at_utc'])] for t in TOOLS], 'tool-versions'))
    add(f'<p>Python {esc(data["tool_metadata"]["myrecon"]["python_version"])}, Requests {esc(data["tool_metadata"]["myrecon"]["requests_version"])}; one Windows workstation and network. References ran first, followed by MyRecon, Sherlock and Maigret in sequence, with one platform per request group and fixed pacing. Application caches were bypassed; provider caches were not controlled. Engine source files and the harness have separate SHA-256 hashes in the JSON. The MyRecon source revision describes the local web engine, not a hosted UI or Android device test.</p>')
    add('<p>Third-party code and bundled rules are pinned to the versions shown, without claiming they are the newest releases. Sherlock’s mutable exclusion list was fetched once and captured with its timestamp and SHA-256. No supplied credentials, proxies or block bypass were used. Upstream libraries may handle cookies returned by the sites. HTTP denials/errors (including 419), redirects that remain unresolved, unsupported checks and native failures normalize to unknown while retaining native output.</p>')
    add('<h2 id="downloads">Download and reproduce the evidence</h2>')
    add(f'<ul><li><a href="{base}/evidence.zip" download>Evidence ZIP</a>: measured JSON, 105-row CSV, fixed manifest, reproduction scripts and upstream license notices.</li><li><a href="{base}/study.json" download>Measured JSON</a>: references, all tool outcomes, source hashes, selected rules, exclusions, versions and timestamps.</li><li><a href="{base}/checks.csv" download>CSV</a>: one row for every tool/control pair, including unknown and excluded outcomes.</li><li><a href="{base}/controls.json" download>Predeclared control manifest</a>, <a href="{base}/README.md" download>reproduction instructions</a> and <a href="{base}/SHA256SUMS.txt" download>SHA-256 checksums</a>.</li></ul>')
    add('<p>Extract the ZIP and follow its README. Check out the recorded MyRecon revision, install the pinned third-party requirements in an isolated Python 3.12 environment, copy the included study harness, and run it with the provided manifest. A fresh run makes fresh network observations; it will not necessarily reproduce these historical outcomes. The ZIP contains retained, privacy-minimized observations and source-response hashes, rather than complete profile bodies.</p>')
    add('<pre><code>python backend/tools/expanded_username_study.py --manifest controls.json --output output/new-study.json</code></pre>')
    add('<h2 id="limits">Limitations and what this study supports</h2>')
    add('<p>This expands the earlier single-handle case to eight selected platforms and a fixed set of platform-specific fixtures and controls. It supports the dated account-existence observations and per-tool outcomes shown here. The sample favors developer/community services, contains repeated fixtures and a GitHub organization, and includes no newly created owner-controlled positive accounts. Public fixtures are upstream test inputs; we make no claim about their ownership or consent to an identity investigation. Broader consumer social networks, authenticated profiles, the Android app and whole catalogues were not measured.</p>')
    add('<p>The reference and MyRecon share some official API sources, so this is a publisher-run regression study rather than an independent audit. Thirty-five controls and one network window cannot estimate population error rates. Eighteen reference negatives and six positives were decisive; eleven references remained unknown. Exclusions reduce effective scope, which is why both the common planned scope and scored denominators are published. No production detection rules were changed in response to this study. Known fixtures are not a held-out evaluation, and a matching handle does not prove identity, common ownership or registration availability.</p>')
    add('<p>See the <a href="/blog/username-search-benchmark-research.html">earlier case study and separate daily regression snapshot</a>, the <a href="/blog/sherlock-vs-maigret-vs-myrecon.html">workflow comparison</a>, and the <a href="/guides/account-enumeration-false-positives.html">false-positive review guide</a>. Corrections can be reported through the <a href="/contact.html">contact page</a>; replacement observations should retain their own dates.</p>')
    add('<h2 id="sources">Primary sources</h2><ul><li><a href="https://github.com/sherlock-project/sherlock">Sherlock upstream project</a> and its pinned site-rule links in the manifest.</li><li><a href="https://github.com/soxoj/maigret">Maigret upstream project</a> and its pinned fixture fields in the manifest.</li><li><a href="https://docs.github.com/en/rest/users/users#get-a-user">GitHub user endpoint</a>, <a href="https://docs.gitlab.com/api/users/">GitLab Users API</a>, <a href="https://github.com/HackerNews/API#users">Hacker News Users API</a> and <a href="https://developers.forem.com/api/v1#tag/users/operation/getUser">Forem user API</a>.</li><li>The account-specific reference URLs and captured evidence for every platform appear in the matrix and downloadable JSON.</li></ul>')
    return '\n\n'.join(parts) + '\n'


def publish(source):
    data = json.loads(source.read_text(encoding="utf-8"))
    validate(data)
    directory = ROOT / "frontend/assets/downloads" / EVIDENCE
    directory.mkdir(parents=True, exist_ok=True)
    write(directory / "study.json", data)
    # Preserve exact prepared bytes; manifest_sha256 refers to this file.
    controls = ROOT / "backend/data/username-study-controls.json"
    if hashlib.sha256(controls.read_bytes()).hexdigest() != data['manifest_sha256']:
        raise ValueError("Predeclared manifest hash changed")
    (directory / "controls.json").write_bytes(controls.read_bytes())
    columns = ['control_id','platform','handle','cohort','tool','reference_verdict','reference_url','reference_status','reference_started_utc','reference_finished_utc','reference_facts','reference_body_sha256','prediction','native_status','prediction_status','reason','outcome','prediction_started_utc','prediction_finished_utc']
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(columns)
    for row in data['checks']:
        r = row['reference']
        for t in TOOLS:
            p = row[t]
            writer.writerow([row['id'],row['platform'],row['handle'],row['cohort'],t,r['verdict'],r['url'],r.get('status_code'),r['started_at_utc'],r['finished_at_utc'],json.dumps(r['facts'],sort_keys=True),r.get('body_sha256'),p['verdict'],p.get('native_status'),p.get('status_code'),p.get('reason_code'),p['outcome'],p['started_at_utc'],p['finished_at_utc']])
    (directory / 'checks.csv').write_text(stream.getvalue(), encoding='utf-8')
    readme = f'''# Dated username-control study — 1 November 2026

35 platform-specific controls, eight platforms, three tools. Published upstream
test fixtures are not accounts owned by MyRecon or the user. Every fixture stays
on its original platform; no personal social-media handles or customer history.
All outcomes are dated observations, including exclusions and unknowns.

## Reproduce with Python 3.12

1. Clone https://github.com/4ryanwalia/Myrecon.git and check out
   `{data['tool_metadata']['myrecon']['commit']}`.
2. Create and activate an isolated Python 3.12 environment.
3. Copy `reproduction/expanded_username_study.py` into `backend/tools/` in that
   checkout. Other helpers are also included for inspection.
4. Run `python -m pip install requests -r backend/tools/requirements-benchmark.txt`.
   Both third-party tool source revisions are immutable pins.
5. Copy controls.json to the checkout root, then run from the checkout root:

   python backend/tools/expanded_username_study.py --manifest controls.json --output output/new-study.json

The manifest is fixed before predictions. Reference observations run first;
then the MyRecon web engine, Sherlock and Maigret run sequentially. Fixture
expectations and random-looking handles never determine reference truth.
One connection at a time, no retries, supplied authentication or block bypass.
Sherlock's current upstream exclusion list is captured per run; it can change.
Reproduce an observation, not an identical historical result: provider state,
network conditions and exclusions may differ. This is not a speed comparison.

## Inspect the retained evidence

study.json: reference identifiers, status, timing, response SHA-256/length,
all tool outcomes, native statuses, selected upstream rule snapshots, exclusions,
versions and source hashes. Complete profile bodies and credentials are omitted.
controls.json: exact predeclared manifest; its byte hash is manifest_sha256.
checks.csv: 105 rows (35 controls x 3 tools), including excluded/unknown cases.

Summary scoring: TP/TN/FP/FN need definitive reference AND prediction. The union
of unknown references/predictions is unresolved_checks, with no double counting.
Coverage = scored / 35. False-positive denominator = FP + TN. Native CLAIMED
outcomes remain visible even when HTTP-error normalization quarantines them.
No false positives were observed on definitive controls in this run. This does
not prove zero population error. Public fixtures, API overlap with MyRecon,
selection bias and eleven unresolved references limit the conclusion.

SHA256SUMS.txt covers the ZIP and loose downloads. The ZIP's CONTENTS.sha256
covers every included payload file (excluding the checksum file itself).
Upstream source-rule license notices are included under licenses/.
'''
    (directory / 'README.md').write_text(readme, encoding='utf-8')
    files = {name: (directory / name).read_bytes() for name in ('study.json','controls.json','checks.csv','README.md')}
    for name in ('expanded_username_study.py','benchmark_worker.py','daily_benchmark.py','benchmark-tools.json','requirements-benchmark.txt'):
        files['reproduction/' + name] = (ROOT / 'backend/tools' / name).read_bytes()
    # Include upstream license texts from their pinned distributions.
    import importlib.metadata
    for tool, package in (('sherlock','sherlock-project'),('maigret','maigret')):
        dist = importlib.metadata.distribution(package)
        candidates = [p for p in dist.files or [] if p.name.lower().startswith('license')]
        if not candidates:
            raise ValueError('Missing upstream license notice')
        files[f'licenses/{tool}-LICENSE'] = Path(dist.locate_file(candidates[0])).read_bytes()
    files['CONTENTS.sha256'] = ''.join(f'{hashlib.sha256(body).hexdigest()}  {name}\n' for name, body in sorted(files.items())).encode()
    with zipfile.ZipFile(directory / 'evidence.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026,11,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, body)
    names = ('study.json','controls.json','checks.csv','README.md','evidence.zip')
    (directory / 'SHA256SUMS.txt').write_text(''.join(f'{hashlib.sha256((directory / name).read_bytes()).hexdigest()}  {name}\n' for name in names), encoding='utf-8')
    article = ROOT / 'frontend/content/blog' / f'{SLUG}.html'
    article.write_text(render(data), encoding='utf-8')
    print(f'Packaged {len(data["checks"])} controls; article: {article}')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    publish(parser.parse_args().input)
