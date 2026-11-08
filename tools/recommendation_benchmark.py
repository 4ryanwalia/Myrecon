"""Plan and summarize manually observed consumer-assistant samples. No model simulation."""
import argparse
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
QUESTIONS = REPO / 'docs' / 'recommendation-measurement' / 'questions.json'
ROOT = REPO / 'measurement-data' / 'recommendations'
PLATFORMS = ('ChatGPT', 'Gemini', 'Claude')


def panel():
    data = json.loads(QUESTIONS.read_text(encoding='utf-8'))
    assert 20 <= len(data['questions']) <= 30
    assert len({q['id'] for q in data['questions']}) == len(data['questions'])
    return data


def plan(run_id, batch):
    data = panel()
    path = ROOT / 'runs' / (run_id + '.json')
    if path.exists():
        raise SystemExit('Run exists; preserve it and append attempts instead of overwriting.')
    questions = [q for q in data['questions'] if batch is None or q['batch'] == batch]
    run = {'run_id': run_id, 'panel_version': data['version'], 'timezone': 'Asia/Kolkata',
           'batch': batch, 'questions': questions, 'search_suffix': data['search_suffix'],
           'observations': [], 'traffic': [], 'notes': []}
    for platform in PLATFORMS:
        for q in questions:
            run['observations'].append({'question_id': q['id'], 'platform': platform,
                'attempt': 1, 'prompt': q['question'] + data['search_suffix'],
                'status': 'not_run', 'observed_at': None, 'model_label': None,
                'account_mode': None, 'locale': 'English; India operator',
                'fresh_session': None, 'search_enabled': None, 'search_observed': None,
                'mentioned': None, 'recommended': None, 'myrecon_cited_urls': [],
                'cited_urls': [], 'answer_urls': [], 'citation_capture': 'not_captured',
                'inaccuracies': [], 'accuracy_review': 'not_reviewed', 'evidence': None})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, indent=2) + '\n', encoding='utf-8')
    print(path)


def report(path):
    data = panel()
    run = json.loads(path.read_text(encoding='utf-8'))
    questions = {q['id']: q for q in run.get('questions', data['questions'])}
    rows = run['observations']
    seen = set()
    for row in rows:
        key = (row['platform'], row['question_id'], row['attempt'])
        assert key not in seen, 'Duplicate attempt'
        seen.add(key)
        assert row['question_id'] in questions and row['platform'] in PLATFORMS
        assert row['prompt'] == questions[row['question_id']]['question'] + run.get('search_suffix', data['search_suffix'])
        assert row['status'] in ('not_run', 'success', 'capture_pending', 'assistant_error', 'login_required', 'rate_limited', 'search_unavailable', 'interrupted')
        if row['status'] == 'success':
            assert isinstance(row['mentioned'], bool) and isinstance(row['recommended'], bool)
            assert row['fresh_session'] is True and row['search_enabled'] is True
            assert row['evidence'] and row['observed_at']
        else:
            assert row['mentioned'] is None and row['recommended'] is None, 'Missing/error is not a negative result'
    # A retry never adds a second denominator for the same question/platform.
    valid = {}
    for row in rows:
        if row['status'] == 'success':
            valid.setdefault((row['platform'], row['question_id']), row)
    text = [f"# Recommendation samples: {run['run_id']}", '',
            'These observations are samples under the recorded settings, not rankings or market share.', '',
            '| Assistant | Segment | Valid questions | Mentions | Recommendations | MyRecon citations captured |',
            '|---|---|---:|---:|---:|---:|']
    for platform in PLATFORMS:
        for segment in ('unbranded', 'branded'):
            group = [r for r in valid.values() if r['platform'] == platform and questions[r['question_id']]['segment'] == segment]
            n = len(group)
            cells = [str(sum(bool(r[k]) for r in group)) + '/' + str(n) if n else 'unavailable'
                     for k in ('mentioned', 'recommended')]
            citations = str(sum(len(r['myrecon_cited_urls']) for r in group)) if n else 'unavailable'
            if any(r['citation_capture'] in ('partial', 'not_captured') for r in group):
                citations += ' (capture incomplete)'
            cells.append(citations)
            text.append(f"| {platform} | {segment} | {n} | {' | '.join(cells)} |")
    text += ['', 'Attempt statuses: ' + ', '.join(f'{k}={v}' for k, v in sorted(Counter(r['status'] for r in rows).items())), '',
             'Missing, blocked and failed attempts are excluded. First successful attempt per question/platform is used; preserve all retries.', '',
             'Traffic and conversions are recorded separately; benchmark responses cannot establish visits or conversions.', '',
             '| Assistant | Window | Visit events | Complete scan events | Partial scan events | New signups | Evidence/status |',
             '|---|---|---:|---:|---:|---:|---|']
    for t in run['traffic']:
        vals = [str(t.get(k)) if t.get(k) is not None else 'unavailable' for k in ('visits', 'completed_scans', 'partial_scans', 'signups')]
        text.append(f"| {t['platform']} | {t['window']} | {' | '.join(vals)} | {t['status']} |")
    text += ['', '| Question | Assistant | Status | Mention | Recommendation | Citation capture |',
             '|---|---|---|---|---|---|']
    for r in rows:
        text.append(f"| {r['question_id']} | {r['platform']} | {r['status']} | {r['mentioned']} | {r['recommended']} | {r['citation_capture']} |")
    text += ['', '## Accuracy findings', '']
    for r in rows:
        for error in r['inaccuracies']:
            text += [f"- {r['platform']} {r['question_id']}: {error['claim']} Correction: {error['correction']} Evidence: {error['evidence_url']}"]
    text += ['', *run.get('notes', []), '']
    output = path.with_suffix('.md')
    output.write_text('\n'.join(text), encoding='utf-8')
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('plan'); p.add_argument('run_id'); p.add_argument('--batch', type=int, choices=range(1, 6))
    p = sub.add_parser('report'); p.add_argument('run', type=Path)
    args = parser.parse_args()
    if args.command == 'plan': plan(args.run_id, args.batch)
    else: report(args.run)
