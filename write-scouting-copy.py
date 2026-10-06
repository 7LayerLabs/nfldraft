"""Write original scout-style copy for every player's draft-day and current reports.

Run after build-grades.py and build-scouting-reports.py:
    python write-scouting-copy.py --sample 2017-10,2021-7      (preview a few players)
    python write-scouting-copy.py                              (all players; resumable)
    python write-scouting-copy.py --merge                      (write cached copy into profiles)

Uses the local Claude Code CLI (`claude -p`). Two separate passes so nothing leaks across time:
  draft   - sees only pre-draft facts plus the NFL.com narrative from the private cache (background
            only; never republished). Any 6-word sequence shared with that narrative is rejected.
  current - sees only a plain fact sheet built from the archive's NFL data; every claim must come
            from a fact line.
Both passes reject copy containing numbers that are not in the player's input.
Output cache: ~/.agent-reach/nfl-player-profiles/writeups.json
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'local' / 'data'
CACHE = Path.home() / '.agent-reach' / 'nfl-player-profiles'
OUT = CACHE / 'writeups.json'
BATCH = 15
WORKERS = 4
MODEL = 'sonnet'
SCALE = ('Grades use one 5.0-8.0 scale: 7.5+ rare/All-Pro caliber, 7.0 Pro Bowl caliber, 6.7 high-end starter, '
         '6.5 quality starter, 6.3 average starter, 6.1 spot starter/top backup, 6.0 backup/special teams, '
         '5.7 fringe roster, below 5.7 did not stick.')
STYLE = """- 70 to 110 words. Plain, confident football language, like an experienced NFL scout. Specific, not generic.
- No em dashes, no en dashes, no emojis, no hashtags, no bullet points, no headings. Use commas, periods and semicolons.
- Use numbers exactly as they appear in the input; never add up, derive or estimate new numbers. Small counts may be written as words.
- Output ONLY a JSON object mapping each player id to the write-up string. No other text."""

DRAFT_PROMPT = """INSTRUCTION
Write a pre-draft scouting report for each prospect below, as if it is April of his draft year and the draft has not happened yet.

CONTEXT
- """ + SCALE + """
- "nflcomNotes" is a published third-party report. It is background only: restate its ideas entirely in your own words.
- Testing and production percentiles compare him with drafted players at his position.

CONSTRAINTS
- Cover: how he wins, the main concerns, what the testing says, college production, and the projected role. You may cite the NFL.com grade and our archive draft grade tier.
- Never mention anything after the draft: no NFL teams, NFL stats, draft slot, awards or career outcomes.
- Never reuse a phrase of five or more consecutive words from nflcomNotes, and do not quote it.
- Do not invent facts that are not in the input (injuries, character, scheme, family, numbers).
""" + STYLE + """

PROSPECTS:
__PLAYERS__
"""

CURRENT_PROMPT = """INSTRUCTION
Write a current scouting report for each NFL player below, as of __ASOF__: his role now, trajectory, what he does well, what holds him back, and a one-sentence outlook.

CONTEXT
- """ + SCALE + """
- Each player has a list of FACTS. They are the only things you know about his NFL career.

CONSTRAINTS
- Every factual statement must be directly supported by a FACT line. You may add scouting interpretation (durable, ascending, declining, reliable) only when the facts plainly show it.
- Do not mention teams, positions, sides (left/right), roles, injuries, trades or seasons beyond what the FACTS state. If a fact says "listed T", say tackle, not left or right tackle.
- Mention his current archive grade tier. If he has no NFL games, say so plainly and say what to watch for.
""" + STYLE + """

