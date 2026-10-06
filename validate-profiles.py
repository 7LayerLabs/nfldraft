"""Audit all published identities, measurements, source provenance and college cutoffs."""
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
drafts = json.loads((ROOT / 'drafts.json').read_text(encoding='utf-8'))
expected = {f'{year}-{row[1]}': (int(year), row) for year, rows in drafts.items() for row in rows}
files = {file.stem: file for file in (ROOT / 'local' / 'data' / 'profiles').glob('*.json')}
assert set(files) == set(expected), 'Every selection must have exactly one published file'
college_ids = {}
nfl_ids = {}
counts = Counter()
limits = {'height': (50,90), 'weight': (120,450), 'handSize': (6,13), 'armLength': (20,42),
          'wingspan': (55,95), 'fortyYardDash': (3.8,7), 'tenYardSplit': (1,3), 'twentyYardSplit': (1.5,4),
          'threeConeDrill': (5,10), 'twentyYardShuttle': (3,6.5), 'sixtyYardShuttle': (9,17),
          'verticalJump': (10,50), 'broadJump': (65,155), 'benchPress': (1,55)}
units = {key: 'in' for key in ('height','handSize','armLength','wingspan','verticalJump','broadJump')}
units.update({key: 's' for key in ('fortyYardDash','tenYardSplit','twentyYardSplit','threeConeDrill','twentyYardShuttle','sixtyYardShuttle')})
units.update(weight='lb', benchPress='reps')
for pid, path in files.items():
    published = path.read_text(encoding='utf-8')
    assert 'rawReference' not in published and '.agent-reach' not in published, pid
    profile = json.loads(published)
    year, row = expected[pid]
    assert [profile[k] for k in ('round','pick','team','via','name','position','college')] == row[:7], pid
    assert profile['id'] == pid and profile['year'] == year
    workout = profile['workouts']
    nfl_id = workout.get('nflPersonId')
    if nfl_id:
        assert (year,nfl_id) not in nfl_ids, f'Duplicate NFL identity: {pid}/{nfl_ids.get((year,nfl_id))}'
        nfl_ids[(year,nfl_id)] = pid
    sources = {source['id']:source for source in workout['sources']}
    for metric, observations in workout['measurements'].items():
        assert observations, (pid,metric)
        for obs in observations:
            assert isinstance(obs['value'], (int,float)) and math.isfinite(obs['value']), (pid,metric)
            assert obs['sourceId'] in sources and sources[obs['sourceId']]['url'].startswith('https://'), (pid,metric)
            assert obs['unit'] and obs['event'] and obs['designation'], (pid,metric)
            if metric in limits:
                low,high = limits[metric]
                assert low <= obs['value'] <= high, (pid,metric,obs)
                assert obs['unit'] == units[metric], (pid,metric,obs)
            if year == 2021:
                assert obs['event'] != 'NFL Scouting Combine', (pid,metric)
            counts['observations'] += 1
    scouting = workout['scouting']
    quote_words = sum(len((scouting.get(key) or '').split()) for key in ('strengthQuote','weaknessQuote','overviewQuote'))
    assert quote_words <= 24, (pid,quote_words)
    assert 'rawReference' not in scouting and 'rawReference' not in workout.get('bio',{}), pid
    stats = profile['collegeStats']
    assert stats['status'] != 'error', pid
    aid = stats.get('athleteId')
    if aid:
        assert aid not in college_ids, f'Duplicate college identity: {pid}/{college_ids.get(aid)}'
        college_ids[aid] = pid
    for category in stats.get('categories',[]):
        seen = set()
        keys = {column['key'] for column in category['columns']}
        for season in category['seasons']:
            assert (season['year'] is None and season.get('seasonLabel') and 'biography' in category['label'].lower()) or 1995 <= season['year'] < year, (pid,season)
            identity = (season['year'],season.get('seasonLabel'),season['teamId'])
            assert identity not in seen, (pid,identity)
            seen.add(identity)
            assert set(season['values']) <= keys, (pid,category['key'])
        assert set(category['career']['values']) <= keys, (pid,category['key'])
    for experience in stats.get('experience',[]):
        assert experience['year'] == 'Career' or (experience['year'] is None and experience.get('seasonLabel')) or experience['year'] < year, (pid,experience)
        assert experience.get('sourceUrl','').startswith('https://'), (pid,experience)
    counts['profiles'] += 1

def stat(pid, category, metric):
    profile = json.loads(files[pid].read_text(encoding='utf-8'))
    return next(c['career']['values'][metric] for c in profile['collegeStats']['categories'] if c['key']==category)

assert stat('2017-10','passing','passingYards') == '11,252'
assert stat('2025-1','passing','passingYards') == '18,187'
assert stat('2026-1','passing','passingYards') == '8,247'
assert stat('2017-1','defensive','sacks') == '32.5'
for pid,value in [('2017-10',9.25),('2025-1',9),('2026-1',9.5)]:
    profile = json.loads(files[pid].read_text(encoding='utf-8'))
    assert any(o['value']==value for o in profile['workouts']['measurements']['handSize']), pid
mendoza = json.loads(files['2026-1'].read_text(encoding='utf-8'))
assert any(o['value']==225 and o['event']=='NFL Scouting Combine' for o in mendoza['workouts']['measurements']['weight'])
assert not any(o['value']==236 and o['event']=='NFL Scouting Combine' for o in mendoza['workouts']['measurements']['weight'])
print(f'PASS: {counts["profiles"]:,} profiles, {counts["observations"]:,} attributed observations; unique identities, units, source links, quotations and college cutoffs.')
