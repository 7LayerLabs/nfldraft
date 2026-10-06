"""Derive transparent positional reference distributions from published profiles.

Each player contributes at most one observation per position/metric. Timed drills,
jumps and bench results use official combine testing when available; body size is
descriptive. Percentiles compare this archive's drafted players, never NFL talent.
"""
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean

ROOT = Path(__file__).resolve().parent
SIZE = {'height', 'weight', 'handSize', 'armLength', 'wingspan'}
METRICS = [*SIZE, 'fortyYardDash', 'tenYardSplit', 'twentyYardSplit', 'threeConeDrill',
           'twentyYardShuttle', 'sixtyYardShuttle', 'verticalJump', 'broadJump', 'benchPress']
ALIASES = {'T':'OT', 'G':'OG', 'NT':'DT', 'ILB':'LB', 'FS':'S', 'SS':'S', 'EDGE':'DE', 'CB / WR':'WR'}
MINIMUM_RANK_SAMPLE = 20


def quantile(values, fraction):
    index = (len(values) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def preferred(readings):
    combine = [o for o in readings if o['event'] == 'NFL Scouting Combine']
    official = [o for o in combine if o['designation'].upper() == 'OFFICIAL']
    other_official = [o for o in readings if o['designation'].upper() == 'OFFICIAL' and 'unspecified' not in o['event']]
    dated = [o for o in readings if o.get('date') and 'unspecified' not in o['event']]
    return (official or combine or other_official or dated or readings)[0]


def main():
    profiles = [json.loads(file.read_text(encoding='utf-8')) for file in sorted((ROOT / 'local' / 'data' / 'profiles').glob('*.json'))]
    assert len(profiles) == 2569
    collected = defaultdict(lambda: defaultdict(lambda: {'official': [], 'reported': []}))
    for profile in profiles:
        position = ALIASES.get(profile['position'], profile['position'])
        positions = ['WR', 'CB'] if profile['position'] == 'CB / WR' else [position]
        if position in ('OT','OG','C'):
            positions.append('OL')
        if position in ('CB','S'):
            positions.append('DB')
        for metric in METRICS:
            readings = profile['workouts']['measurements'].get(metric, [])
            if not readings:
                continue
            reported = preferred(readings)['value']
            official = [o for o in readings if o['event'] == 'NFL Scouting Combine' and o['designation'].upper() == 'OFFICIAL']
            for group in positions:
                collected[group][metric]['reported'].append(reported)
                if official:
                    collected[group][metric]['official'].append(official[0]['value'])
    positions = {}
    for position, metrics in sorted(collected.items()):
        positions[position] = {}
        for metric, observations in metrics.items():
            size = metric in SIZE
            use_official = bool(observations['official']) and not size
            values = sorted(observations['official'] if use_official else observations['reported'])
            scope = ('Official NFL Scouting Combine results only. The cancelled 2021 in-person combine contributes no results.' if use_official else
                     'Reported prospect body measurements; measurement dates and events vary.' if size else
                     'Mixed reported workouts: combine, pro-day and event-unspecified observations. Comparable official combine results were unavailable.')
            rule = ('One official combine observation per drafted player; repeated source copies are not additional players.' if use_official else
                    'One preferred reported observation per drafted player. Other source/event values remain in individual profiles.')
            positions[position][metric] = {'n':len(values), 'mean':round(fmean(values),6), 'median':quantile(values,.5),
                                          'p25':quantile(values,.25), 'p75':quantile(values,.75), 'min':values[0], 'max':values[-1],
                                          'values':values, 'cohort':f'{position} players selected in the 2017–2026 regular NFL drafts with eligible reported results.',
                                          'eventScope':scope, 'selectionRule':rule, 'rankable':len(values)>=MINIMUM_RANK_SAMPLE,
                                          'officialCombineOnly':use_official}
    payload = {'generatedAt':datetime.now(timezone.utc).isoformat(), 'positions':positions, 'positionAliases':ALIASES,
               'minimumRankSample':MINIMUM_RANK_SAMPLE,
               'methodology':{'population':'Drafted players in this archive, 2017–2026; not every combine invitee or current NFL player.',
                              'ranking':'Empirical midpoint ranks for ties. Lower timed results receive higher performance percentiles; jumps and bench use higher results. Body size percentiles describe larger measurements, not better play.',
                              'averages':'Arithmetic means. Median and quartiles use linear interpolation of sorted observations.',
                              'missing':'Missing and quarantined results are excluded; no imputation. A minimum of 20 results is required for percentile bands.',
                              'positions':'Draft-listed positions. NT joins DT, ILB joins LB, FS/SS join S. OLB stays separate from LB. Two-way CB/WR players enter both cohorts; WR is the default comparison.',
                              'eventComparison':'Comparing pro-day or unspecified timing against official combine results is approximate and explicitly labelled.'}}
    destination = ROOT / 'local' / 'data' / 'measurement-benchmarks.json'
    destination.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    assert all(stats['n']==len(stats['values']) and stats['values']==sorted(stats['values']) and stats['min']<=stats['mean']<=stats['max']
               for metrics in positions.values() for stats in metrics.values())
    wr = positions['WR']['fortyYardDash']
    percentile = 100*(sum(value>4.34 for value in wr['values'])+.5*wr['values'].count(4.34))/wr['n']
    assert percentile > 80
    print(f'Built {sum(map(len,positions.values()))} metric distributions for {len(positions)} positions; WR 4.34 sec: {percentile:.1f} percentile, n={wr["n"]}, mean={wr["mean"]:.3f}.')


if __name__ == '__main__':
    main()
