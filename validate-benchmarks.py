"""Check the published comparison populations and downloadable measurement data."""
import json
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'local' / 'data'
benchmarks = json.loads((DATA / 'measurement-benchmarks.json').read_text(encoding='utf-8'))
definitions = json.loads((DATA / 'measurement-definitions.json').read_text(encoding='utf-8'))
assert len(definitions) == 14
assert all(d['direction'] in ('size', 'higher', 'lower') and d['sourceUrl'].startswith('https://') for d in definitions.values())
official = defaultdict(lambda: defaultdict(list))
reported = defaultdict(lambda: defaultdict(int))
for file in (DATA / 'profiles').glob('*.json'):
    profile = json.loads(file.read_text(encoding='utf-8'))
    position = benchmarks['positionAliases'].get(profile['position'], profile['position'])
    groups = ['WR', 'CB'] if profile['position'] == 'CB / WR' else [position]
    if position in ('C', 'OT', 'OG'):
        groups.append('OL')
    if position in ('S', 'CB'):
        groups.append('DB')
    for metric, readings in profile['workouts']['measurements'].items():
        if metric not in definitions:
            continue
        eligible = [o for o in readings if o['event'] == 'NFL Scouting Combine' and o['designation'].upper() == 'OFFICIAL']
        for group in groups:
            reported[group][metric] += 1
            if eligible:
                assert profile['year'] != 2021
                official[group][metric].append(eligible[0]['value'])

count = 0
for position, metrics in benchmarks['positions'].items():
    for metric, stats in metrics.items():
        count += 1
        values = stats['values']
        assert len(values) == stats['n'] and values == sorted(values)
        assert abs(stats['mean'] - fmean(values)) < 0.000001
        assert stats['min'] <= stats['p25'] <= stats['median'] <= stats['p75'] <= stats['max']
        assert stats['rankable'] == (stats['n'] >= benchmarks['minimumRankSample'])
        size = definitions[metric]['direction'] == 'size'
        if not size and official[position][metric]:
            assert stats['officialCombineOnly'] and values == sorted(official[position][metric])
        else:
            assert not stats['officialCombineOnly'] and stats['n'] == reported[position][metric]

wr = benchmarks['positions']['WR']['fortyYardDash']
percentile = 100 * (sum(v > 4.34 for v in wr['values']) + .5 * wr['values'].count(4.34)) / wr['n']
assert wr['n'] == 221 and 89.9 <= percentile <= 90.1
with ZipFile(ROOT / 'local' / 'player-profiles-2017-2026.zip') as archive:
    assert archive.testzip() is None
    assert len([n for n in archive.namelist() if n.startswith('profiles/') and n.endswith('.json')]) == 2569
    for name in ('measurement-definitions.json', 'measurement-benchmarks.json', 'coverage.json', 'current-teams.json'):
        assert archive.read(name) == (DATA / name).read_bytes()
print(f'Validated {count} positional distributions, official-combine eligibility, WR 4.34 percentile and full profile ZIP.')