PLAYERS:
__PLAYERS__
"""

CAREERS = None
lock = threading.Lock()


def ngrams(text, n=6):
    words = re.findall(r"[a-z0-9']+", (text or '').lower())
    return {' '.join(words[i:i + n]) for i in range(len(words) - n + 1)}


def clean(text):
    text = re.sub(r'\s*[—–]\s*', ', ', text)
    return re.sub(r'\s+', ' ', text).strip()


NUMBER = re.compile(r'(?<![\w.])(\d[\d,]*(?:\.\d+)?)')


def allowed_numbers(source):
    allowed = {n.replace(',', '') for n in NUMBER.findall(source)}
    extra = set()
    for n in allowed:
        if re.fullmatch(r'0\.\d+', n):
            extra |= {str(round(float(n) * 100, 1)).rstrip('0').rstrip('.'), str(round(float(n) * 100))}
        if re.fullmatch(r'\d+\.\d+', n):
            extra |= {str(round(float(n))), str(round(float(n), 1))}
    return allowed | extra


def bad_numbers(text, allowed):
    return [raw for raw in NUMBER.findall(text or '') if raw.replace(',', '').rstrip('.') not in allowed]


def draft_input(pid, profile, narrative, rec):
    draft = (profile.get('scoutingReports') or {}).get('draft') or {}
    g = profile.get('grades') or {}
    notes = ' '.join(filter(None, [narrative.get('overview'), 'Strengths: ' + narrative['strengths'] if narrative.get('strengths') else None,
                                   'Weaknesses: ' + narrative['weaknesses'] if narrative.get('weaknesses') else None]))
    return {'id': pid, 'name': rec['name'], 'position': rec['position'], 'college': rec['college'], 'draftYear': rec['year'],
            'nflcomGrade': g.get('nfl'), 'nflcomGradeRankInClass': draft.get('gradeRankClass'), 'classGraded': draft.get('classGraded'),
            'nflcomGradeRankAtPosition': draft.get('gradeRankPosition'), 'positionGraded': draft.get('positionGraded'),
            'projectedRound': draft.get('projection'), 'nflcomComparison': draft.get('comparison'),
            'testing': [f"{t['label']} {t['value']} {t['unit']} ({round(t['percentile'])} percentile{', size' if t['kind'] == 'size' else ''})" for t in draft.get('athletic', [])],
            'collegeProduction': [f"{p['label']}: {p.get('final')} in {p.get('finalYear')} (ranked {p.get('finalRank')} of {p.get('finalOf')} at his position in the class); career {p.get('career')} (ranked {p.get('careerRank')} of {p.get('careerOf')})" for p in draft.get('production', [])],
            'archiveDraftGrade': g.get('draft'), 'archiveDraftTier': g.get('draftTier'),
            'nflcomNotes': ' '.join(notes.split()[:320]) or None}


def current_input(pid, profile, rec, asof):
    current = (profile.get('scoutingReports') or {}).get('current') or {}
    g = profile.get('grades') or {}
    seasons = CAREERS['players'][pid]['seasons']
    live_year = CAREERS['inProgress']['season']
    facts = [f"As of {asof}, {rec['name']} is in Year {live_year - rec['year'] + 1} of his NFL career; drafted {rec['year']} as a {rec['position']} from {rec['college']}.",
             'Current status: ' + (f"on the {current.get('status')} roster" + (f" ({current['rosterStatus'].lower()})" if current.get('rosterStatus') else '') if current.get('onRoster') else str(current.get('status')).lower()) + '.']
    done = [s for s in seasons if not s.get('inProgress')]
    for s in done:
        if not s['g']:
            facts.append(f"{s['season']} (Year {s['cy']}): did not play in a regular-season game.")
            continue
        bits = [f"{s['g']} games", f"{s.get('gs', 0) or 0} starts"]
        if s.get('av') is not None:
            bits.append(f"{s['av']} AV")
        if s.get('pfrPos'):
            bits.append(f"listed {s['pfrPos']}")
        if s.get('teams'):
            bits.append('team ' + '/'.join(s['teams']))
        if s.get('all_pro'):
            bits.append('first-team All-Pro')
        elif s.get('all_pro_2nd'):
            bits.append('second-team All-Pro')
        if s.get('pro_bowl'):
            bits.append('Pro Bowl')
        if s.get('awards'):
            bits.append(', '.join(s['awards']))
        facts.append(f"{s['season']} (Year {s['cy']}): " + ', '.join(bits) + '.')
    played = [s for s in done if s['g']]
    if played:
        facts.append(f"Career through {done[-1]['season']}: {sum(s['g'] for s in done)} games, {sum(s.get('gs') or 0 for s in done)} starts, "
                     f"{sum(1 for s in done if s.get('pro_bowl'))} Pro Bowls, {sum(1 for s in done if s.get('all_pro'))} first-team All-Pros.")
    if current.get('peakAv'):
        facts.append(f"Career-best AV: {current['peakAv']['av']} in {current['peakAv']['season']}.")
    if current.get('strengths'):
        facts.append(f"Strengths in {current['latest']['season']} vs all drafted players at his position: " +
                     '; '.join(f"{r['label']} {r['text']} ({round(r['percentile'])} percentile)" for r in current['strengths']) + '.')
    if current.get('concerns'):
        facts.append(f"Weak spots in {current['latest']['season']}: " +
                     '; '.join(f"{r['label']} {r['text']} ({round(r['percentile'])} percentile)" for r in current['concerns']) + '.')
    if current.get('careerYear'):
        c = current['careerYear']
        facts.append(f"{c['label']} in Year {c['cy']}: {c['text']} against a median of {c['medianText']} for players at his position in that career year.")
    live = next((s for s in seasons if s.get('inProgress')), None)
    if live and live['g']:
        line = (current.get('thisSeason') or {}).get('line') or []
        facts.append(f"{live['season']} so far: {live['g']} games, {live.get('gs') or 0} starts" + (', listed ' + live['pfrPos'] if live.get('pfrPos') else '') +
                     (', team ' + '/'.join(live['teams']) if live.get('teams') else '') + ('; ' + ', '.join(f"{i['text']} {i['label']}" for i in line) if line else '') + '.')
    elif live:
        facts.append(f"{live['season']} so far: no regular-season games.")
    if g.get('current') is not None:
        facts.append(f"Archive current grade: {g['current']} ({g['currentTier']}); basis: {g.get('currentBasis')}.")
    if g.get('hindsight') is not None:
        facts.append(f"Archive hindsight grade for his career so far: {g['hindsight']} ({g['hindsightTier']}){' (provisional)' if g.get('hindsightProvisional') else ''}.")
    return {'id': pid, 'name': rec['name'], 'facts': facts}


def call_claude(prompt):
    for attempt in range(3):
        try:
            result = subprocess.run(['claude', '-p', '--model', MODEL, '--effort', 'low', '--output-format', 'text'], input=prompt,
                                    capture_output=True, text=True, encoding='utf-8', timeout=1200)
            match = re.search(r'\{.*\}', result.stdout or '', re.S)
            if result.returncode == 0 and match:
                return json.loads(match.group(0))
            print(f'  retry {attempt + 1}: exit {result.returncode} {(result.stderr or "")[:200]}', flush=True)
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            print(f'  retry {attempt + 1}: {type(exc).__name__}', flush=True)
        time.sleep(10 * (attempt + 1))
    return {}


def main():
    global CAREERS
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--sample', help='comma-separated draft ids to (re)write and print')
    parser.add_argument('--merge', action='store_true', help='merge cached copy into profiles and exit')
    parser.add_argument('--kind', choices=['draft', 'current', 'both'], default='both')
    args = parser.parse_args()
    drafts = json.loads((ROOT / 'drafts.json').read_text(encoding='utf-8'))
    recs = {f'{y}-{r[1]}': {'year': int(y), 'round': r[0], 'pick': r[1], 'team': r[2], 'name': r[4], 'position': r[5], 'college': r[6]}
            for y, rows in drafts.items() for r in rows}
    narratives = json.loads((CACHE / 'scouting-text.json').read_text(encoding='utf-8'))
    done = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {}
    CAREERS = json.loads((DATA / 'nfl-careers.json').read_text(encoding='utf-8'))
    asof = f"{CAREERS['asOf']} ({CAREERS['inProgress']['season']} season through Week {CAREERS['inProgress']['throughWeek']})"

    if args.merge:
        merged = 0
        for pid in recs:
            file = DATA / 'profiles' / f'{pid}.json'
            profile = json.loads(file.read_text(encoding='utf-8'))
            reports = profile.get('scoutingReports') or {}
            for key in ('draft', 'current'):
                entry = (done.get(pid) or {}).get(key)
                if reports.get(key) is not None:
                    if entry and entry.get('text') and not entry.get('flags'):
                        reports[key]['writeup'] = entry['text']
                    else:
                        reports[key].pop('writeup', None)
            published = json.dumps(profile, ensure_ascii=False, separators=(',', ':'))
            if published != file.read_text(encoding='utf-8'):
                file.write_text(published, encoding='utf-8', newline='\n')
                merged += 1
        counts = {k: sum(1 for v in done.values() if (v.get(k) or {}).get('text') and not v[k].get('flags')) for k in ('draft', 'current')}
        print(f'Merged into {merged} profiles; clean write-ups cached: {counts}')
        return

    # Drop cached copy whose numbers no longer match the player's current data (grades or stats changed).
    stale = 0
    for pid, entry in list(done.items()):
        if pid not in recs:
            continue
        profile = json.loads((DATA / 'profiles' / f'{pid}.json').read_text(encoding='utf-8'))
        for kind in ('draft', 'current'):
            copy = (entry or {}).get(kind)
            if not copy or not copy.get('text'):
                continue
            source = draft_input(pid, profile, narratives.get(pid, {}), recs[pid]) if kind == 'draft' else current_input(pid, profile, recs[pid], asof)
            if bad_numbers(copy['text'], allowed_numbers(json.dumps(source, ensure_ascii=False) + ' ' + asof)):
                del entry[kind]
                stale += 1
    if stale:
        OUT.write_text(json.dumps(done, ensure_ascii=False), encoding='utf-8')
        print(f'Dropped {stale} cached write-ups that no longer match current data', flush=True)
    kinds = ['draft', 'current'] if args.kind == 'both' else [args.kind]
    jobs = []
    for kind in kinds:
        ids = args.sample.split(',') if args.sample else [pid for pid in recs if not ((done.get(pid) or {}).get(kind) or {}).get('text')]
        jobs += [(kind, ids[i:i + BATCH]) for i in range(0, len(ids), BATCH)]
    print(f'{len(jobs)} batches ({WORKERS} at a time)', flush=True)

    def run(kind, batch, attempt=0):
        inputs = {}
        for pid in batch:
            profile = json.loads((DATA / 'profiles' / f'{pid}.json').read_text(encoding='utf-8'))
            inputs[pid] = draft_input(pid, profile, narratives.get(pid, {}), recs[pid]) if kind == 'draft' else current_input(pid, profile, recs[pid], asof)
        template = DRAFT_PROMPT if kind == 'draft' else CURRENT_PROMPT
        prompt = template.replace('__ASOF__', asof).replace('__PLAYERS__', json.dumps(list(inputs.values()), ensure_ascii=False))
        result = call_claude(prompt)
        good, redo = {}, []
        for pid in batch:
            text = result.get(pid)
            if isinstance(text, dict):
                text = text.get(kind) or next(iter(text.values()), None)
            if not isinstance(text, str):
                redo.append(pid)
                continue
            text = clean(text)
            problems = []
            n = len(text.split())
            if not 45 <= n <= 150:
                problems.append(f'length {n}')
            bad = bad_numbers(text, allowed_numbers(json.dumps(inputs[pid], ensure_ascii=False) + ' ' + asof))
            if bad:
                problems.append(f'numbers not in input: {bad[:4]}')
            if kind == 'draft':
                n_ = narratives.get(pid, {})
                shared = ngrams(text) & ngrams(' '.join(filter(None, [n_.get('overview'), n_.get('strengths'), n_.get('weaknesses')])))
                if shared:
                    problems.append('copied wording: ' + '; '.join(sorted(shared)[:2]))
            if problems and attempt < 2:
                redo.append(pid)
                print(f'  {kind} {pid}: {problems}', flush=True)
            else:
                good[pid] = {'text': text, 'model': MODEL, 'writtenAt': time.strftime('%Y-%m-%d'), **({'flags': problems} if problems else {})}
        if redo and attempt < 2:
            good.update(run(kind, redo, attempt + 1))
        return good

    with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(run, kind, batch): kind for kind, batch in jobs}
        for i, future in enumerate(cf.as_completed(futures), 1):
            kind = futures[future]
            result = future.result()
            with lock:
                for pid, entry in result.items():
                    done.setdefault(pid, {})[kind] = entry
                OUT.write_text(json.dumps(done, ensure_ascii=False), encoding='utf-8')
            print(f'batch {i}/{len(jobs)} ({kind}): {len(result)} written', flush=True)
    if args.sample:
        for pid in args.sample.split(','):
            entry = done.get(pid, {})
            print(f"\n== {recs[pid]['name']} ({pid})\nDRAFT: {(entry.get('draft') or {}).get('text')}\nNOW:   {(entry.get('current') or {}).get('text')}")


if __name__ == '__main__':
    sys.exit(main())
